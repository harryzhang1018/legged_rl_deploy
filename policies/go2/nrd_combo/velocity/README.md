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

See [evaluation and reproduction](../../../../reports/nrd_candidates_20261102/README.md)
for the real C++ deploy-stack MuJoCo runs and the earlier CRM development screen.
This is a simulation candidate, with no hardware validation.
