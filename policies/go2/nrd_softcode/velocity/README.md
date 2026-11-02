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

See [evaluation and reproduction](../../../../reports/nrd_candidates_20261102/README.md)
for the real C++ deploy-stack MuJoCo runs and the earlier CRM development screen.
This is a simulation candidate, with no hardware validation.
