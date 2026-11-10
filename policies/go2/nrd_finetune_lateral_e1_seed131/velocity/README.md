# Go2 velocity: NRD lateral finetune E1, seed 131 (EXPERIMENTAL)

**Status: experimental simulation candidate. Chrono label NOT_CONFIRMED. Not tested on hardware.**

PPO seed 131, iteration 299, initialized from the unchanged `unitree_rl_mjlab` actor and optimized inside a frozen
ensemble of four three-transformer NRDs (core/collision/contact) of `nrd_v3`: FRESH-b, NOSTALL-b, FRESH-c and
FRESH-d. At each 4 s training branch, each environment uses one member drawn at random (model randomization). The
member-disagreement term was logged only (weight 0). The rewards, starts and commands are recipe V2 of study
`lateral_stuck_20261108`, unchanged; the only difference from
[`nrd_finetune_lateral_v2n_seed81`](../../nrd_finetune_lateral_v2n_seed81/velocity/README.md) is the ensemble of
dynamics models in place of FRESH-b alone (and the PPO seed). All four NRDs were trained on the same data, and they and their fitted
normalizers use only trajectories collected by the original fixed teacher, including the study's 2.22 h of added
lateral CRM data (uneven beds, softer soil, long slow lateral holds, foot-lift excitations). No
fine-tuned-policy trajectories were used. Direct physics was used for evaluation, not actor optimization.

Goal: fix the lateral foot-drag stall seen on the real robot. On sand the teacher steps only about 1.8 cm sideways per
step (10.2 cm on rigid ground), at a fixed 1.67 Hz gait clock, so its feet land in their own craters and it stalls.
This actor takes longer sideways strides.

The deployment contract matches [`unitree_rl_mjlab`](../../unitree_rl_mjlab/velocity/README.md):
47 observations including gait phase, no stacked actor history, 12 actions, embedded observation normalization,
50 Hz policy and 200 Hz low-level loop. The parsed config changes only `policy.model_path`; joint order/map, gains,
action processing, command clips and `clip_final_tau: false` are inherited unchanged.

| File | Purpose |
|---|---|
| `config.yaml` | Deploy config with model path relative to `$WORKSPACE` |
| `policy.onnx` | Deterministic actor, static `[1,47]` to `[1,12]` |
| `policy_export.json` | Original checkpoint/export metadata and structural checks |
| `parity.json` | Fresh 4,000-row action/observation parity through the deploy-policy mirror |
| `provenance.json` | Actor, fixed teacher, frozen NRD ensemble, recipe, results and sim_deploy SHA256 lineage |

ONNX SHA256: `3ec4301b9f9461d985d742bdee5a2485ae96ed9ea50d85f9bb355d286a792ed8`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `1.91e-06`; deploy-policy mirror versus Torch
max error `6.61e-05`. The larger mirror error includes observation
reconstruction, including phase.

## Chrono CRM lateral evidence (simulation only)

Teacher = the unchanged `unitree_rl_mjlab` actor in the same jobs. Stuck time = failure-penalized lateral STUCK
time (1 s windows with lateral tracking ratio below 0.4; a fall or early stop counts the rest of the hold as stuck).
Realistic cells = medium flat, medium uneven and firm uneven sand, lateral holds at 0.3 to 0.45 m/s.

| Check (fresh suite_v3, 72 realistic episodes) | This policy | Teacher | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio (blocks better, of 9) | **0.185** (9) | 1 | 0.75 or less, 8 of 9 | pass |
| Stuck-time ratio, medium flat / medium uneven / firm uneven | 0.05 / 0.30 / 0.18 | 1 | - | better |
| Stuck-time ratio +y / -y | 0.21 / 0.15 | 1 | 1.0 or less | pass |
| Lateral progress / command, +y / -y | 0.79 / 0.87 | 0.18 / 0.24 | - | better |
| Soft-sand wrong-way segments -y / +y, of 16 | 4 / 0 | 0 / 0 | teacher + 1 | **fail** |
| Realistic early stops, of 72 | 8: 6 falls (5 of 24 medium uneven, 1 firm uneven) + 2 bed exits | 3: 2 falls + 1 bed exit | teacher + 2 | **fail** |
| Power / action-rate ratio | 1.54 / 1.38 | 1 (24.4 W) | 1.25 or less | **fail** |
| Soft-sand stress early stops, of 32 (flag only) | 6 | 15 | - | better |

