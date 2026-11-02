# unitree_mujoco comparison: `/home/harry/go2_sand/results/deploy_mujoco/nrd_candidates_20261102/runs`

MAE = mean |measured - command| over the completed segments (lower is better). falls = runs that fell or did not finish. tau = /lowstate tau_est under the policy.

## Profile `demo_final`

| policy | runs | falls | MAE vx [m/s] | MAE vy [m/s] | MAE wz [rad/s] | vs `unitree_rl_mjlab` (vx / vy / wz) | max tilt [deg] | peak tau hip / thigh / calf [N m] | power [W] | target rate [rad/s] |
|---|---|---|---|---|---|---|---|---|---|---|
| `nrd_combo` | 1 | 0 | 0.078 | 0.058 | 0.121 | -7% / -4% / -3% | 3.2 | 7.1 / 13.1 / 24.1 | 19 | 1.50 |
| `nrd_ensemble` | 1 | 0 | 0.079 | 0.062 | 0.119 | -5% / +3% / -5% | 3.8 | 6.7 / 13.6 / 25.6 | 18 | 1.44 |
| `nrd_softcode` | 1 | 0 | 0.085 | 0.061 | 0.122 | +2% / +3% / -3% | 4.0 | 6.8 / 11.9 / 24.3 | 18 | 1.44 |
| `unitree_rl_mjlab` | 1 | 0 | 0.083 | 0.060 | 0.125 | +0% / +0% / +0% | 3.4 | 7.7 / 12.6 / 24.3 | 18 | 1.47 |

Achieved / commanded on each commanded axis (mean of the repeats):

| segment | command (vx, vy, wz) | `nrd_combo` | `nrd_ensemble` | `nrd_softcode` | `unitree_rl_mjlab` |
|---|---|---|---|---|---|
| stand | (+0.0, +0.0, +0.0) | drift 0.00 | drift 0.00 | drift 0.00 | drift 0.00 |
| forward_0.5 | (+0.5, +0.0, +0.0) | 0.71 | 0.73 | 0.71 | 0.71 |
| forward_0.8 | (+0.8, +0.0, +0.0) | 0.84 | 0.83 | 0.82 | 0.81 |
| lateral_+0.5 | (+0.0, +0.5, +0.0) | 0.52 | 0.52 | 0.49 | 0.53 |
| lateral_-0.5 | (+0.0, -0.5, +0.0) | 0.65 | 0.57 | 0.57 | 0.56 |
| turn_+0.8 | (+0.0, +0.0, +0.8) | 0.51 | 0.51 | 0.51 | 0.49 |
| turn_-0.8 | (+0.0, +0.0, -0.8) | 0.50 | 0.52 | 0.53 | 0.52 |
| backward_0.5 | (-0.5, +0.0, +0.0) | 0.73 | 0.70 | 0.67 | 0.67 |
| fwd+turn | (+0.6, +0.0, +0.6) | 0.85 / 0.64 | 0.84 / 0.65 | 0.83 / 0.65 | 0.83 / 0.61 |
| stop | (+0.0, +0.0, +0.0) | drift 0.00 | drift 0.00 | drift 0.00 | drift 0.00 |

## Profile `stress`

| policy | runs | falls | MAE vx [m/s] | MAE vy [m/s] | MAE wz [rad/s] | vs `unitree_rl_mjlab` (vx / vy / wz) | max tilt [deg] | peak tau hip / thigh / calf [N m] | power [W] | target rate [rad/s] |
|---|---|---|---|---|---|---|---|---|---|---|
| `nrd_combo` | 1 | 0 | 0.084 | 0.071 | 0.136 | -13% / -2% / -5% | 5.8 | 7.5 / 17.2 / 26.2 | 31 | 1.78 |
| `nrd_ensemble` | 1 | 0 | 0.093 | 0.072 | 0.140 | -4% / -1% / -2% | 7.0 | 7.0 / 18.6 / 26.3 | 29 | 1.72 |
| `nrd_softcode` | 1 | 0 | 0.099 | 0.069 | 0.146 | +2% / -5% / +2% | 6.7 | 7.5 / 17.3 / 26.5 | 29 | 1.71 |
| `unitree_rl_mjlab` | 1 | 0 | 0.096 | 0.073 | 0.143 | +0% / +0% / +0% | 6.2 | 8.1 / 17.9 / 27.5 | 30 | 1.74 |

Achieved / commanded on each commanded axis (mean of the repeats):

| segment | command (vx, vy, wz) | `nrd_combo` | `nrd_ensemble` | `nrd_softcode` | `unitree_rl_mjlab` |
|---|---|---|---|---|---|
| stand | (+0.0, +0.0, +0.0) | drift 0.00 | drift 0.00 | drift 0.00 | drift 0.00 |
| forward_1.0 | (+1.0, +0.0, +0.0) | 0.87 | 0.86 | 0.85 | 0.84 |
| turn_+1.0 | (+0.0, +0.0, +1.0) | 0.62 | 0.61 | 0.61 | 0.60 |
| turn_-1.0 | (+0.0, +0.0, -1.0) | 0.61 | 0.62 | 0.62 | 0.62 |
| diagonal | (+0.5, +0.5, +0.0) | 0.80 / 0.60 | 0.78 / 0.61 | 0.77 / 0.60 | 0.77 / 0.64 |
| fwd1.0+turn- | (+1.0, +0.0, -0.5) | 0.88 / 0.74 | 0.87 / 0.71 | 0.85 / 0.69 | 0.86 / 0.72 |
| lat-+turn+ | (+0.0, -0.5, +0.5) | 0.62 / 0.56 | 0.58 / 0.54 | 0.63 / 0.55 | 0.58 / 0.53 |
| sprint_1.0 | (+1.0, +0.0, +0.0) | 0.87 | 0.86 | 0.85 | 0.84 |
| reverse_-0.5 | (-0.5, +0.0, +0.0) | 0.75 | 0.70 | 0.67 | 0.67 |
| stop | (+0.0, +0.0, +0.0) | drift 0.00 | drift 0.00 | drift 0.00 | drift 0.00 |
