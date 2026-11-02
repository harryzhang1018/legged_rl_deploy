# Three NRD-trained Go2 policy candidates

The three actors below share the `unitree_rl_mjlab` deployment contract. PPO
fine-tuning took place inside NRD. They use 47 observations and 12 actions with no
stacked actor history. Direct-Chrono AWR policies are excluded.

| Deploy folder | Candidate | Study |
|---|---|---|
| [`nrd_combo`](../../policies/go2/nrd_combo/velocity/README.md) | `lco_E2_s1_m200` | Combined contact-label preprocessing |
| [`nrd_ensemble`](../../policies/go2/nrd_ensemble/velocity/README.md) | `xeS5abc_m175` | Uncertainty ensemble during NRD training |
| [`nrd_softcode`](../../policies/go2/nrd_softcode/velocity/README.md) | `xsc_XSb_m175` | Ground-code shift toward soft soil |

## New MuJoCo deploy evaluation

The existing `scripts/sim_deploy/eval_go2_velocity.sh` runs the actual C++ deploy
node and `unitree_lowlevel` in `unitree_mujoco`, on rigid `go2/scene.xml` ground.
The same two profiles (`demo_final`, 31 s; `stress`, 30 s) run once for the mjlab
reference and once for each candidate: eight runs. The first second of each
segment is excluded from tracking averages, as in the existing analyzer.

The configs have identical parsed settings except for `policy.model_path`,
including timing, observations, joint order, gains, action scale and command clips.
All six candidate command plans were checked before simulation and have no
dead-zone or clipping warnings. The evaluator's original fall rule is unchanged:
base-link height below 0.15 m or total tilt above 60 degrees.

See `compare.md` for the evaluator's full tables and `deploy_metrics.json` for
machine-readable results. Individual run summaries, driver plans/results and model
identities are retained in `runs/`. `runtime.json` records the evaluator revision,
simulator/low-level revisions and executable hashes. `raw_artifacts.json` pins the
large local recordings without adding CSV/NPZ files to this repository.

All **eight runs completed**, with **zero falls**, no non-finite policy outputs and no command-plan warnings. Real-time factors were approximately 1.0.

| Profile | Policy | MAE vx / vy / yaw | Change vs mjlab | Power [W] | Max tilt [deg] |
|---|---|---|---|---|---|
| demo_final | unitree_rl_mjlab | 0.0830 / 0.0599 / 0.1253 | +0.0% / +0.0% / +0.0% | 18.5 | 3.4 |
| demo_final | nrd_combo | 0.0776 / 0.0577 / 0.1212 | -6.5% / -3.6% / -3.3% | 19.3 | 3.2 |
| demo_final | nrd_ensemble | 0.0786 / 0.0617 / 0.1190 | -5.3% / +3.1% / -5.0% | 18.0 | 3.8 |
| demo_final | nrd_softcode | 0.0846 / 0.0614 / 0.1218 | +2.0% / +2.6% / -2.8% | 18.3 | 4.0 |
| stress | unitree_rl_mjlab | 0.0965 / 0.0726 / 0.1431 | +0.0% / +0.0% / +0.0% | 29.7 | 6.2 |
| stress | nrd_combo | 0.0839 / 0.0711 / 0.1355 | -13.1% / -2.0% / -5.3% | 30.9 | 5.8 |
| stress | nrd_ensemble | 0.0927 / 0.0720 / 0.1400 | -4.0% / -0.8% / -2.2% | 29.2 | 7.0 |
| stress | nrd_softcode | 0.0986 / 0.0690 / 0.1456 | +2.2% / -5.0% / +1.8% | 29.4 | 6.7 |

Errors are vx/vy in m/s and yaw rate in rad/s. Negative percentage change is better.

**Choice:** Combo remains the primary candidate. It improves all three tracking errors on both profiles, with about 4% higher mechanical power. Ensemble is a lower-power alternative, improving forward/yaw tracking but slightly worsening demo lateral error. Softcode remains an ablation: forward error is about 2% worse on both profiles, and stress yaw is also worse. One repeat per profile does not establish significance.

## Earlier CRM development screen

These are archived results from the earlier NRD candidate selection, not new CRM
simulation performed by this deploy task. Each actor shared 20 soft, 10 medium
and 10 firm paths with mjlab. Verified completed cases were reused in that screen;
it is a development shortlist, not fresh held-out validation.

| Candidate | Saved rigid120 MAE change vx / vy / yaw | CRM pooled MAE change vx / vy / yaw | CRM falls soft / medium / firm |
|---|---|---|---|
| Combo | -2.6% / -5.7% / -25.5% | -6.9% / -7.1% / -10.2% | 1 / 0 / 0 |
| Ensemble | +0.3% / +0.5% / -9.3% | -5.9% / -7.9% / -9.8% | 1 / 1 / 0 |
| Softcode | +0.9% / +0.1% / -4.0% | -2.2% / -1.1% / -7.7% | 1 / 0 / 0 |
| mjlab | reference | reference | 1 / 1 / 0 |

All three had zero falls in the saved rigid120 judge. CRM tracking uses each
actor's paired completed paths; falls and finite-bed exits are excluded from those
averages and reported separately in `crm_screen.json`. Each candidate had one
medium and one firm bed exit, versus zero medium and one firm for mjlab. This
prevents reading the smaller fall counts as an unqualified success-rate gain.
The pooled CRM score emphasizes soft soil through the 20/10/10 case counts.

Combo has the strongest nominal rigid and pooled CRM balance and an independent
earlier soft120 result (2 falls versus mjlab's 5). The ensemble's forward/yaw
confidence intervals exclude zero in the smaller screen; Combo's overlap zero.
Firm forward MAE increases by 3.8% for Combo and 2.4% for Ensemble. Softcode is a
weaker terrain-bias ablation, with medium/firm forward regressions of 5.4%/12.4%.

The earlier rigid120 judge and this C++ MuJoCo deployment check have different
simulation protocols. Their numbers should not be combined. Neither provides
hardware validation, and the MuJoCo deploy runs do not validate soft-terrain CRM.

## Reproduce

From the ROS workspace root, in its container or a native install with the built
deploy stack and `use_joystick: 0`:

```bash
./src/legged_rl_deploy/scripts/sim_deploy/eval_go2_velocity.sh -n 1 \
  -o sim_results/nrd_candidates \
  unitree_rl_mjlab=src/legged_rl_deploy/policies/go2/unitree_rl_mjlab/velocity/config.yaml \
  nrd_combo=src/legged_rl_deploy/policies/go2/nrd_combo/velocity/config.yaml \
  nrd_ensemble=src/legged_rl_deploy/policies/go2/nrd_ensemble/velocity/config.yaml \
  nrd_softcode=src/legged_rl_deploy/policies/go2/nrd_softcode/velocity/config.yaml
```

The run is a quick deployment check: one repeat per profile establishes that these
specific runs completed, rather than a statistically reliable policy ranking.
