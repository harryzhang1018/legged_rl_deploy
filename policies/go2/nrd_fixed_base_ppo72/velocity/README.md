# Go2 velocity: fixed-base NRD PPO72

PPO seed 72, iteration 299, initialized from the unchanged `unitree_rl_mjlab`
actor and optimized inside a frozen three-transformer NRD (core/collision/contact,
NRD seed 61, H50 checkpoint LAST13500). H50 means a 1 s supervised dynamics-loss
horizon; PPO used 2 s branches. The NRD and its fitted normalizers use only
trajectories collected by that original fixed teacher: matched rigid + CRM TRAIN,
5.3523917 h total. No fine-tuned-policy trajectories or descendant normalization
were used. Direct physics was used for evaluation, not actor optimization.

The deployment contract matches [`unitree_rl_mjlab`](../../unitree_rl_mjlab/velocity/README.md):
47 observations including gait phase, no stacked actor history, 12 actions, embedded
observation normalization, 50 Hz policy and 200 Hz low-level loop. The parsed config
changes only `policy.model_path`; joint order/map, gains, action processing, command
clips and `clip_final_tau: false` are inherited unchanged.

| File | Purpose |
|---|---|
| `config.yaml` | Deploy config with model path relative to `$WORKSPACE` |
| `policy.onnx` | Deterministic actor, static `[1,47]` to `[1,12]` |
| `policy_export.json` | Original checkpoint/export metadata and structural checks |
| `parity.json` | Fresh 4,000-row action/observation parity through the deploy-policy mirror |
| `provenance.json` | Actor, fixed teacher, frozen NRD, split and configuration SHA256 lineage |

ONNX SHA256: `9bc189ec0a1bc5c1d795a93cbe4bfb7aa84627d924987f95c9e939e7e6ea618b`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `2.15e-06`; deploy-policy mirror versus Torch
max error `6.36e-05`. The larger mirror error includes observation
reconstruction, including phase.

## Independent physics development evidence

Against the same original teacher: **9.41%** lower failure-penalized tracking loss
on 120 MuJoCo rigid cases, **9.32%** on 10 Chrono soft-soil cases, and **14.00%**
on 10 Chrono firm-soil cases; zero observed falls in these 140 candidate episodes.
These percentages are loss reductions, not accuracy. Aggregate tracking improved,
but rigid vy MAE increased 4.05%. Baseline and candidate used the same actual binary,
hardware and settings within each comparison. CRM used matched torqueClip-off
physics; torqueClip-on transfer is not established.

These are reused development cases, not a sealed final test. Zero observed falls
on this small CRM sample does not establish safety. This candidate shares the
same NRD seed as PPO71; it is a PPO-seed repeat, not an independent NRD
replication. Another NRD seed produced a failing soft-soil PPO replica. Final-v3
remains sealed. Neither architecture convergence nor hardware performance is claimed.

Source report SHA256:
`5a9d563bd259e224924b64480d907dc199d9601227083debc91c4dc1fef695a6`.
Detailed research receipts and deployment evidence are archived outside Git at
`/home/harry/go2_sand/results/fixed_base_20261103_policy_release_v1/`.

## Check in unitree_mujoco (2026-11-03)

The exact packaged ONNX and its teacher ran through the existing C++ deploy stack
in MuJoCo 3.3.6 on flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress`
(30 s) run per policy. Both completed both profiles with zero falls, zero
non-finite policy outputs and no command-plan warnings; real-time factors were
approximately 1.000. The deployment config and physics settings were identical
apart from the model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.082 / 0.060 / 0.124 | 7.7 / 13.2 / 24.3 | 18.6 | 1.472 | 3.31 |
| PPO72 / demo_final | 0.078 / 0.060 / 0.115 | 6.8 / 13.2 / 24.4 | 19.0 | 1.462 | 2.81 |
| mjlab / stress | 0.096 / 0.072 / 0.144 | 8.5 / 17.5 / 27.8 | 30.1 | 1.756 | 6.25 |
| PPO72 / stress | 0.091 / 0.073 / 0.131 | 7.3 / 18.0 / 26.3 | 30.9 | 1.757 | 5.66 |

Forward and yaw MAE improved in both profiles. Lateral MAE rose 1.25% on demo and 0.83% on stress.
Mean power rose 2.40% on demo and 2.66% on stress; these
single-run differences are descriptive.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.


Reproduce both candidates and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#fixed-base-nrd-candidates).
This is a one-repeat C++ deployment check, not a statistically reliable ranking or
hardware validation. No physical robot was actuated.
