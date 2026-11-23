# Go2 velocity: NRD lateral finetune, architecture ablation 3M, seed 81 (EXPERIMENTAL)

**Status: EXPERIMENTAL architecture-ablation policy. Passes the Chrono sand selection rule. Held-out Chrono label NOT_CONFIRMED. Not tested on hardware.**

PPO seed 81, iteration 299, initialized from the unchanged `unitree_rl_mjlab` actor (`model_10000.pt`, ONNX
`c58a3494...`). It was optimized inside one frozen NRD of the 3M design: `go2_3m_s62` (loader SHA256 `7da4ce7b...`).
The 3M is the three-network design of the V2n s81 NRD (core, collision, contact) with each transformer trunk replaced
by a residual MLP (width 256, 2 blocks; hidden width core 516, collision 356, contact 356). Everything else is the 3T's.
It has 2,474,118 parameters, 536 (0.02 %) more than the 3T (2,473,582). It is 0.10 % below the study's size target
of 2,476,551, which also counts the 3T's 2,969 normalization numbers. Its foot-contact flags come from its own collision
network, as in the 3T. It reads only the current joint target.

Recipe V2 of study `lateral_stuck_20261108` (`v2.json`, SHA256 `162b4883...`) is unchanged from V2n s81. It adds
lateral commands, starts from stuck lateral states, a relaxed action anchor for lateral commands, and swing-peak,
foot-drag and lateral-shortfall terms. The PPO config differs from the V2n s81 run only in the NRD file, its SHA256
and the lineage track. The PPO code is the V2n code (`8e08e2544f0d`) plus the architecture port (snapshot
`1baaae85b223`). Its 3T path is bit-identical to the old code over 1,000 environment steps x 1,024 environments
(fixed behaviour policy, no PPO updates). PPO ran on an Euler A100 (job 123516); V2n s81 ran on an RTX A4500. The
NRD weights did not change during PPO (digest equal before and after).

The NRD was trained from scratch (seed 62, 13,500 updates, the 3T schedule) on the same data as FRESH-b, the NRD of
V2n s81. It has the same four sources, split manifest `9ba6dce9` and mixture: rigid 0.5; Chrono CRM 0.5, half
`crm_prod` and half the 2.22 h of lateral sand data of the lateral study. The NRD and its fitted normalizers use only
trajectories collected by the original fixed teacher. No fine-tuned-policy trajectories were used. Direct physics was
used for evaluation, not actor optimization.

Goal: this policy is one arm of an NRD architecture ablation. All arms use the same recipe, PPO seeds (81-83) and NRD training data. Only
the frozen NRD changes. The question: does an NRD with MLP trunks give a policy as good as V2n s81 against the lateral
foot-drag stall on sand? The task is the same as for V2n s81: take longer sideways strides, so the feet do not land in
their own craters.

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
| `provenance.json` | Actor, fixed teacher, frozen 3M NRD, recipe, PPO code, results and sim_deploy SHA256 lineage |

ONNX SHA256: `b2804cdc091e73f2f05e1638b201d7fdba616e7d3b8d4654a3334b828d902829`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `1.79e-06`; deploy-policy mirror versus Torch
max error `6.87e-05`. The larger mirror error includes observation
reconstruction, including phase.

## Chrono CRM sand evidence (simulation only)

Teacher = the unchanged `unitree_rl_mjlab` actor in the same jobs. Stuck time = failure-penalized lateral STUCK
time (1 s windows with lateral tracking ratio below 0.4; a fall or early stop counts the rest of the hold as stuck).
Realistic cells = medium flat, medium uneven and firm uneven sand.

Selection suite (`suite_v1`, tag `ablsel1`). 48 realistic episodes: 3 cells x 8 commands x 2 repeats. The teacher and
all 21 ablation policies ran in each of the 18 AMD MI210 jobs.

| Check (selection suite, 48 realistic episodes) | This policy | Teacher | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio (selection score) | **0.295** | 1 | lowest eligible 3M | 3M pick |
| Stuck-time ratio, medium flat / medium uneven / firm uneven | 0.31 / 0.32 / 0.25 | 1 | - | better |
| Early stops | 1 (1 fall, medium uneven) | 2 | teacher + 2 | pass |
| Wrong-way holds | 0 | 0 | teacher + 1 | pass |
| Realistic blocks complete, of 6 | 6 | 6 | all | pass |

The policy passes the sand selection rule. It is the 3M pick of the study. Only 1 of the 3 3M PPO seeds passed:
seeds 82 and 83 had 7 and 5 early stops.

Held-out `suite_v2` (tag `ablq1`, run once). The jobs held the teacher, this policy and V2n s81.

