#!/usr/bin/env bash
# Scripted run of one deploy config in unitree_mujoco, with no person and no gamepad.
#
#   run_mujoco_deploy.sh <config.yaml> [profile.yaml] [out_dir]
#
# Run it inside the workspace's container (or a native install), where ROS 2, the built
# workspace and unitree_mujoco are. The defaults are profiles/demo_final.yaml and
# $WORKSPACE/sim_results/<policy>_<date>. Sequence:
#   Xvfb (unless SIM_DISPLAY is set) -> unitree_mujoco -> recorder (wait for /lowstate)
#   -> legged_rl_deploy_node (wait for "init done") -> gamepad driver
#      (L2+A, stand-up, start, profile segments as sticks, select) -> SIGINT deploy (CSV save)
#   -> stop recorder, sim, Xvfb -> copy $WORKSPACE/plot/data/data.csv -> analyze.py
#
# Needs: use_joystick: 0 in src/unitree_mujoco/simulate/config.yaml (the driver is then
# the only gamepad), and Xvfb (installed with apt if missing and running as root).
#
# Environment overrides:
#   WORKSPACE=<dir>       colcon workspace (default: four levels above this script)
#   SIM_ROS_DISTRO=humble ROS 2 distro under /opt/ros (default: $ROS_DISTRO, else humble)
#   SIM_DISPLAY=:0        render on an existing X display instead of a private Xvfb
#   SIM_SCENE=scene.xml   scene under unitree_mujoco/unitree_robots/go2/
#   SIM_DOMAIN=0          DDS domain (sim -i, ROS_DOMAIN_ID)
#   SIM_SETTLE=2.0        seconds between the first /lowstate and the deploy start
#   DRIVER_ARGS="..."     extra gamepad_driver.py arguments (e.g. "--end-hold 2")
#   ANALYZE_SETTLE=1.0    seconds skipped at the start of each segment in the summary
#   SIM_XVFB_SCREEN=1024x768x24  private Xvfb screen
# Exit code: the driver's (0 ok, 2 transition/timeout failure, 3 fall), or 1 on setup errors.
set -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 || $# -gt 3 || $1 == -h || $1 == --help ]]; then
  sed -n '2,27p' "$0"
  exit 1
fi

WS=${WORKSPACE:-$(cd "$HERE/../../../.." && pwd)}
WS=${WS%/}
SIM_BIN="$WS/src/unitree_mujoco/simulate/build/unitree_mujoco"
NODE_BIN="$WS/install/legged_rl_deploy/lib/legged_rl_deploy/legged_rl_deploy_node"
SIM_CFG="$WS/src/unitree_mujoco/simulate/config.yaml"
DISTRO=${SIM_ROS_DISTRO:-${ROS_DISTRO:-humble}}
for f in "/opt/ros/$DISTRO/setup.bash" "$WS/install/setup.bash" "$SIM_BIN" "$NODE_BIN" "$SIM_CFG"; do
  [[ -e $f ]] || { echo "missing: $f (WORKSPACE=$WS; build the workspace first, see README)" >&2; exit 1; }
done
if grep -Eq '^\s*use_joystick:\s*1' "$SIM_CFG"; then
  echo "set 'use_joystick: 0' in $SIM_CFG for a scripted run (the driver replaces the gamepad)" >&2
  exit 1
fi

CFG=$(realpath "$1")
PROFILE=$(realpath "${2:-$HERE/profiles/demo_final.yaml}")
[[ -f $CFG ]] || { echo "config not found: $1" >&2; exit 1; }
[[ -f $PROFILE ]] || { echo "profile not found: ${2:-}" >&2; exit 1; }
if [[ -n ${3:-} ]]; then
  OUT_ARG=$3