Same-job comparison with V2n s81 and the teacher (deploy-check jobs, torque clip on, 48 realistic episodes):
stuck-time ratio 0.183 (clip off 0.197; V2n s81 0.197), 2 early stops (2 falls; teacher 2, V2n s81 3), medium-sand
power 1.54 times the teacher. The torque clip changed no result.

The ensemble kept the V2 stuck-time gain and gave a better left/right balance than V2n s81. It did not remove the
medium-uneven roll-overs or the soft -y wrong-way slide: the four members share all their training data, and all
predict almost no falls for this gait. The Chrono falls are real roll-overs in simulation, not false alarms of the
fall rule.

## Rigid MuJoCo development evidence

On the 120-path MuJoCo rigid development suite (paired with the teacher, 10,000 path-bootstrap draws):
failure-penalized tracking loss ratio **0.909** (95 % range 0.887 to 0.931), lateral-path loss ratio 0.57, 0 falls
of 120 (teacher 0). Power is 1.18 times the teacher value (95 % range 1.15 to 1.20), above the prior-study limit of
1.15.

## Limits

- Chrono label NOT_CONFIRMED (gates G2 wrong way, G3 falls, S1 power not satisfied).
- The selection rule picked it at its limits (each count limit passed by 1).
- The suite_v3 row and the V2n s81 suite_v2 row use different beds and teacher jobs; only the deploy-check row above
  is a paired comparison.
- Soil levels are study levels, not measured sand. No physical robot was actuated.
- These are development and held-out simulation suites, not hardware qualification.

Suggested first hardware test (not done): flat medium sand only, lateral 0.3 to 0.45 m/s, with a spotter. Stop if
the tilt exceeds 25 deg for 0.5 s, or if the body leans slowly onto the trailing legs and slides backward.

Study report SHA256 (`FINAL_REPORT.md`):
`5c01a9e7bfe5c2d8158e538e43a5d509e6cf3cc85172d82ec2ac3bc3efcac2a1`.
Detailed research receipts are archived outside Git at
`/home/harry/go2_sand/results/lateral_stuck_20261108_pr_20261109/receipts/`.

## Check in unitree_mujoco (2026-11-09)

The package was renamed on 2026-11-09 from the checked alias `rigidcheck_E1_s131`; ONNX bytes and all control
settings are unchanged from the package checked below.

The exact packaged ONNX and its teacher ran through the existing C++ deploy stack
in MuJoCo on flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress`
(30 s) run per policy. Both completed both profiles with zero falls, zero
non-finite policy outputs and no command-plan warnings; real-time factors were
approximately 1.000. The deployment config and physics settings were identical
apart from the model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.083 / 0.060 / 0.125 | 7.7 / 13.0 / 24.1 | 18.5 | 1.470 | 3.28 |
| E1-131 / demo_final | 0.082 / 0.036 / 0.122 | 8.5 / 15.1 / 24.0 | 21.7 | 1.593 | 5.75 |
| mjlab / stress | 0.097 / 0.073 / 0.144 | 8.2 / 17.4 / 27.7 | 29.7 | 1.742 | 6.34 |
| E1-131 / stress | 0.091 / 0.048 / 0.139 | 7.2 / 18.3 / 26.5 | 33.0 | 1.856 | 7.19 |

MAE improved on all three axes in both profiles: vx / vy / wz -1% / -39% / -2% on demo and -6% / -35% / -4% on
stress. Lateral achieved/commanded on demo: +0.5 m/s 0.76 (teacher 0.53), -0.5 m/s 0.85 (teacher 0.56).
Mean power rose 17.6% on demo and 10.9% on stress; these single-run differences are descriptive.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.

Reproduce both lateral candidates and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-lateral-finetune-candidates).
This is a one-repeat C++ deployment check on rigid ground, not a statistically reliable ranking, a sand test or
hardware validation. No physical robot was actuated.
