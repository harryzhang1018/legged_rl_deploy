#!/usr/bin/env bash
# One command: run Go2 velocity policies in unitree_mujoco and compare them.
#
#   eval_go2_velocity.sh [-o out_dir] [-n repeats] [-p profile.yaml]... [label=config.yaml ...]
#
# With no label=config.yaml arguments it runs these Go2 velocity policies of policies/go2/:
#   unitree_rl_mjlab   unitree_rl_mjlab/velocity/config.yaml
#   nrdlab_base        nrdlab_base/velocity/config.yaml
#   nrdlab_finetuned   nrdlab_finetuned/velocity/config.yaml
# Default profiles: profiles/demo_final.yaml and profiles/stress.yaml; default repeats: 1.
# -p takes a path, or a name in profiles/ (e.g. -p smoke).
# Each run is run_mujoco_deploy.sh (same environment overrides, same requirements); the
# result is <out_dir>/<label>/<profile>_r<k>/ and the table <out_dir>/compare.md (compare.py,
# MAE change relative to the first label).
# Default out_dir: $WORKSPACE/sim_results/go2_velocity_<date>. One run takes about 50 s.
# The console output of each run is <out_dir>/<label>/<profile>_r<k>.log.
# Exit code: 0 if every run finished without a fall and compare.md was written, else 1.
set -o pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POL="$(cd "$HERE/../../policies/go2" && pwd)"
WS=${WORKSPACE:-$(cd "$HERE/../../../.." && pwd)}
WS=${WS%/}

OUT="" REPEATS=1 PROFILES=()
while getopts "o:n:p:h" opt; do
  case $opt in
    o) OUT=$OPTARG ;;
    n) REPEATS=$OPTARG ;;
    p)
      f=$OPTARG
      [[ -f $f ]] || f=$HERE/profiles/$OPTARG
      [[ -f $f ]] || f=$HERE/profiles/$OPTARG.yaml
      [[ -f $f ]] || { echo "profile not found: $OPTARG" >&2; exit 1; }
      PROFILES+=("$(realpath "$f")")
      ;;
    *) sed -n '2,20p' "$0"; exit 1 ;;
  esac
done
shift $((OPTIND - 1))
[[ ${#PROFILES[@]} -gt 0 ]] || PROFILES=("$HERE/profiles/demo_final.yaml" "$HERE/profiles/stress.yaml")
OUT=${OUT:-$WS/sim_results/go2_velocity_$(date +%Y%m%d_%H%M%S)}

LABELS=() CONFIGS=()
if [[ $# -eq 0 ]]; then
  LABELS=(unitree_rl_mjlab nrdlab_base nrdlab_finetuned)
  CONFIGS=("$POL/unitree_rl_mjlab/velocity/config.yaml" "$POL/nrdlab_base/velocity/config.yaml"
           "$POL/nrdlab_finetuned/velocity/config.yaml")
else
  for a in "$@"; do
    [[ $a == *=* ]] || { echo "expected label=config.yaml, got '$a'" >&2; exit 1; }
    c=$(realpath -e "${a#*=}") || { echo "config not found: ${a#*=}" >&2; exit 1; }
    LABELS+=("${a%%=*}") CONFIGS+=("$c")
  done
fi

# the container runs as root: give the results to the workspace owner at exit
OWNER=$(stat -c %u:%g "$WS")
[[ -d $WS/sim_results ]] || NEW_PARENT=1
mkdir -p "$OUT"
trap 'chown -R "$OWNER" "$OUT" 2>/dev/null; [[ -n ${NEW_PARENT:-} ]] && chown "$OWNER" "$WS/sim_results" 2>/dev/null' EXIT
echo "eval -> $OUT"
FAILED=0
for ((i = 0; i < ${#LABELS[@]}; i++)); do
  for prof in "${PROFILES[@]}"; do
    for ((k = 1; k <= REPEATS; k++)); do
      run="$OUT/${LABELS[i]}/$(basename "$prof" .yaml)_r$k"
      mkdir -p "$OUT/${LABELS[i]}"
      "$HERE/run_mujoco_deploy.sh" "${CONFIGS[i]}" "$prof" "$run" > "$run.log" 2>&1
      rc=$?
      echo "$(date +%H:%M:%S) ${LABELS[i]} $(basename "$prof" .yaml) r$k: rc $rc$( ((rc == 3)) && echo ' (FALL)')"
      ((rc == 0 || rc == 3)) || { echo "  see $run.log:"; tail -n 3 "$run.log" | sed 's/^/    /'; }
      ((rc == 0)) || FAILED=1
    done
  done
done
python3 "$HERE/compare.py" "$OUT" --ref "${LABELS[0]}" || { echo "compare.py failed: no compare.md" >&2; FAILED=1; }
exit $FAILED
