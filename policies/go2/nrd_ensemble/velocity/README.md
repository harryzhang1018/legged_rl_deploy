# Go2 velocity: NRD uncertainty-ensemble candidate

`xeS5abc_m175` starts from the repository's `unitree_rl_mjlab` actor and fine-tunes
it with PPO inside a five-member NRD ensemble. Recipe XS5abc samples an NRD member
per environment, penalizes ensemble disagreement (weight 0.18), and uses pessimistic
shadow falls. This is seed 2, iteration 175. The deployed actor is one feedforward
network; the dynamics ensemble is used during training, not deployment.

The deployment contract matches [`unitree_rl_mjlab`](../../unitree_rl_mjlab/velocity/README.md):
47 observations including gait phase, no stacked history, 12 actions, 50 Hz policy,
200 Hz low-level loop, the same motor map, gains, action scale and command clips.
Only `policy.model_path` differs in the parsed config. The actor was optimized in
NRD, without direct-Chrono AWR actor updates.

| File | Purpose |
|---|---|
| `config.yaml` | Single-policy deploy config; model path relative to `$WORKSPACE` |
| `policy.onnx` | Self-contained actor with observation normalization |
| `policy_export.json` | Original checkpoint/export identity and numerical checks |
| `parity.json` | Saved recorded-observation action parity checks |
| `provenance.json` | Candidate lineage and exact ONNX SHA256 |

ONNX SHA256: `de957e9e4084dad02530696c7792365e69b0b0752e4ca9b1b8a7bc1d4f2e796e`.

## Check in unitree_mujoco (2026-11-02)

This actor and `unitree_rl_mjlab` ran through the real C++ deploy stack on flat
`go2/scene.xml` ground using `scripts/sim_deploy`: one `demo_final` run (31 s)
and one `stress` run (30 s) per policy. Both policies completed both profiles
without a fall; real-time factors were approximately 1.0.

| Policy | MAE vx / vy / wz, demo | MAE vx / vy / wz, stress | Peak torque hip / thigh / calf, stress [N m] | Power demo / stress [W] |
|---|---|---|---|---|
| `unitree_rl_mjlab` | 0.083 / 0.060 / 0.125 | 0.096 / 0.073 / 0.143 | 8.1 / 17.9 / 27.5 | 18.5 / 29.7 |
| `nrd_ensemble` | 0.079 / 0.062 / 0.119 | 0.093 / 0.072 / 0.140 | 7.0 / 18.6 / 26.3 | 18.0 / 29.2 |

MAE is mean absolute tracking error (vx/vy in m/s, wz in rad/s), excluding the
first second of each segment; lower is better. Forward and yaw MAE decrease in both profiles and mechanical power is lower; demo lateral MAE increases slightly.

Reproduce with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-candidates).
One repeat per profile is a deployment check, not a statistically reliable ranking
or hardware validation. The earlier CRM screen is a separate simulation protocol.
