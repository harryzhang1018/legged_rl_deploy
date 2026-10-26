# Go2 velocity: NRDLab base policy (rl_sar `robot_lab` Go2)

This is the Go2 base policy of the NRDLab Go2 study, before any fine-tuning. It is the rl_sar `robot_lab` Go2 policy, trained in robot_lab v2.1.
NeDM Study 4 fine-tunes this policy on CRM soil. For its fine-tuned versions, see [`../../nrdlab_finetuned/velocity`](../../nrdlab_finetuned/velocity/README.md).
How to run it in MuJoCo: see "Simulation: Go2 velocity policies" in the [root README](../../../../README.md).

| File | Content |
|---|---|
| `config.yaml` | Single-policy deploy config |
| `LICENSE` | Apache-2.0 text from rl_sar at `afacc139`. It applies to `policy.onnx` |
| `policy.onnx` | ONNX conversion (opset 17) of rl_sar `policy/go2/robot_lab/policy.pt`: same weights, same function. Input `obs` [1, 45], output `action` [1, 12]. sha256 `8e9956b35d96461fbe78f41f9eb13545e2a9529fac9bb44863e2edff83cbf2cc` |

## Source and license

- Source: [fan-ziqi/rl_sar](https://github.com/fan-ziqi/rl_sar) at commit `afacc139b8963ccd3a6c4357ab27d8775e913a30`, file `policy/go2/robot_lab/policy.pt`. The sha256 of `policy.pt` is `9f14cb95e74ac9e5e30954da0fc0c33eaa41e337852ebed19fcee869279ade0b`. This is the same file as NRDLab's `BASE_POLICY_SHA256`.
- License: Apache-2.0 ([LICENSE](LICENSE), copied from rl_sar at `afacc139`), Copyright (c) 2024-2025 Ziqi Fan. `policy.onnx` is a format conversion of that file.
- Training: [robot_lab](https://github.com/fan-ziqi/robot_lab) v2.1 (`8b447f2c`). Command ranges vx, vy, wz [-1, 1]. A curriculum can widen vx and vy up to ±1.5; how far it went for this policy is unknown.

## Contract (rl_sar `robot_lab` Go2 config, NRDLab `tasks/go2/{policy.py, mdp.py}`)

| Item | Value |
|---|---|
| Timing | `ll_dt` 0.005 s, `policy_dt` 0.02 s (decimation 4) |
| Joint order | Policy order = motor order FR, FL, RR, RL (`joint_ids_map` identity) |
| Gains | kp 20, kd 0.5, all joints |
| `tau_max` | 23.7 / 23.7 / 45.43 N m (URDF efforts, as NRDLab) |
| Action | `target = clip(raw, ±100) * (0.125, 0.25, 0.25) + (0, 0.8, -1.5)` (hip / thigh / calf) |
| Command | Clipped to the trained range [-1, 1] on vx, vy, wz. No scale |
| Observation (45) | `base_ang_vel_B` x 0.25 (3), `projected_gravity` (3), `velocity_commands` x 1 (3), `joint_pos` - (0, 0.8, -1.5) (12), `joint_vel` x 0.05 (12), `last_action` (12). Each term is clipped to ±100 |

It needs no C++ change: all its observation terms already exist in `PolicySlot`. Another policy with this contract runs with this config: change `model_path`. The NeDM Study 4 fine-tunes do this (`../../nrdlab_finetuned/velocity`).

## Check in unitree_mujoco (2026-10-22)

`legged_rl_deploy_node` with `config.yaml` in `unitree_mujoco` (`go2/scene.xml`, MuJoCo 3.3.6) walked a 31 s scripted gamepad sequence in 2 runs with no fall: stand 2 s; vx 0.5, then 0.8 (4 s each); vy +0.5, then -0.5; wz +0.8, then -0.8; vx -0.5 (3 s each); vx 0.6 with wz 0.6 (4 s); stop 2 s. The real-time factor was 1.0, and the deploy loop ran at 200 Hz. The policy reached 0.79 to 1.00 of the commanded speed on the commanded axis. It turns slowly to the left with a zero command (about 0.08 rad/s).
