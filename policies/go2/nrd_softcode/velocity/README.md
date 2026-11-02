# Go2 velocity: NRD pessimistic soil-code candidate

`xsc_XSb_m175` starts from the repository's `unitree_rl_mjlab` actor and fine-tunes
it with PPO inside NRD, shifting the training ground code toward soft soil
(`soft_shift`, power 3, probability 1; recipe XSb, seed 2, iteration 175).
This is a terrain-bias ablation. Its pooled CRM gains do not imply gains on each
soil: earlier screening found worse medium/firm forward tracking.

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

ONNX SHA256: `5d4d546175d852e706a9bc762ea09c0df5cd85e8549b5c619fb8c1ba6bfe4c72`.

## Check in unitree_mujoco (2026-11-02)

This actor and `unitree_rl_mjlab` ran through the real C++ deploy stack on flat
`go2/scene.xml` ground using `scripts/sim_deploy`: one `demo_final` run (31 s)
and one `stress` run (30 s) per policy. Both policies completed both profiles
without a fall; real-time factors were approximately 1.0.

| Policy | MAE vx / vy / wz, demo | MAE vx / vy / wz, stress | Peak torque hip / thigh / calf, stress [N m] | Power demo / stress [W] |
|---|---|---|---|---|
| `unitree_rl_mjlab` | 0.083 / 0.060 / 0.125 | 0.096 / 0.073 / 0.143 | 8.1 / 17.9 / 27.5 | 18.5 / 29.7 |
| `nrd_softcode` | 0.085 / 0.061 / 0.122 | 0.099 / 0.069 / 0.146 | 7.5 / 17.3 / 26.5 | 18.3 / 29.4 |

MAE is mean absolute tracking error (vx/vy in m/s, wz in rad/s), excluding the
first second of each segment; lower is better. Results are mixed: forward MAE increases by about 2% on both profiles, while lateral and yaw changes depend on the profile.

Reproduce with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-candidates).
One repeat per profile is a deployment check, not a statistically reliable ranking
or hardware validation. The earlier CRM screen is a separate simulation protocol.
