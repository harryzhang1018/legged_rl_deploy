# Go2 velocity: NRD lateral finetune, architecture ablation 1T, seed 81 (EXPERIMENTAL)

**Status: experimental architecture-ablation policy. It FAILS the Chrono sand selection rule (Chrono label
NOT_ELIGIBLE). On flat rigid MuJoCo ground it has 0 falls and passes the rigid tracking-loss rule and the C++
deploy-stack gates, but its power is above the prior-study limit. Not tested on hardware.**

This package is an ablation reference, not a sand candidate. It shows what recipe V2 gives when the frozen NRD is one
network without a contact head. Compare it with [V2n s81](../../nrd_finetune_lateral_v2n_seed81/velocity/README.md),
which used the same recipe and PPO seed in the three-transformer NRD.

PPO seed 81, iteration 299, initialized from the unchanged `unitree_rl_mjlab` actor and optimized inside one
frozen 1T NRD: `go2_1t_s62` (loader SHA256 `f3a2300d...`). The 1T is one causal transformer (6 layers, 8 heads, no
bias, token width 184). It has no collision network, no contact network and no contact head. One token per 20 ms step
holds the 37-channel state, the 12 joint targets and 3 ground features. The model reads the last 4 steps. It has
2,493,384 parameters, +0.68 % of the study's size target of 2,476,551 (the 3T's 2,473,582 parameters plus its 2,969
normalization numbers). The NRD has no contact output. Thus the PPO rewards and critic get the four foot-contact flags
from a frozen foot-height rule (`foot_rule_v1`, SHA256 `644c7ac9...`) on the predicted foot height and vertical foot
speed.

Recipe V2 of study `lateral_stuck_20261108` (`v2.json`, SHA256 `162b4883...`) is the recipe of V2n s81. The PPO
config differs from V2n s81 only in the NRD path, the NRD SHA256 and the lineage track. The PPO code is the V2n code
(`8e08e2544f0d`) plus the architecture port (snapshot `1baaae85b223`). For one-network NRDs the start states also
carry the 3 previous joint targets. PPO ran on an Euler A100 (job 123519). The NRD weight digest was the same before
and after PPO (`5868a11b...`).

The NRD trains on the same data as the V2n NRD (FRESH-b): equal source hashes, split manifest `9ba6dce9` and mixture.
Sampling shares: rigid MuJoCo 0.5, Chrono CRM production 0.25, lateral Chrono CRM sand of study
`lateral_stuck_20261108` 0.25 (480 training shards). The held-out lateral TEST folder is excluded. All data come from
the original fixed teacher (`c58a3494`). No fine-tuned-policy trajectories were used. Training: 13,500 updates from a
normal(0, 0.02) start, no ridge prefit, Euler A100 (job 123465). NRD seed 62 was picked by the pre-registered rule
(lowest validation stall gap among seeds 61 to 64): validation gap 0.143 (limit 0.257), held-out gap 0.156
(limit 0.239). This NRD fails G1, the rigid accuracy rules. Direct physics was used for evaluation, not actor
optimization.

Goal: the goal of recipe V2 is unchanged. It is to fix the lateral foot-drag stall seen on the real robot (see the
V2n s81 README). The ablation keeps the recipe, the NRD data, the PPO seed and the parameter budget (within 3 %). It
changes the NRD design and the settings that come with it (the last 4 joint targets as input, foot flags from a rule,
no ridge prefit, another stage-A learning-rate schedule). PPO also ran on another GPU type (A100; V2n s81: RTX A4500).

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

ONNX SHA256: `59d0251a7c67b4e623c6fd052707ae0b50ee006ce458242b6c7debfc41e6ad7f`.

Fresh parity checks passed on 4,000 recorded observations (tolerance `1e-4`):
ONNX versus Torch max error `1.43e-06`; deploy-policy mirror versus Torch
max error `6.40e-05`. The larger mirror error includes observation
reconstruction, including phase.

## Chrono CRM sand evidence (simulation only)

Teacher = the unchanged `unitree_rl_mjlab` actor in the same 18 AMD MI210 jobs (all 22 roles in each job). Stuck time
= failure-penalized lateral STUCK time, as for V2n s81. Lower is better. Realistic cells = medium flat, medium uneven
and firm uneven sand, 8 commands each, repeats r0 and r2.

| Check (selection suite, 48 realistic episodes) | This policy | Teacher | Limit | Result |
|---|---|---|---|---|
| Stuck-time ratio (selection score) | 0.479 | 1 | - | better |
| Stuck-time ratio, medium flat / medium uneven / firm uneven | 0.30 / 0.72 / 0.35 | 1 | - | better |
| Early stops, of 48 | **16** (13 falls, 3 bed exits) | 2 (2 falls) | teacher + 2 = 4 | **fail** |
| Wrong-way holds (net progress below -0.10 m) | **4** | 0 | teacher + 1 = 1 | **fail** |
| Realistic repeats present, of 6 blocks | 6 | 6 | 6 | pass |
| Soft-sand cells, not scored: early stops, of 16 (flag only) | 12 (12 falls) | 6 (4 falls, 2 bed exits) | - | worse |