| Check (held-out suite_v2, 72 realistic episodes) | This policy | Teacher | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio (blocks better, of 9) | **0.302** (9) | 1 | 0.75 or less, 8 of 9 | pass |
| Stuck-time ratio, medium flat / medium uneven / firm uneven | 0.27 / 0.42 / 0.18 | 1 | 1 or less in each cell | pass |
| Stuck-time ratio +y / -y | 0.33 / 0.27 | 1 | 1.0 or less | pass |
| Soft-sand wrong-way segments -y / +y, of 16 | 14 / 0 | 0 / 0 | teacher + 1 | **fail** |
| Realistic early ends, of 72 | 17 (4 falls, 13 left the bed) | 0 | teacher + 2 | **fail** |
| Power / action-rate ratio | 1.52 / 1.39 | 1 | 1.25 or less | **fail** |
| Soft-sand stress early stops, of 32 (flag only) | 18 (14 falls) | 16 (16 falls) | flag above teacher + 4 | not flagged |

Verdict NOT_CONFIRMED. All 4 realistic falls are on medium uneven sand. The 13 bed exits are 6 on firm uneven, 5 on
medium flat and 2 on medium uneven sand. On soft sand, the policy slides the wrong way in 14 of 16 -y segments.

## Rigid MuJoCo development evidence

On the 120-path MuJoCo rigid development suite (tag `ablsel1`, paired with the teacher, family-stratified path
bootstrap): failure-penalized tracking loss ratio **0.896** (95 % range 0.876 to 0.917), lateral-path loss ratio 0.69
(0.64 to 0.76), 0 falls of 120 (teacher 0). vx / vy / wz loss ratio 1.01 / 0.84 / 0.84. Power is 1.23 times the
teacher value (95 % range 1.21 to 1.26), above the prior-study limit of 1.15.

