# Go2 velocity: NRD lateral finetune, architecture ablation 3T control, seed 81 (EXPERIMENTAL)

**Status: EXPERIMENTAL architecture-ablation policy. Passes the Chrono sand selection rule (4 early stops, limit 4). Held-out suite not run: Chrono label NOT_EVALUATED_ON_HELDOUT. Not tested on hardware.**

PPO seed 81, iteration 299, initialized from the unchanged `unitree_rl_mjlab` actor (`model_10000.pt`, ONNX
`c58a3494...`) and optimized inside one frozen three-transformer NRD (3T: core, collision with one contact switch per
foot, and contact): `nrd_v3` FRESH-b, NRD seed 62 (loader SHA256 `501c9b8d...`). This NRD is byte for byte the NRD of
[V2n s81](../../nrd_finetune_lateral_v2n_seed81/velocity/README.md). Its weight digest was `ca01f9e1...` before and
after PPO. The 3T has 2,473,582 parameters plus 2,969 normalization numbers (2,476,551), the size target of the
ablation. The recipe is V2 of study `lateral_stuck_20261108` (`v3_V2`, SHA256 `162b4883...`), as for V2n s81. It adds
lateral commands, starts from stuck lateral states, a relaxed action anchor for lateral commands, and swing-peak,
foot-drag and lateral-shortfall terms.

The NRD data is the data of V2n's NRD: MuJoCo rigid, Chrono CRM `crm_prod`, and the lateral CRM sand data of
`lateral_stuck_20261108` (mixture: rigid 0.5; CRM 0.5, split `crm_prod` 0.5 / lateral 0.5; split manifest
`9ba6dce9`). The original fixed teacher collected all of it (480 of 480 lateral shards record policy `c58a3494`). No
fine-tuned-policy trajectories were used. The held-out TEST folder is excluded. Direct physics was used for
evaluation, not for actor optimization.

