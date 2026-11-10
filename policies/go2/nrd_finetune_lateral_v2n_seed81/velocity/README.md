# Go2 velocity: NRD lateral finetune V2n, seed 81 (EXPERIMENTAL)

**Status: experimental simulation candidate. Chrono label NOT_CONFIRMED. Not tested on hardware.**

PPO seed 81, iteration 299, initialized from the unchanged `unitree_rl_mjlab` actor and optimized inside one
frozen three-transformer NRD (core/collision/contact): `nrd_v3` FRESH-b (loader SHA256 `501c9b8d...`), with its
train-only CRM OOD reference. Recipe V2 of study `lateral_stuck_20261108` adds lateral commands, starts from stuck
lateral states, a relaxed action anchor for lateral commands, and swing-peak, foot-drag and lateral-shortfall terms.
The NRD was retrained for this study from scratch (seed 62) with 2.22 h of added lateral data of the original
teacher on Chrono CRM (about 25 % of its training data): uneven beds, softer soil, long slow lateral holds and
foot-lift excitations. The NRD and its fitted normalizers use only trajectories collected by
the original fixed teacher. No fine-tuned-policy trajectories were used. Direct physics was used for evaluation, not
actor optimization.

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
| `provenance.json` | Actor, fixed teacher, frozen NRD, recipe, results and sim_deploy SHA256 lineage |

ONNX SHA256: `1419d9722698c23a04b8805dd15f6eb25710e1f11860ffbad0cb1a63159674e9`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `1.91e-06`; deploy-policy mirror versus Torch
max error `6.26e-05`. The larger mirror error includes observation
reconstruction, including phase.

## Chrono CRM lateral evidence (simulation only)

Teacher = the unchanged `unitree_rl_mjlab` actor in the same jobs. Stuck time = failure-penalized lateral STUCK
time (1 s windows with lateral tracking ratio below 0.4; a fall or early stop counts the rest of the hold as stuck).
Realistic cells = medium flat, medium uneven and firm uneven sand, lateral holds at 0.3 to 0.45 m/s.

| Check (held-out suite_v2, 72 realistic episodes) | This policy | Teacher | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio (blocks better, of 9) | **0.214** (9) | 1 | 0.75 or less, 8 of 9 | pass |
| Stuck-time ratio, medium flat / medium uneven / firm uneven | 0.11 / 0.35 / 0.16 | 1 | - | better |
| Stuck-time ratio +y / -y | 0.31 / 0.11 | 1 | 1.0 or less | pass |
| Lateral progress / command, +y / -y | 0.67 / 0.94 | 0.17 / 0.21 | - | better |
| Soft-sand wrong-way segments -y / +y, of 16 | 8 / 1 | 0 / 0 | teacher + 1 | **fail** |
| Realistic falls, of 72 | 5 (all medium uneven, 5 of 24) | 0 | teacher + 2 | **fail** |
| Power / action-rate ratio | 1.66 / 1.46 | 1 | 1.25 or less | **fail** |
| Soft-sand stress early stops, of 32 (flag only) | 21 | 16 | - | worse |

Same-job comparison with E1 s131 and the teacher (deploy-check jobs, torque clip on, 48 realistic episodes):
stuck-time ratio 0.197 (clip off 0.199), 3 early stops (2 falls, 1 bed exit; teacher 2), medium-sand power 1.56
times the teacher. The torque clip changed no result.

The Chrono falls are roll-overs onto the trailing side while the robot slides backward (32 of 32 fall events), not
false alarms of the fall rule. The teacher's Chrono falls are of another type (toward the commanded side) and occur
almost only on the soft stress soil. Thus the earlier observation that teacher falls in Chrono did not transfer to
the real robot does not transfer to this policy. Chrono predicts about 1 roll-over in 5 episodes of 20 s on medium
uneven sand.

## Rigid MuJoCo development evidence

On the 120-path MuJoCo rigid development suite (paired with the teacher, 10,000 path-bootstrap draws):
failure-penalized tracking loss ratio **0.854** (95 % range 0.836 to 0.874), lateral-path loss ratio 0.62, 0 falls
of 120 (teacher 0). Power is 1.22 times the teacher value (95 % range 1.20 to 1.24), above the prior-study limit of
1.15. vx loss ratio 0.99.

## Limits

- Chrono label NOT_CONFIRMED (gates G2 wrong way, G3 falls, S1 power not satisfied).
- One NRD seed (FRESH-b). NRD replicas with seeds 63 and 64 did not pass the main NRD gate.
- The NRDs, trained only on teacher data, predict almost no falls for this gait. The falls are found only in Chrono.
- Soil levels are study levels, not measured sand. No physical robot was actuated.
- These are development and held-out simulation suites, not hardware qualification.

Suggested first hardware test (not done): flat medium sand only, lateral 0.3 to 0.45 m/s, with a spotter. Stop if
the tilt exceeds 25 deg for 0.5 s, or if the body leans slowly onto the trailing legs and slides backward.

Study report SHA256 (`FINAL_REPORT.md`):
`5c01a9e7bfe5c2d8158e538e43a5d509e6cf3cc85172d82ec2ac3bc3efcac2a1`.
Detailed research receipts are archived outside Git at
`/home/harry/go2_sand/results/lateral_stuck_20261108_pr_20261109/receipts/`; the side-by-side CRM showcase video
is at `/home/harry/go2_sand/results/lateral_stuck_showcase_v2s81_20261109/`.

## Check in unitree_mujoco (2026-11-09)

The package was renamed on 2026-11-09 from the checked alias `rigidcheck_V2n_s81`; ONNX bytes and all control
settings are unchanged from the package checked below.

The exact packaged ONNX and its teacher ran through the existing C++ deploy stack
in MuJoCo on flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress`
(30 s) run per policy. Both completed both profiles with zero falls, zero
non-finite policy outputs and no command-plan warnings; real-time factors were
approximately 1.000. The deployment config and physics settings were identical
apart from the model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.083 / 0.059 / 0.125 | 7.7 / 12.6 / 23.9 | 18.4 | 1.466 | 3.81 |
| V2n81 / demo_final | 0.071 / 0.041 / 0.119 | 7.6 / 13.5 / 25.0 | 22.5 | 1.616 | 5.53 |
| mjlab / stress | 0.096 / 0.073 / 0.143 | 8.4 / 17.5 / 27.4 | 29.8 | 1.742 | 6.29 |
| V2n81 / stress | 0.078 / 0.052 / 0.135 | 7.2 / 18.6 / 26.8 | 34.1 | 1.894 | 6.98 |

MAE improved on all three axes in both profiles: vx / vy / wz -15% / -31% / -5% on demo and -18% / -30% / -6% on
stress. Lateral achieved/commanded on demo: +0.5 m/s 0.70 (teacher 0.54), -0.5 m/s 0.84 (teacher 0.56).
Mean power rose 22.2% on demo and 14.6% on stress; these single-run differences are descriptive.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.

Reproduce both lateral candidates and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-lateral-finetune-candidates).
This is a one-repeat C++ deployment check on rigid ground, not a statistically reliable ranking, a sand test or
hardware validation. No physical robot was actuated.
