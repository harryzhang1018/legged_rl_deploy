# Go2 velocity: NRD combo contact-label candidate

`lco_E2_s1_m200` starts from the repository's `unitree_rl_mjlab` actor and fine-tunes
it with PPO inside the NRD trained with combined contact-label preprocessing
(`lab_combo`, recipe E2, seed 1, iteration 200). Direct Chrono rollouts are used for
data collection and evaluation; this actor was optimized in NRD, without AWR.

The deployment contract matches [`unitree_rl_mjlab`](../../unitree_rl_mjlab/velocity/README.md):
47 observations including gait phase, no stacked history, 12 actions, 50 Hz policy,
200 Hz low-level loop, the same motor map, gains, action scale and command clips.
Only `policy.model_path` differs in the parsed config.

| File | Purpose |
|---|---|
| `config.yaml` | Single-policy deploy config; model path relative to `$WORKSPACE` |
| `policy.onnx` | Self-contained actor with observation normalization |
| `policy_export.json` | Original checkpoint/export identity and numerical checks |
| `parity.json` | Saved recorded-observation action parity checks |
| `provenance.json` | Candidate lineage and exact ONNX SHA256 |

ONNX SHA256: `c29d50eec41ddcdcc6d7340ff7a9b296b5b64e330f891689ad0574e20e4f1566`.

## Check in unitree_mujoco (2026-11-02)

This actor and `unitree_rl_mjlab` ran through the real C++ deploy stack on flat
`go2/scene.xml` ground using `scripts/sim_deploy`: one `demo_final` run (31 s)
and one `stress` run (30 s) per policy. Both policies completed both profiles
without a fall; real-time factors were approximately 1.0.

| Policy | MAE vx / vy / wz, demo | MAE vx / vy / wz, stress | Peak torque hip / thigh / calf, stress [N m] | Power demo / stress [W] |
|---|---|---|---|---|
| `unitree_rl_mjlab` | 0.083 / 0.060 / 0.125 | 0.096 / 0.073 / 0.143 | 8.1 / 17.9 / 27.5 | 18.5 / 29.7 |
| `nrd_combo` | 0.078 / 0.058 / 0.121 | 0.084 / 0.071 / 0.136 | 7.5 / 17.2 / 26.2 | 19.3 / 30.9 |

MAE is mean absolute tracking error (vx/vy in m/s, wz in rad/s), excluding the
first second of each segment; lower is better. Tracking MAE decreases on all three axes in both profiles, with about 4% higher mechanical power.

Reproduce with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-candidates).
One repeat per profile is a deployment check, not a statistically reliable ranking
or hardware validation. The earlier CRM screen is a separate simulation protocol.
