# Go2 velocity: unitree_rl_mjlab `Unitree-Go2-Flat`

A Go2 flat-ground velocity policy, trained with [unitree_rl_mjlab](https://github.com/unitreerobotics/unitree_rl_mjlab).
How to run it in MuJoCo: see "Simulation: Go2 velocity policies" in the [root README](../../../../README.md).

| File | Content |
|---|---|
| `config.yaml` | Single-policy deploy config |
| `policy.onnx` | Actor exported by mjlab at the final save. The observation normalizer is inside the model. Input `obs` [1, 47], output `actions` [1, 12]. sha256 `c58a3494b22604b5aa67640ec6ebabe0c6c277d85b072dc9e76c3191e2dfdd45` |

## Training

| Item | Value |
|---|---|
| Repo | unitree_rl_mjlab `1425b15` (mjlab 1.2.0, rsl_rl_lib 5.0.1) |
| Command | `python scripts/train.py Unitree-Go2-Flat --env.scene.num-envs=4096 --agent.logger=wandb --agent.wandb-project=unitree_rl_mjlab --agent.run-name=Unitree-Go2-Flat` |
| Run | `2026-10-22_02-14-16_Unitree-Go2-Flat`, 10001 iterations, seed 42, 1 x A100, about 2 h 50 min |
| Checkpoint | `model_10000.pt` (final) |
| Command ranges | vx [-0.5, 1], vy [-0.5, 0.5], wz [-1, 1] until iteration 5000; then vx [-1, 2], vy [-1, 1], wz [-1, 1] |

## Contract

| Item | Value |
|---|---|
| Timing | `ll_dt` 0.005 s, `policy_dt` 0.02 s (decimation 4, as in training) |
| Joint order | Policy order FL, FR, RL, RR. `joint_ids_map` maps it to the motor order FR, FL, RR, RL |
| Gains | kp 20 / 20 / 40, kd 1 / 1 / 2 (hip / thigh / calf) |
| `tau_max` | 23.5 / 23.5 / 45 N m (training actuator limits) |
| Action | `target = raw * 0.25 + default`, default (±0.1, 0.9, -1.8), no clip |
| Command | Clipped to Unitree's Go2 `deploy.yaml` ranges: vx [-0.5, 1], vy [-0.5, 0.5], wz [-1, 1]. No scale |
| Observation (47) | `base_ang_vel_B` (3), `projected_gravity` (3), `velocity_commands` (3), `gait_phase` (2), `joint_pos` - default (12), `joint_vel` (12), `last_action` (12). No scale, no clip |
| `gait_phase` | `[sin, cos](2 pi fmod(k * 0.02, 0.6) / 0.6)`. `k` counts the policy steps since START. It is `[0, 0]` while the command norm is below 0.1. This is mjlab's `phase` term with `k = episode_length_buf`. It needs the `gait_phase` term in `src/policy_slot.cpp` |

The deploy does not reproduce these training items: observation noise, pushes, and domain randomization.

## Check in unitree_mujoco (2026-10-22)

`legged_rl_deploy_node` with `config.yaml` in `unitree_mujoco` (`go2/scene.xml`, MuJoCo 3.3.6) walked a 31 s scripted gamepad sequence in 2 runs with no fall: stand 2 s; vx 0.5, then 0.8 (4 s each); vy +0.5, then -0.5; wz +0.8, then -0.8; vx -0.5 (3 s each); vx 0.6 with wz 0.6 (4 s); stop 2 s. The real-time factor was 1.0, and the deploy loop ran at 200 Hz. In this scene the policy is slow: it reached 0.49 to 0.83 of the commanded speed on the commanded axis. Pure turns reached about half of the command.