Real-robot indicators on the same stored traces (120 paths; swing peak and calf lift on the 112 paths where the robot
walks) (power and lower-leg swing lift higher than the base policy's):

| Indicator (rigid dev120) | This policy | Base policy |
|---|---|---|
| Mechanical power x base | 1.23 (1.21 to 1.26) | 1 (18.7 W) |
| Foot swing peak x base | 1.42 (1.39 to 1.45), 66.9 mm | 1 (47.1 mm) |
| Calf lift x base | 1.38 (1.35 to 1.41), 48.3 mm | 1 (35.0 mm) |
| Sideways drift, zero lateral command [mm/s, + = left] | +7.3 (4.1 to 10.4) | +7.6 |
| Lateral speed / command, +y / -y | 0.89 / 0.94 | 0.67 / 0.67 |

Both indicators are higher than the base policy's. The sideways drift stays at the base policy's value
(difference -0.2 mm/s, 95 % range -2.2 to +1.7). The indicators are at most a necessary sign: the V2 reward asks for a
swing peak of 80 mm.

## Compared with V2n s81

V2n s81 = study role `abl3t_s81` =
[`nrd_finetune_lateral_v2n_seed81`](../../nrd_finetune_lateral_v2n_seed81/velocity/README.md), the 3T reference.
Each V2n number below comes from the same jobs, the same tag or the same deploy job as this policy. These are new
runs of V2n s81, so some values differ a little from its own README.

| Metric | This policy (3M) | V2n s81 (3T) | Same job or tag |
|---|---|---|---|
| Chrono selection score (lower is better) | 0.295 | 0.208 | `ablsel1`, same 18 jobs |
| Selection early stops / wrong-way holds (teacher 2 / 0) | 1 / 0 | 3 / 0 | `ablsel1` |
| Held-out stuck-time ratio | 0.302 | 0.215 | `ablq1`, same jobs |
| Held-out realistic early ends, of 72 | 17 (4 falls) | 6 (6 falls) | `ablq1` |
| Held-out soft-sand -y wrong-way segments, of 16 | 14 | 9 | `ablq1` |
| Held-out power / action-rate ratio | 1.52 / 1.39 | 1.68 / 1.47 | `ablq1` |
| Held-out verdict | NOT_CONFIRMED | NOT_CONFIRMED | `ablq1` |
| Rigid dev120 loss ratio | 0.896 (0.876 to 0.917) | 0.854 (0.836 to 0.874) | `ablsel1`, same base run |
| Rigid lateral-path loss ratio | 0.69 | 0.62 | `ablsel1` |
| Rigid power x base | 1.23 | 1.22 | `ablsel1` traces |
| Rigid foot swing peak / calf lift x base | 1.42 / 1.38 | 1.40 / 1.36 | `ablsel1` traces |
| Rigid drift, zero lateral command [mm/s] (base +7.6) | +7.3 | +1.9 | `ablsel1` traces |
| C++ deploy power x base, demo / stress | 1.22 / 1.12 | 1.22 / 1.15 | 2026-11-19 job |
| C++ deploy MAE vy, demo / stress [m/s] (teacher 0.059 / 0.073) | 0.042 / 0.056 | 0.041 / 0.051 | 2026-11-19 job |

On sand, the 3M policy cuts the stall less than V2n s81 does (selection 0.295 against 0.208, held-out 0.302 against
0.215). On the held-out suite it has fewer falls (4 against 6), but more early ends (17 against 6) and more soft-sand
wrong-way slides (14 against 9). On rigid ground both have 0 falls and similar power and swing lift, but the 3M
tracks a little worse (loss ratio 0.896 against 0.854; the 95 % ranges do not overlap).

## Limits

- Held-out Chrono label NOT_CONFIRMED (gates G2 wrong way, G3 early ends, S1 power and action rate not satisfied).
- One NRD seed (62) and one PPO seed (81). Only 1 of 3 3M PPO seeds passed the selection rule.
- The NRD seed rule (lowest validation stall gap G2v.P1 of seeds 61-64) picked `go2_3m_s62` at 0.310. This is above
  the limit of 0.257. Its held-out G2.P1 is 0.233 (limit 0.239). It fails the G1 accuracy rules (CRM body-velocity
  RMSE 0.0801 m/s, limit 0.0704 m/s). The same pooled rule picked the most left-biased seed in every design. This
  rule is an open user decision.
- Open loop on sand, the NRD's base position error at 1 s / 2 s is 52.8 / 139.6 mm (FRESH-b: 50.8 / 121.4 mm).
  A few windows diverge but stay finite (13 of 1,933 by 2 s, 30 by 4 s; FRESH-b 5 and 55). In the 3M they run much
  farther (largest error 54 km; FRESH-b 9.2 m), so from about 2.5 s on the 3M's sand mean shows these few windows,
  not the typical error.
- The 3M NRD trained on an Euler A100 (job 123466), FRESH-b on an AMD MI350X. No 3T NRD control covers this
  platform difference.
- The NRD was trained only on teacher data. The early ends and wrong-way slides show only in Chrono. Rigid MuJoCo has
  0 falls.
- Soil levels are study levels, not measured sand. No physical robot was actuated.
- These are development, selection and held-out simulation suites, not hardware qualification.

Study report SHA256 (`STUDY_REPORT_ROUND2.md`):
`6773562a60bcf3392c3aae6969e13e400c05a6675cdfa60790031eaca95c1ae0`.
Detailed research receipts and the fresh parity log are archived outside Git at
`/home/harry/go2_sand/results/arch_ablation_20261123_pr/`. The study files are in `/home/harry/arch_ablation_20261118/`
(`go2_sand/results_policy/`, `go2_sand/mujoco_rigid/`). The MuJoCo replay of the C++ `demo_final` run is
`/home/harry/arch_ablation_20261118/go2_sand/mujoco_rigid/videos5/3_3m_s81.mp4` (V2n s81: `1_v2n_s81.mp4`; all five
policies and the base policy side by side in `lateral_+0.5`: `0_all_five_lateral.mp4`). The videos show flat rigid ground, not sand and
not the real robot.

## Check in unitree_mujoco (2026-11-19)

The package was renamed on 2026-11-23 from the checked alias `rigidcheck_abl3m_s81`; ONNX bytes and all control
settings are unchanged from the package checked below.

The exact packaged ONNX and its teacher ran through the existing C++ deploy stack
in MuJoCo on flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress`
(30 s) run per policy. V2n s81 ran in the same job. Both completed both profiles
with zero falls, zero non-finite policy outputs and no command-plan warnings;
real-time factors were approximately 1.000. The deployment config and physics
settings were identical apart from the model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.082 / 0.059 / 0.125 | 7.7 / 12.6 / 24.2 | 18.5 | 1.470 | 3.46 |
| 3M81 / demo_final | 0.076 / 0.042 / 0.125 | 6.9 / 14.2 / 24.1 | 22.6 | 1.631 | 5.38 |
| mjlab / stress | 0.097 / 0.073 / 0.144 | 8.2 / 17.8 / 29.0 | 29.9 | 1.742 | 6.43 |
| 3M81 / stress | 0.087 / 0.056 / 0.133 | 7.6 / 18.4 / 25.6 | 33.5 | 1.868 | 5.67 |

MAE vx / vy / wz changed by -7% / -29% / -0% on demo and -10% / -23% / -8% on stress. Lateral achieved/commanded
on demo: +0.5 m/s 0.68 (teacher 0.54), -0.5 m/s 0.80 (teacher 0.56). Mean power rose 22.3% on demo and 12.2% on
stress. Foot swing peak was 1.34 times the teacher value on demo and 1.25 times on stress; calf lift 1.30 and 1.20
times. These single-run differences are descriptive.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.

Reproduce the four ablation policies, V2n s81 and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-architecture-ablation-candidates).
This is a one-repeat C++ deployment check on rigid ground, not a statistically reliable ranking, a sand test or
hardware validation. No physical robot was actuated.
