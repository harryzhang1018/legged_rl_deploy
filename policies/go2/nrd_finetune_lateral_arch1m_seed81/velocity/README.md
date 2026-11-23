# Go2 velocity: NRD lateral finetune, architecture ablation 1M, seed 81 (EXPERIMENTAL)

**Status: experimental architecture-ablation policy. It FAILS the Chrono sand selection rule (10 early stops, limit 4). Chrono label NOT_ELIGIBLE. Not tested on hardware.**

PPO seed 81, iteration 299, initialized from the unchanged `unitree_rl_mjlab` actor (`model_10000.pt`, ONNX
`c58a3494...`). It was optimized inside one frozen NRD of the **1M** design of study `arch_ablation_20261118`:
`go2_1m_s62` (loader SHA256 `29fd869c...`). The 1M is one network: a token projection, then a residual MLP (width 512,
2 blocks, hidden 953) over the last 4 step tokens. Each 20 ms token holds 37 state values, 12 joint targets and
3 ground features. The 1M has no collision network, no contact network and no contact head. It has 2,476,168
parameters, -0.02 % of the study's size target of 2,476,551 (the 3T's 2,473,582 parameters plus its 2,969
normalization numbers). PPO gets its foot-contact flags (rewards and critic) from a frozen foot-height rule,
`foot_rule_v1` (SHA256 `644c7ac9...`), on the predicted foot height and vertical foot speed. The NRD weights did not
change during PPO (digest `25429dd6...` before and after).

The recipe is V2 of study `lateral_stuck_20261108` (`v3_V2`, SHA256 `162b4883...`), the same recipe file as
[V2n s81](../../nrd_finetune_lateral_v2n_seed81/velocity/README.md): lateral commands, starts from stuck lateral
states, a relaxed action anchor for lateral commands, and swing-peak, foot-drag and lateral-shortfall terms. The PPO
run config differs from the V2n s81 run only in the NRD path, the NRD hash and the lineage track. Only for the
one-network NRD: the start states carry the 3 previous joint targets, and the flags come from `foot_rule_v1`. The PPO
code is the ablation snapshot `1baaae85b223`: the V2n code `8e08e2544f0d` plus the architecture port. Its 3T path is
bit-identical to the original code over 1,000 environment steps x 1,024 environments (fixed behaviour policy, no PPO
updates). PPO ran on an Euler A100 (job 123522); V2n s81 ran on an RTX A4500. The study's 3T control (same 3T NRD,
A100) covers this GPU change.

The NRD trained on the same data as the V2n NRD (FRESH-b): the same 4 sources (rigid, `crm_prod` and the two lateral
sand sets), split manifest `9ba6dce9` and mixture (rigid 0.5; CRM 0.5, split `crm_prod` 0.5 / lateral 0.5). The
held-out lateral TEST folder was not used. The original fixed teacher collected all of this data (480 of 480 lateral
shards). No fine-tuned-policy trajectories were used. The NRD trained for 13,500 updates from a normal(0, 0.02) start
(no ridge prefit) on an Euler A100 (job 123470). Direct physics was used for evaluation, not actor optimization.

Goal: test if the NRD design changes the result of this fine-tune. The 1M is the simplest design of the study: one
network, contact only implicit. The target behaviour is the one of V2n s81: longer sideways strides against the
lateral foot-drag stall seen on the real robot.

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

ONNX SHA256: `e530a616d83ea743a07f1addc69b0db1d817295da216c4fda2edbeee77584111`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `1.43e-06`; deploy-policy mirror versus Torch
max error `6.51e-05`. The larger mirror error includes observation
reconstruction, including phase (`2.25e-05`).

## Chrono CRM sand evidence (simulation only)

Teacher = the unchanged `unitree_rl_mjlab` actor in the same jobs. Selection suite `suite_v1` (tag `ablsel1`): 18
AMD MI210 jobs, the teacher and all 21 study policies in every job. Score = failure-penalized lateral STUCK time
divided by the teacher's, over 6 blocks (medium flat, medium uneven, firm uneven sand x repeats r0 and r2 = 48
realistic episodes). Lower is better. Pass rule (frozen study rule `selection_rule_abl_v1`): early stops not more than teacher + 2,
wrong-way holds not more than teacher + 1, no missing realistic repeat.

| Check (selection suite_v1, 48 realistic episodes) | This policy | Teacher | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio (score) | **0.252** (98.0 s / 388.1 s) | 1 | ranks eligible policies only | better |
| Early stops (falls / bed exits) | **10** (3 / 7) | 2 (2 / 0) | teacher + 2 = 4 | **fail** |
| Wrong-way holds | 0 | 0 | teacher + 1 = 1 | pass |
| Realistic blocks present | 6 of 6 | 6 of 6 | 6 | pass |
| Eligible | **no** | - | all three rules | **fail** |