else
  name=${CFG#*/policies/}
  [[ $name == "$CFG" ]] && name=$(basename "$CFG" .yaml) || name=$(dirname "$name")
  OUT_ARG="$WS/sim_results/${name//\//_}_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "$OUT_ARG"
OUT=$(realpath "$OUT_ARG")
LOGS="$OUT/logs"
mkdir -p "$LOGS"
: > "$LOGS/run.log"
rm -f "$OUT"/{data.csv,recording.npz,sportmodestate.csv,lowstate.csv,lowcmd.csv,wirelesscontroller.csv} \
  "$OUT"/{driver_plan.json,driver_events.csv,driver_result.json,summary.json,summary.md}

DOMAIN=${SIM_DOMAIN:-0}
SCENE=${SIM_SCENE:-scene.xml}
SETTLE=${SIM_SETTLE:-2.0}
XVFB_SCREEN=${SIM_XVFB_SCREEN:-1024x768x24}
OWNER=$(stat -c %u:%g "$WS")

log() { echo "[run $(date +%H:%M:%S)] $*" | tee -a "$LOGS/run.log"; }

# one run at a time: the deploy CSV path ($WORKSPACE/plot/data/data.csv) is global
mkdir -p "$WS/plot/data"
exec 9> "$WS/plot/.sim_deploy.lock"
flock -n 9 || { echo "another run_mujoco_deploy.sh is active (lock $WS/plot/.sim_deploy.lock)" >&2; exit 1; }

# ROS 2 / DDS environment (= unitree_lowlevel/scripts/setup.sh lo <distro>, without its
# 'sudo ip link set dev lo multicast on': unicast discovery via cyclonedds_lo.xml instead)
set +u
source "/opt/ros/$DISTRO/setup.bash"
source "$WS/install/setup.bash"
export WORKSPACE="$WS/"   # trailing slash: the sim logger concatenates WORKSPACE + "plot/..."
export NetworkInterface=lo ROS_DOMAIN_ID=$DOMAIN RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="file://$HERE/cyclonedds_lo.xml"
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1  # no root-owned __pycache__ in the repo

PIDS=()
XVFB_PID=""
cleanup() {
  local p
  for p in "${PIDS[@]}"; do kill -INT "$p" 2>/dev/null; done
  sleep 1
  for p in "${PIDS[@]}"; do kill -KILL "$p" 2>/dev/null; done
  [[ -n $XVFB_PID ]] && kill "$XVFB_PID" 2>/dev/null
  chown -R "$OWNER" "$OUT" "$WS/plot" 2>/dev/null
}
trap cleanup EXIT

# stop a process with SIGINT, wait up to $2 s, then SIGKILL
stop_proc() {
  local pid=$1 timeout=$2 name=$3 i
  kill -INT "$pid" 2>/dev/null
  for ((i = 0; i < timeout * 10; i++)); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "$pid" 2>/dev/null; then
    log "$name did not exit after SIGINT in ${timeout}s -> SIGKILL"
    kill -KILL "$pid" 2>/dev/null
  fi
  wait "$pid" 2>/dev/null
  log "$name exited (status $?)"
  local keep=() q
  for q in "${PIDS[@]}"; do [[ $q == "$pid" ]] || keep+=("$q"); done
  PIDS=("${keep[@]}")
}

# legged_rl_deploy_node: SIGINT -> spin returns -> CsvLogger::save() prints its message after
# file.close(). The process sometimes hangs in teardown after that; then it is SIGKILLed 5 s
# after the save message (the CSV is complete at that point).
stop_deploy() {
  local pid=$1 i saved_at=""
  kill -INT "$pid" 2>/dev/null
  for ((i = 0; i < 1200; i++)); do
    kill -0 "$pid" 2>/dev/null || break
    if [[ -z $saved_at ]] && grep -q "数据成功保存到" "$LOGS/deploy.log"; then saved_at=$i; fi
    if [[ -n $saved_at ]] && ((i - saved_at >= 50)); then
      log "legged_rl_deploy_node hung after saving its CSV -> SIGKILL"
      kill -KILL "$pid" 2>/dev/null
      break
    fi
    sleep 0.1
  done
  kill -0 "$pid" 2>/dev/null && { log "legged_rl_deploy_node: no exit/CSV after 120 s -> SIGKILL"; kill -KILL "$pid"; }
  wait "$pid" 2>/dev/null
  log "legged_rl_deploy_node exited (status $?)"
  local keep=() q
  for q in "${PIDS[@]}"; do [[ $q == "$pid" ]] || keep+=("$q"); done
  PIDS=("${keep[@]}")
}

# wait until a command succeeds (timeout s); fail if the watched pid died
wait_for() {
  local timeout=$1 pid=$2 desc=$3; shift 3
  local i
  for ((i = 0; i < timeout * 10; i++)); do
    "$@" && return 0
    kill -0 "$pid" 2>/dev/null || { log "FAIL: process for '$desc' died"; return 1; }
    sleep 0.1
  done
  log "FAIL: timeout (${timeout}s) waiting for $desc"
  return 1
}

log "config  $CFG"
log "profile $PROFILE"
log "out     $OUT"
log "lo: $(ip -o link show lo 2>/dev/null | grep -o '<[^>]*>')"
# the model file (first model_path, relative to $WORKSPACE)
MODEL=$(grep -m1 -E '^\s*model_path:' "$CFG" | sed -E 's/^\s*model_path:\s*//; s/\s*#.*$//')
MODEL_SHA=$( (cd "$WS" && sha256sum "$MODEL" 2>/dev/null) | cut -d' ' -f1)
{
  echo "{"
  echo "  \"config\": \"$CFG\", \"profile\": \"$PROFILE\", \"started\": \"$(date -Iseconds)\","
  echo "  \"model_path\": \"$MODEL\", \"model_sha256\": \"$MODEL_SHA\","
  echo "  \"legged_rl_deploy_head\": \"$(git -c safe.directory='*' -C "$HERE" rev-parse --short HEAD 2>/dev/null)\","
  echo "  \"legged_rl_deploy_dirty_files\": $(git --no-optional-locks -c safe.directory='*' -C "$HERE" status --porcelain 2>/dev/null | wc -l),"
  echo "  \"domain\": $DOMAIN, \"scene\": \"$SCENE\", \"display\": \"${SIM_DISPLAY:-xvfb}\""
  echo "}"
} > "$OUT/run_info.json"

# ---- display
if [[ -n ${SIM_DISPLAY:-} ]]; then
  export DISPLAY=$SIM_DISPLAY
else
  if ! command -v Xvfb > /dev/null; then  # apt packages are lost when the container is recreated
    log "Xvfb missing -> apt-get install xvfb"
    (apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends xvfb) \
      > "$LOGS/apt_xvfb.log" 2>&1 || { log "FAIL: cannot install Xvfb (install it, or set SIM_DISPLAY)"; exit 1; }
  fi
  for n in $(seq 90 119); do
    [[ -e /tmp/.X11-unix/X$n || -e /tmp/.X$n-lock ]] || { DNUM=$n; break; }
  done
  Xvfb ":$DNUM" -screen 0 "$XVFB_SCREEN" -nolisten tcp > "$LOGS/xvfb.log" 2>&1 &
  XVFB_PID=$!
  export DISPLAY=":$DNUM"
  wait_for 10 "$XVFB_PID" "Xvfb :$DNUM" test -e "/tmp/.X11-unix/X$DNUM" || exit 1
  log "Xvfb on $DISPLAY (pid $XVFB_PID)"
fi

# ---- simulator
rm -f "$WS/plot/data/data.csv"
(cd "$(dirname "$SIM_BIN")" && exec "$SIM_BIN" -i "$DOMAIN" -n lo -r go2 -s "$SCENE") \
  > "$LOGS/sim.log" 2>&1 < /dev/null &
SIM_PID=$!
PIDS+=("$SIM_PID")
log "unitree_mujoco pid $SIM_PID (DISPLAY $DISPLAY)"

# ---- recorder
rm -f "$LOGS/recorder.ready"
python3 "$HERE/recorder.py" --out-dir "$OUT" --ready-file "$LOGS/recorder.ready" \
  > "$LOGS/recorder.log" 2>&1 < /dev/null &
REC_PID=$!
PIDS+=("$REC_PID")
wait_for 40 "$REC_PID" "first /lowstate" test -s "$LOGS/recorder.ready" || exit 1
kill -0 "$SIM_PID" 2>/dev/null || { log "FAIL: simulator died"; exit 1; }
log "/lowstate flowing; settling ${SETTLE}s"
sleep "$SETTLE"

# ---- deploy node (model_path and llc_config_file are relative to $WORKSPACE)
(cd "$WS" && exec "$NODE_BIN" lo "$CFG") > "$LOGS/deploy.log" 2>&1 < /dev/null &
NODE_PID=$!
PIDS+=("$NODE_PID")
wait_for 60 "$NODE_PID" "deploy 'init done'" grep -q "\[LeggedRLDeploy\] init done." "$LOGS/deploy.log" \
  || { tail -20 "$LOGS/deploy.log"; exit 1; }
log "legged_rl_deploy_node pid $NODE_PID: init done"

# ---- gamepad driver (foreground)
# shellcheck disable=SC2086
python3 "$HERE/gamepad_driver.py" --config "$CFG" --profile "$PROFILE" --out-dir "$OUT" \
  ${DRIVER_ARGS:-} 2>&1 < /dev/null | tee "$LOGS/driver.log"
DRIVER_RC=${PIPESTATUS[0]}
log "driver exit $DRIVER_RC"

# ---- shutdown: deploy first (its CSV is written after spin returns)
stop_deploy "$NODE_PID"
stop_proc "$REC_PID" 60 recorder
stop_proc "$SIM_PID" 20 unitree_mujoco
if [[ -n $XVFB_PID ]]; then kill "$XVFB_PID" 2>/dev/null; wait "$XVFB_PID" 2>/dev/null; XVFB_PID=""; fi

if [[ -s $WS/plot/data/data.csv ]]; then
  cp "$WS/plot/data/data.csv" "$OUT/data.csv"
  log "deploy CSV -> $OUT/data.csv ($(du -h "$OUT/data.csv" | cut -f1))"
else
  log "WARN: no deploy CSV at $WS/plot/data/data.csv"
fi
N_NAN=$(grep -c "NaN/Inf" "$LOGS/deploy.log")
[[ $N_NAN -gt 0 ]] && log "WARN: $N_NAN NaN/Inf policy outputs (previous output kept)"

python3 "$HERE/analyze.py" "$OUT" --settle "${ANALYZE_SETTLE:-1.0}" > "$LOGS/analyze.log" 2>&1 \
  && cat "$OUT/summary.md" || { log "analyze.py failed:"; tail -20 "$LOGS/analyze.log"; }
log "done (driver rc $DRIVER_RC)"
exit "$DRIVER_RC"
