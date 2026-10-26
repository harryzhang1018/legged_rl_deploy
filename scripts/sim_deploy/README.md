# sim_deploy: scripted policy evaluation in unitree_mujoco

These scripts run the real deploy stack (`legged_rl_deploy_node` on `unitree_lowlevel`) in `unitree_mujoco` with no person and no gamepad.
A scripted gamepad (`gamepad_driver.py`) does the FSM steps and sends the commands of a profile. A recorder logs the simulator's ground truth.
`compare.py` puts the policies side by side.

## One command

Run it in the workspace's container (`docker exec -it unitree_ws bash`) or a native install, from the workspace root:

```bash
./src/legged_rl_deploy/scripts/sim_deploy/eval_go2_velocity.sh
```

It runs three Go2 velocity policies on two profiles, then writes `compare.md`:
- `unitree_rl_mjlab`
- `nrdlab_base`
- `nrdlab_finetuned`, if you got it with `policies/go2/nrdlab_finetuned/velocity/get_policy.py`

One run takes about 50 s. To run another config, for example `policies/go2/mjlab/velocity`, give it as `label=<config.yaml>`.

| Option | Meaning |
|---|---|
| `-n 2` | Repeat each run (default 1) |
| `-p <profile>` | Profile: a path, or a name in `profiles/` (`-p smoke`). Repeat the option for more profiles (default `demo_final` and `stress`) |
| `-o <dir>` | Output folder (default `$WORKSPACE/sim_results/go2_velocity_<date>`) |
| `label=<config.yaml> ...` | Run these configs instead. The first label is the reference for the MAE change |

One config, one profile: `run_mujoco_deploy.sh <config.yaml> [profile.yaml] [out_dir]`.

## Before the first run

1. Build the workspace with `unitree_mujoco`. See "Simulation: Go2 velocity policies" in the [root README](../../README.md).
2. Set `use_joystick: 0` in `src/unitree_mujoco/simulate/config.yaml`. The scripted gamepad then is the only gamepad. Set it back to `1` to drive with a real gamepad.
3. Xvfb: the script installs it with apt if it is missing (root, network). To watch the robot, set `SIM_DISPLAY=$DISPLAY`. Then the simulator opens on your display, not in a private Xvfb.

The script does not change the host network. `unitree_lowlevel/scripts/setup.sh` runs `sudo ip link set dev lo multicast on`. These scripts do not. Their DDS config (`cyclonedds_lo.xml`) follows the `lo` MULTICAST flag, as the simulator does: unicast discovery to 127.0.0.1 while the flag is off, multicast discovery while it is on. `logs/run.log` records the `lo` flags of each run.

## Profiles

A profile is a list of segments. Each segment has a duration `t` [s] and a body-frame command `vx`, `vy` [m/s], `wz` [rad/s]. A value that is not given is 0.

| Profile | Content |
|---|---|
| `demo_final.yaml` | 31 s: stand; forward 0.5 and 0.8; lateral ±0.5; turn ±0.8; backward 0.5; forward 0.6 with turn 0.6; stop |
| `stress.yaml` | 30 s: forward 1.0; turn ±1.0; diagonal; forward 1.0 with turn -0.5; lateral with turn; sprint; reversal; stop |
| `smoke.yaml` | 4 s: checks the pipeline only |

The driver inverts the config's `commands.base_velocity` processor and the stick map `v = (ly, -lx, -rx)`.
`unitree_lowlevel` sets each stick to 0 while its value is below 0.5 (dead zone). Thus a command must be 0 or have a magnitude of at least 0.5. The driver changes a command that it cannot send to the nearest value that it can send, and logs a warning. The analysis uses the command that was really sent.

## Outputs

| File | Content |
|---|---|
| `<label>/<profile>_r<k>/` (eval folder) | One run: the files below |
| `<label>/<profile>_r<k>.log` (eval folder) | Console output of that run. Read it when the exit code is 1 or 2 |
| `compare.md` (eval folder) | For each profile: falls, MAE vx / vy / wz, MAE change from the reference, max tilt, peak joint torque, mean mechanical power, joint-target rate; achieved / commanded for each segment |
| `summary.md`, `summary.json` | For each segment: command, mean, std and MAE of body-frame vx, vy (`/sportmodestate`) and wz (gyro); base height; tilt; fall; real-time factor |
| `recording.npz`, `*.csv` | `/sportmodestate`, `/lowstate`, `/lowcmd`, `/wirelesscontroller` with receive times |
| `data.csv` | The deploy node's own CSV log |
| `driver_*.json`, `driver_events.csv` | Stick plan, events, result |
| `run_info.json`, `policy_source.json` | Config, profile, model path and sha256, git HEAD; the fetch record of a fine-tuned policy |
| `logs/` | Logs of each process |

Exit codes of `run_mujoco_deploy.sh`: 0 success, 1 setup failure (or another run is active), 2 failed FSM transition or timeout, 3 fall (base z < 0.15 m or tilt > 60°).

## Limits

- The scripted runs were tested with the `lo` MULTICAST flag off (the default). With the flag on, both DDS sides use multicast discovery, as in the gamepad flow.
- Only one run at a time. The deploy CSV path `$WORKSPACE/plot/data/data.csv` is global, so the script uses a lock.
- `legged_rl_deploy_node` sometimes hangs after it saves its CSV at shutdown. The script then stops it with SIGKILL. The CSV is complete at that time.
- Velocities are those of the `base_link` origin, rotated into the body frame. They are not the COM velocity.
- A MuJoCo result is not a hardware result. It finds contract errors (joint order, gains, observation scales) and large sim-to-sim gaps before you go to the robot.
