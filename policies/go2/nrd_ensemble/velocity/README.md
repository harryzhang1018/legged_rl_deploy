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

See [evaluation and reproduction](../../../../reports/nrd_candidates_20261102/README.md)
for the real C++ deploy-stack MuJoCo runs and the earlier CRM development screen.
This is a simulation candidate, with no hardware validation.