- The 10 early stops: 6 on medium flat, 3 on medium uneven and 1 on firm uneven sand.
- 7 bed exits: 5 on the lateral reversal hold (8 s left, then 8 s right, 0.4 m/s) and 2 on the right 0.3 m/s hold.
- 3 falls: 1 on the left 0.3 m/s hold and 2 on the left 0.3 m/s hold with 0.3 rad/s yaw.
- The teacher's 2 early stops are falls on the left 0.5 m/s hold.
- No 1M policy was eligible (seeds 81 / 82 / 83: score 0.252 / 0.310 / 0.240, early stops 10 / 5 / 9). Thus the 1M design has no pick.
- The held-out suite_v2 was **not run** for this policy. The study runs it only for the pick of each design.

The study's diagnosis (`POLICY_DIAGNOSIS.md`, all three 1M policies): the picked 1M NRD moves the robot too far left
(offset +63 mm/s, NRD minus Chrono; 3T NRD +29). PPO cancels this offset inside the NRD by a steer to the right. In
Chrono this becomes a real drift to the right (-68 to -47 mm/s on firm ground; 3T -42 to -19). All 14 bed exits of the
1M policies were at the right edge. All 10 of their falls were on commands with a leftward part: the robot slides back,
sinks on its trailing feet and rolls over. No NRD, the 3T NRD included, predicts these falls.

## Rigid MuJoCo development evidence

On the 120-path MuJoCo rigid development suite (paired with the teacher, tag `ablsel1`, family-stratified paired
path bootstrap): failure-penalized tracking loss ratio **0.959** (95 % range 0.939 to 0.980), a pass of the rigid gate
(upper bound 1.05 or less). Lateral-path loss ratio 0.789 (0.720 to 0.875). 0 falls of 120 (teacher 0). vx / vy / wz
loss ratio 0.956 / 0.978 / 0.950. The vy range over all 120 paths (0.917 to 1.042) includes 1. Power is 1.21 times
the teacher value (1.18 to 1.23), above the prior-study limit of 1.15. Target rate 1.14 times the teacher.

Real-robot indicators named by the user (same stored traces; 112 paths for swing peak and calf lift). They are a
necessary sign at most. The V2 reward asks for a swing peak of 80 mm.

| Indicator | This policy | Teacher | Ratio [95 % range] |
|---|---|---|---|
| Mechanical power | 22.6 W | 18.7 W | 1.21 [1.18, 1.23] |
| Foot swing peak | 66.0 mm | 47.1 mm | 1.40 [1.38, 1.43] |
| Calf lift | 48.5 mm | 35.0 mm | 1.39 [1.36, 1.41] |
| Sideways drift, zero lateral command (84 paths; + = left) | -20.6 mm/s [-23.1, -18.2] | +7.6 mm/s | difference -28.1 [-30.3, -25.9] |
| Lateral speed / command, +y / -y (7 / 5 paths) | 0.84 / 1.13 | 0.67 / 0.67 | - |

Both indicators are higher than the teacher's. The sideways drift to the right is the largest of the four
architecture-ablation candidates. The -y ratio above 1 means the policy overshoots right commands on rigid ground.

## Compared with V2n s81

V2n s81 = study role `abl3t_s81` = [`nrd_finetune_lateral_v2n_seed81`](../../nrd_finetune_lateral_v2n_seed81/velocity/README.md):
the same recipe, PPO seed and NRD training data, in the 3T NRD (FRESH-b). All rows come from the same jobs or the same stored runs
for both policies: the Chrono selection suite `ablsel1`, the rigid dev120 tag `ablsel1` and the 2026-11-19 C++ job.
The held-out row is from suite_v2 tag `ablq1`, which ran V2n s81 but not this policy.

| Measure | This policy (1M) | V2n s81 (3T) | Teacher |
|---|---|---|---|
| Chrono selection score | 0.252 | 0.208 | 1 |
| Chrono early stops, of 48 (falls / bed exits) | 10 (3 / 7) | 3 (2 / 1) | 2 (2 / 0) |
| Chrono wrong-way holds | 0 | 0 | 0 |
| Chrono selection rule | **fail** | pass (3T pick) | - |
| Held-out suite_v2 | not run | NOT_CONFIRMED (0.215) | 1 |
| Rigid dev120 loss ratio [95 %] | 0.959 [0.939, 0.980] | 0.854 [0.836, 0.874] | 1 |
| Rigid lateral-path loss ratio | 0.789 | 0.623 | 1 |
| Rigid vy loss ratio, 120 paths | 0.978 | 0.752 | 1 |
| Rigid falls, of 120 | 0 | 0 | 0 |
| Power x base (rigid) | 1.21 | 1.22 | 1 |
| Foot swing peak x base (rigid) | 1.40 | 1.40 | 1 |
| Calf lift x base (rigid) | 1.39 | 1.36 | 1 |
| Sideways drift, zero lateral command (rigid, mm/s) | -20.6 | +1.9 | +7.6 |
| C++ deploy power x base, demo / stress | 1.19 / 1.14 | 1.22 / 1.15 | 1 |
| C++ deploy MAE vy, demo / stress (m/s) | 0.037 / 0.048 | 0.041 / 0.051 | 0.059 / 0.073 |