Role in the study: this is the 3T control `abl3tctl_s81` of the NRD architecture ablation `arch_ablation_20261118`.
It repeats the V2n s81 run with the ablation PPO code (snapshot `1baaae85b223` = the V2n code `8e08e2544f0d` plus the
architecture port) on an Euler A100 (job 123531). V2n s81 trained on an RTX A4500. The 3T path of the port was
bit-identical to the V2n code over 1,000 environment steps x 1,024 environments (fixed behaviour policy, no PPO
updates). The two PPO configs differ only in the NRD file path and the lineage label. The ONNX bytes still differ
(`3aea21c1...` against V2n's `1419d972...`). The control checks whether the PPO GPU type and code explain the ablation
results; the study report infers that they do not explain the one-network result, and the control does not test the
NRD-training platform. It is reported, never in the pick pool.

Goal: the V2n goal. Fix the lateral foot-drag stall seen on the real robot. On sand the teacher steps only about
1.8 cm sideways per step (10.2 cm on rigid ground), at a fixed 1.67 Hz gait clock, so its feet land in their own
craters and it stalls. This actor takes longer sideways strides. In the ablation, the 3T is the reference design.
The 3M, 1T and 1M policies change only the frozen NRD.

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

ONNX SHA256: `3aea21c14b6916e36bb6957187d6a9b744fbee705313c6459944b86381de7bf0`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `1.91e-06`; deploy-policy mirror versus Torch
max error `6.19e-05`. The larger mirror error includes observation
reconstruction, including phase.

## Chrono CRM sand evidence (simulation only)

Base policy = the unchanged `unitree_rl_mjlab` actor in the same jobs. Selection suite `suite_v1`, tag `ablsel1`:
18 AMD MI210 jobs, each with the base policy and all 21 ablation policies (V2n s81 included). Score = stuck-time
ratio = failure-penalized lateral STUCK seconds of the policy / those of the base policy, summed over the realistic
cells (medium flat, medium uneven and firm uneven sand) and repeats r0 and r2: 48 episodes. Lower is better. Frozen
rule `selection_rule_abl_v1.json` (SHA256 `49c1442d...`).

| Check (selection suite, 48 realistic episodes) | This policy | Base policy | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio | **0.249** (96.8 s / 388.1 s) | 1 | score only | better |
| Stuck-time ratio, medium flat / medium uneven / firm uneven | 0.18 / 0.29 / 0.27 | 1 | - | better |
| Realistic early stops | 4 (4 falls: 1 medium flat, 3 medium uneven) | 2 (2 falls) | base + 2 = 4 | pass, at the limit |
| Wrong-way holds (net progress below -0.10 m) | 0 | 0 | base + 1 | pass |
| Realistic blocks complete | 6 of 6 | 6 of 6 | 6 | pass |
| Soft-sand stress early stops, of 16 (r0, not scored) | 7 (7 falls) | 6 (4 falls, 2 bed exits) | - | worse |

Sand selection rule: **pass** (eligible). One more realistic early stop would exclude it. The control seeds 82 and 83
scored 0.285 and 0.216; both are eligible with 3 early stops. A control is not in the pick pool. Thus the held-out
`suite_v2` was **not run** for this policy. Per-cell ratios are sums over r0 and r2 in `aggregate_ablsel1.json`.

Over all 72 selection episodes, soft stress cells included, this policy fell 11 times. Each control seed fell 6 to 11
times, each V2n-pool seed 6 to 8 times. No NRD of the study, the 3T included, predicts these falls.

## Rigid MuJoCo development evidence

On the 120-path MuJoCo rigid development suite (tag `ablsel1`, paired with the same-tag base-policy run,
family-stratified paired bootstrap): failure-penalized tracking loss ratio **0.859** (95 % range 0.838 to 0.880),
lateral-path loss ratio 0.63 (0.57 to 0.71), 0 falls of 120 (base 0). Axis loss ratios vx / vy / wz: 0.99 / 0.73 /
0.83. Power is 1.21 times the base value (95 % range 1.19 to 1.23), above the prior-study limit of 1.15. Target rate
is 1.12 times.

Real-robot indicators named by the user: a policy that works on the real Go2 has higher power and leg lift than the
base policy. This is at most a necessary sign; the V2 reward asks for a swing peak of 80 mm. Same 120 stored traces
(112 paths for the swing values), ratio of means, 95 % path bootstrap:

| Indicator | This policy | Base policy | x base [95 % range] |
|---|---:|---:|---|
| Mechanical power | 22.6 W | 18.7 W | 1.21 [1.19, 1.23] |
| Foot swing peak | 67.4 mm | 47.1 mm | 1.43 [1.40, 1.46] |
| Calf lift | 48.7 mm | 35.0 mm | 1.39 [1.37, 1.42] |
| Sideways drift, 84 paths with zero lateral command (+ = left) | -2.9 mm/s [-5.1, -0.8] | +7.6 mm/s | - |

Both indicators are above the base policy. Lateral speed / command: +y 0.88, -y 1.00.

## Compared with V2n s81

V2n s81 is study role `abl3t_s81`: the same NRD, recipe and PPO seed, trained with the original PPO code on an
RTX A4500.

| Metric | This policy (new 3T) | V2n s81 | Same job? |
|---|---|---|---|
| Chrono selection stuck-time ratio | 0.249 | 0.208 | yes, the same 18 jobs |
| Per cell: medium flat / medium uneven / firm uneven | 0.18 / 0.29 / 0.27 | 0.11 / 0.26 / 0.24 | yes |
| Realistic early stops (base 2, limit 4) | 4 (4 falls) | 3 (2 falls, 1 bed exit) | yes |
| Wrong-way holds | 0 | 0 | yes |
| Held-out `suite_v2` | not run | NOT_CONFIRMED, stuck-time ratio 0.215 | - |
| Rigid dev120 loss ratio | 0.859 [0.838, 0.880] | 0.854 [0.836, 0.874] | yes, tag `ablsel1` |
| Rigid lateral-path loss ratio | 0.63 | 0.62 | yes |
| Rigid falls, of 120 | 0 | 0 | yes |
| Rigid power x base | 1.21 | 1.22 | yes |
| Rigid foot swing peak x base | 1.43 | 1.40 | yes |
| Rigid calf lift x base | 1.39 | 1.36 | yes |
| Rigid drift, zero lateral command | -2.9 mm/s | +1.9 mm/s | yes |
| C++ deploy power x base, demo / stress | 1.21 / 1.13 | 1.22 / 1.15 | no: 11-20 and 11-19 jobs; both use the 11-19 base run |
| C++ deploy foot swing peak x base, demo / stress | 1.37 / 1.25 | 1.34 / 1.23 | no (as above) |
| C++ deploy MAE vy, demo | 0.039 m/s | 0.041 m/s | no |

The rigid and indicator values are almost equal. The Chrono score is worse (0.249 against 0.208). The frozen rule
compares 3-seed spreads, not single seeds: 3T pool 0.208 to 0.291, control 0.216 to 0.285. The spreads overlap. The
study report calls the control slightly worse than the pool.

## Limits

- Chrono label NOT_EVALUATED_ON_HELDOUT. Only the selection suite ran; it is a development suite, not a held-out one.
  V2n s81 passed the same rule and was then NOT_CONFIRMED on the held-out suite (wrong way, falls, power).
- The early-stop result is at the limit (4 of 4 allowed). On soft stress sand the policy fell in 7 of 16 episodes.
- One NRD seed (FRESH-b). This NRD fails the rigid NRD rules (G1). The seed rule picked the most left-biased seed in
  every design, the 3T included. That rule is an open user decision.
- The NRDs predict almost no falls. The falls are found only in Chrono.
- PPO did not repeat across GPU type and code: the same NRD, recipe and seed gave other ONNX bytes and another score.
- Rigid power is 1.21 times the base value, above the prior-study limit of 1.15.
- Soil levels are study levels, not measured sand. No physical robot was actuated.
- These are development simulation suites, not hardware qualification.

Study report SHA256: `STUDY_REPORT.md` `87e8072f62ca8949e150b6fbd4ee9b1b3968a69ea12b4585fac78d3951876155`,
`STUDY_REPORT_ROUND2.md` `6773562a60bcf3392c3aae6969e13e400c05a6675cdfa60790031eaca95c1ae0`.
Detailed receipts and parity logs of this package are archived outside Git at
`/home/harry/go2_sand/results/arch_ablation_20261123_pr/`; the raw C++ deploy evidence is at
`/home/harry/go2_sand/results/arch_ablation_20261120_rigid_deploy_new3t/`. The MuJoCo replay video of the
`demo_final` run below is `/home/harry/arch_ablation_20261118/go2_sand/mujoco_rigid/videos5/2_new_3t_s81.mp4`
(V2n s81: `1_v2n_s81.mp4`; side views of all five policies and the base policy in segment `lateral_+0.5`:
`0_all_five_lateral.mp4`; see `README.txt` there). The
videos show flat rigid ground, not sand and not the real robot.

## Check in unitree_mujoco (2026-11-20)

The package was renamed on 2026-11-23 from the checked alias `rigidcheck_abl3tctl_s81`; ONNX bytes and all control
settings are unchanged from the package checked below.

The exact packaged ONNX and its teacher ran through the existing C++ deploy stack
in MuJoCo on flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress`
(30 s) run per policy. This was a separate 2026-11-20 job with its own teacher run.
V2n s81, 3M, 1T and 1M ran in the 2026-11-19 job. Both policies completed both
profiles with zero falls, zero non-finite policy outputs and no command-plan
warnings; real-time factors were approximately 1.000. All tool gates D1 to D5
passed. The deployment config and physics settings were identical apart from the
model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.083 / 0.060 / 0.125 | 7.6 / 12.9 / 24.4 | 18.4 | 1.471 | 3.24 |
| arch3t81 / demo_final | 0.074 / 0.039 / 0.119 | 7.2 / 13.0 / 25.5 | 22.4 | 1.619 | 5.54 |
| mjlab / stress | 0.097 / 0.073 / 0.143 | 8.2 / 17.5 / 28.2 | 29.8 | 1.737 | 6.38 |
| arch3t81 / stress | 0.084 / 0.054 / 0.133 | 7.3 / 17.9 / 29.0 | 33.8 | 1.881 | 6.35 |

MAE improved on all three axes in both profiles: vx / vy / wz -11% / -34% / -5% on demo and -13% / -26% / -7% on
stress. Lateral achieved/commanded on demo: +0.5 m/s 0.69 (teacher 0.53), -0.5 m/s 0.86 (teacher 0.56).
Mean power rose 21.5% on demo and 13.4% on stress; these single-run differences are descriptive. The study's
deploy-stack indicator ratios use the 11-19 base run: power 1.21 / 1.13, foot swing peak 1.37 / 1.25 and calf lift
1.33 / 1.21 times (demo / stress). The 11-20 teacher run matched the 11-19 one: 18.44 against 18.49 W on demo,
29.83 against 29.85 W on stress.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.

Reproduce the four architecture-ablation actors, V2n s81 and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-architecture-ablation-candidates).
This is a one-repeat C++ deployment check on rigid ground, not a statistically reliable ranking, a sand test or
hardware validation. No physical robot was actuated.