The policy FAILS the sand pass rule on early stops and on wrong-way holds. Early stops by cell: medium uneven 8 falls
(of 16 episodes), medium flat 4 falls and 1 bed exit, firm uneven 1 fall and 2 bed exits. The per-cell ratios are
computed from `aggregate_ablsel1.json`.

No 1T policy was eligible. PPO seeds 82 and 83 scored 0.353 and 0.371 with 11 and 13 early stops. The frozen rule
gives no substitute, so the 1T design has no pick. The held-out suite_v2 was not run for this policy.

The study diagnosis (3 1T policies, realistic cells) found the same failure for all of them. All 31 falls were on
commands with a leftward part. All 9 bed exits were at the right edge. The picked 1T NRD moves the robot about
59 mm/s too far to the left (3T NRD: 29 mm/s). PPO cancels this inside the NRD by a steer to the right. In Chrono
this becomes a real drift to the right: 38 to 69 mm/s on firm ground (3T: 19 to 42 mm/s). Under a left command the
robot slides back, sinks on its trailing feet and rolls over. Under a right command it leaves the bed at the right
edge. No NRD, the 3T included, predicts these falls. This cause is not proven by an experiment.

## Rigid MuJoCo development evidence

On the 120-path MuJoCo rigid development suite (paired with the teacher, 10,000 path-bootstrap draws):
failure-penalized tracking loss ratio **0.936** (95 % range 0.918 to 0.954), lateral-path loss ratio 0.77 (0.73 to
0.82), 0 falls of 120 (teacher 0). Axis loss ratios vx / vy / wz: 1.03 / 0.83 / 0.93. The vx ratio is slightly worse
than the teacher (95 % range 1.00 to 1.05). The constant, velocity-step and stop-and-go command families are also
worse than the teacher (1.10, 1.04, 1.09; each 95 % range above 1). Power is 1.20 times the teacher value (95 % range
1.18 to 1.22), above the prior-study limit of 1.15.

Real-robot indicators named by the user, from the stored traces of the same suite (ratio of means, 95 % range):

| Indicator | This policy | Teacher | Ratio |
|---|---|---|---|
| Mechanical power (120 paths) | 22.4 W | 18.7 W | 1.20 (1.18 to 1.22) |
| Foot swing peak (112 paths) | 65.4 mm | 47.1 mm | 1.39 (1.36 to 1.42) |
| Calf lift (112 paths) | 46.8 mm | 35.0 mm | 1.34 (1.31 to 1.36) |
| Sideways drift, zero lateral command, 84 paths (+ = left) | -14.7 mm/s (-16.4 to -12.9) | +7.6 mm/s | - |
| Lateral speed / command, +y / -y | 0.81 / 1.01 | 0.67 / 0.67 | - |

Both indicators are higher than the teacher's. The drift to the right is 22.2 mm/s more than the teacher's (95 %
range 19.8 to 24.6). The V2 reward asks for an 80 mm swing peak in every NRD. Thus the indicators are at most a
necessary sign. Over 3 PPO seeds they do not separate the 1T from the 3T (Welch test: power p = 0.65, foot swing
peak p = 0.45).

## Compared with V2n s81

V2n s81 = study role `abl3t_s81` (3T NRD FRESH-b, original PPO code, RTX A4500).

| Metric | This policy (1T) | V2n s81 (3T) | Same run |
|---|---|---|---|
| Chrono selection score | 0.479 | 0.208 | same 18 jobs (`ablsel1`) |
| Chrono early stops, of 48 (teacher 2) | 16 (13 falls, 3 bed exits) | 3 (2 falls, 1 bed exit) | same jobs |
| Chrono wrong-way holds (teacher 0) | 4 | 0 | same jobs |
| Sand selection rule | fail | pass (3T pick) | same jobs |
| Chrono held-out suite_v2 | not run | NOT_CONFIRMED, ratio 0.215 | - |
| Rigid dev120 loss ratio | 0.936 (0.918 to 0.954) | 0.854 (0.836 to 0.874) | same tag (`ablsel1`) |
| Rigid lateral-path loss ratio | 0.77 | 0.62 | same tag |
| Rigid falls, of 120 | 0 | 0 | same tag |
| Rigid power x base | 1.20 | 1.22 | same tag |
| Rigid foot swing peak / calf lift x base | 1.39 / 1.34 | 1.40 / 1.36 | same tag |
| Rigid drift, zero lateral command (base +7.6 mm/s) | -14.7 mm/s | +1.9 mm/s | same tag |
| C++ deploy power x base, demo / stress | 1.16 / 1.10 | 1.22 / 1.15 | same 2026-11-19 job |
| C++ deploy MAE vx / vy / wz, demo | 0.085 / 0.042 / 0.130 | 0.070 / 0.041 / 0.120 | same job |

All rows except held-out suite_v2 compare the two policies in the same job or tag, against the same teacher run.
Power and lift are almost the same on rigid ground and in the deploy stack. Rigid tracking is worse for the 1T (loss
ratio 0.936 against 0.854, the 95 % ranges do not overlap), and with zero lateral command it drifts to the right
(-14.7 against +1.9 mm/s). On sand the 1T stopped early about 5 times as often.