## Limits

- It FAILS the Chrono selection rule: 10 realistic early stops against a limit of 4. Chrono label NOT_ELIGIBLE.
- The held-out suite_v2 was not run. No 1M policy (seeds 81-83) passed the selection rule.
- It is shipped as an ablation reference that passes the rigid MuJoCo tracking gate (0 falls) and the C++ deploy check.
  It does not pass the prior-study rigid power limit (1.21 x, limit 1.15). It is not a hardware candidate.
- It drifts to the right: -20.6 mm/s on rigid ground with zero lateral command. The three 1M policies drift -68 to -47 mm/s on firm Chrono sand.
- Its NRD fails the rigid NRD rules G1 (roll/pitch RMSE 0.02686 rad against the limit 0.02415 rad; FRESH-b, the V2n NRD,
  also fails G1). Seed 62 was picked by the
  lowest validation stall gap (0.159, limit 0.257; held-out gap 0.172, limit 0.239).
- The seed rule picked the most left-biased seed in every design, the 3T included. The study decision (d) on this rule is still open.
- The foot flags come from a rule. On lateral sand (closed loop, first 1 s) this NRD's flags agree with the recorded
  labels 0.860 of the time (FRESH-b 3T collision switches: 0.955).
- Settings not matched by design: the 1M reads the last 4 joint targets, the 3T only the current one. The 1M has no ridge
  prefit and one learning-rate cosine instead of the 3T's per-network schedule.
- The 1M NRD trained on an Euler A100, FRESH-b on an AMD MI350X. No 3T NRD control covers this platform difference.
- One NRD seed and one PPO seed. No NRD predicts a fall in these policies' Chrono episodes. The falls are found only in Chrono.
- Soil levels are study levels, not measured sand. No physical robot was actuated.
- These are development and selection simulation suites, not hardware qualification.

Study report SHA256: `STUDY_REPORT.md` `87e8072f62ca8949e150b6fbd4ee9b1b3968a69ea12b4585fac78d3951876155`,
`STUDY_REPORT_ROUND2.md` `6773562a60bcf3392c3aae6969e13e400c05a6675cdfa60790031eaca95c1ae0`.
Detailed research receipts are archived outside Git at
`/home/harry/go2_sand/results/arch_ablation_20261123_pr/` (receipts and the parity log); the raw C++ deploy evidence is
at `/home/harry/go2_sand/results/arch_ablation_20261119_rigid_deploy/`. The MuJoCo replay video of the C++ demo run is
`/home/harry/arch_ablation_20261118/go2_sand/mujoco_rigid/videos5/5_1m_s81.mp4` (SHA256 `4f2da2f9...`), next to
`1_v2n_s81.mp4` and the side-by-side lateral clip `0_all_five_lateral.mp4`. The videos show flat rigid ground, not sand
and not the real robot.

## Check in unitree_mujoco (2026-11-19)

The package was renamed on 2026-11-23 from the checked alias `rigidcheck_abl1m_s81`; ONNX bytes and all control
settings are unchanged from the package checked below.

The exact packaged ONNX and its teacher ran through the existing C++ deploy stack
in MuJoCo on flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress`
(30 s) run per policy. The same 2026-11-19 job ran V2n s81 and the other ablation
policies. Both policies completed both profiles with zero falls, zero
non-finite policy outputs and no command-plan warnings; real-time factors were
approximately 1.000. All five checks of the tool (D1-D5) passed. The deployment
config and physics settings were identical apart from the model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.082 / 0.059 / 0.125 | 7.7 / 12.6 / 24.2 | 18.5 | 1.470 | 3.46 |
| 1M81 / demo_final | 0.077 / 0.037 / 0.126 | 8.9 / 13.1 / 24.0 | 22.1 | 1.624 | 5.29 |
| mjlab / stress | 0.097 / 0.073 / 0.144 | 8.2 / 17.8 / 29.0 | 29.9 | 1.742 | 6.43 |
| 1M81 / stress | 0.084 / 0.048 / 0.132 | 9.6 / 18.0 / 25.4 | 33.9 | 1.912 | 5.56 |

MAE vx / vy / wz changed by -6% / -37% / +1% on demo and -13% / -35% / -8% on stress. Lateral achieved/commanded on
demo: +0.5 m/s 0.63 (teacher 0.54), -0.5 m/s 0.94 (teacher 0.56). Mean power rose 19.3% on demo and 13.6% on stress.
Peak hip torque was higher than the teacher's in both profiles. Foot swing peak was 1.33 / 1.25 and calf lift
1.31 / 1.21 times the teacher (demo / stress). Sideways drift in moving segments with zero lateral command: -12.5 mm/s
on demo (teacher +4.9) and -22.1 mm/s on stress (teacher -12.5). These single-run differences are descriptive.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.

Reproduce the four architecture-ablation candidates, V2n s81 and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-architecture-ablation-candidates).
This is a one-repeat C++ deployment check on rigid ground, not a statistically reliable ranking, a sand test or
hardware validation. No physical robot was actuated.