## Limits

- FAILS the Chrono sand selection rule: 16 early stops (limit 4) and 4 wrong-way holds (limit 1). Chrono label
  NOT_ELIGIBLE. Not run on held-out suite_v2.
- All 3 1T policies (PPO seeds 81 to 83) fail the rule. This package is an ablation reference only.
- One NRD seed (62). The seed rule picked the most left-biased seed in every design, the 3T included. A user decision
  on this rule is still open. Another pick could change the size or sign of the drift.
- The picked 1T NRD fails G1 (rigid velocity RMSE 0.0458 > 0.0444 m/s, rigid roll/pitch RMSE 0.0259 > 0.0242 rad).
  The 3T NRD of V2n s81 (FRESH-b) also fails G1.
- The 1T NRD trained on an Euler A100 (job 123465), FRESH-b on an AMD MI350X. No 3T NRD control covers this
  platform difference.
- No contact head: in closed loop on recorded joint targets (lateral-sand validation windows, first 1 s), the
  foot-height rule of this NRD agrees with the recorded contact labels 0.855 of the time (mean of the four 1T seeds
  0.856). The collision switches of the 3T NRD (FRESH-b) agree 0.955 of the time.
- The NRDs, trained only on teacher data, predict no falls for this gait. The falls are found only in Chrono.
- Soil levels are study levels, not measured sand. No physical robot was actuated.
- These are development and selection simulation suites, not hardware qualification.

This policy is not a candidate for a sand hardware test.

Study report SHA256 (`STUDY_REPORT.md`, round 1):
`87e8072f62ca8949e150b6fbd4ee9b1b3968a69ea12b4585fac78d3951876155`.
Round 2 (`STUDY_REPORT_ROUND2.md`): `6773562a60bcf3392c3aae6969e13e400c05a6675cdfa60790031eaca95c1ae0`.
Packaging receipts and parity logs are archived outside Git at
`/home/harry/go2_sand/results/arch_ablation_20261123_pr/`. The study is at `/home/harry/arch_ablation_20261118/`.
The MuJoCo replay video of the demo run is
`/home/harry/arch_ablation_20261118/go2_sand/mujoco_rigid/videos5/4_1t_s81.mp4` (V2n s81: `1_v2n_s81.mp4`; side
views of the five policies and the base policy in segment lateral_+0.5: `0_all_five_lateral.mp4`). The videos show flat rigid ground, not sand and not the real robot.

## Check in unitree_mujoco (2026-11-19)

The package was renamed on 2026-11-23 from the checked alias `rigidcheck_abl1t_s81`; ONNX bytes and all control
settings are unchanged from the package checked below.

The exact packaged ONNX, its teacher and V2n s81 ran in one job through the existing C++ deploy stack in MuJoCo on
flat `go2/scene.xml`: one `demo_final` (31 s) and one `stress` (30 s) run per policy. All three completed both profiles
with zero falls, zero non-finite policy outputs and no command-plan warnings; real-time factors were approximately
1.000. The tool gates D1 to D5 passed. The deployment config and physics settings were identical apart from the
model path.

| Policy / profile | MAE vx / vy / wz | Peak torque hip / thigh / calf [N m] | Power [W] | Mean target rate [rad/s] | Max tilt [deg] |
|---|---|---|---:|---:|---:|
| mjlab / demo_final | 0.082 / 0.059 / 0.125 | 7.7 / 12.6 / 24.2 | 18.5 | 1.470 | 3.46 |
| 1T81 / demo_final | 0.085 / 0.042 / 0.130 | 9.1 / 15.8 / 25.1 | 21.4 | 1.620 | 5.25 |
| mjlab / stress | 0.097 / 0.073 / 0.144 | 8.2 / 17.8 / 29.0 | 29.9 | 1.742 | 6.43 |
| 1T81 / stress | 0.091 / 0.052 / 0.139 | 7.6 / 18.9 / 25.2 | 32.8 | 1.901 | 6.02 |

vy MAE improved by 29 % in both profiles. vx / wz MAE were slightly worse on demo (+3 % / +4 %) and better on stress
(-6 % / -3 %). Lateral achieved/commanded on demo: +0.5 m/s 0.59 (teacher 0.54), -0.5 m/s 0.80 (teacher 0.56).
Mean power rose 15.5 % on demo and 10.0 % on stress. Foot swing peak x teacher: 1.31 on demo, 1.23 on stress. Calf
lift x teacher: 1.26 and 1.18. These single-run differences are descriptive.

MAE uses vx/vy in m/s and wz in rad/s, excluding the first second of each
segment. Power is mean sum of absolute joint mechanical powers; target rate is
mean per-joint absolute target variation per second. These are descriptive
single-run values, not the failure-penalized research tracking loss above.

Reproduce the four architecture-ablation candidates, V2n s81 and their teacher with the explicit-label command in
[scripts/sim_deploy](../../../../scripts/sim_deploy/README.md#nrd-architecture-ablation-candidates).
This is a one-repeat C++ deployment check on rigid ground, not a statistically reliable ranking, a sand test or
hardware validation. No physical robot was actuated.
