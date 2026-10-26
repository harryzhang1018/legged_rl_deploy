# Go2 velocity: NeDM Study 4 fine-tuned policy (NRDLab base, fine-tuned for CRM soil)

NeDM Study 4 (Kyle Sha; [uwsbel/NeDM](https://github.com/uwsbel/NeDM), branch `kyle/quadruped-pipeline`) takes the NRDLab base policy ([`../../nrdlab_base/velocity`](../../nrdlab_base/velocity/README.md)) and fine-tunes it for a Go2 on Chrono CRM granular soil:

1. It records the base policy as it walks on CRM.
2. It trains a neural reduced model of the robot on that soil.
3. It fine-tunes the policy with PPO inside that model, for 1000 iterations.
4. It scores every result in full Chrono, paired against the base policy.

The fine-tune changes the weights by about 5.5 % and keeps the network and the contract. Thus `config.yaml` here is the base config with only `model_path` changed.

| File | Content |
|---|---|
| `config.yaml` | Single-policy deploy config |
| `policy.onnx` | The recipe policy of surrogate seed 9 (`standard_s9`), the best of the ten in the check below. Input `obs` [1, 45], output `action` [1, 12]. sha256 `253805e575614c4648c6498dae1a894ac48adc56110ff0190a7d7299073a3ea7` |

Run it like the other policies: see "Simulation: Go2 velocity policies" in the [root README](../../../../README.md).

## Source and license

- Source: Hugging Face dataset [`ksha23/nedm-study4-go2-crm`](https://huggingface.co/datasets/ksha23/nedm-study4-go2-crm), revision `66caa72be7118c78a13262d0fb90d14a393980fe` (2026-09-29), file `policies/recipe_iteration1000/standard_s9/policy_ft.pt`. Its sha256 is `4c1c90c028fa0d06bc725629ddc0df2d5f33a997b728339d6ad6009dfd2853f4`, as in the dataset's `MANIFEST.tsv`.
- Export: `scripts/pt_to_onnx.py --config config.yaml --opset 17 --check`. The ONNX gives the same actions as the TorchScript file within 5.1e-5 on 1000 random observations and 5.7e-6 on 2200 recorded ones (onnxruntime vs torch, CPU).
- License: the fine-tuned policies are CC-BY-4.0 (the dataset's card). They are derived from the base policy, so the base policy's Apache-2.0 attribution also applies (the dataset's `NOTICE.md`, and [`../../nrdlab_base/velocity/LICENSE`](../../nrdlab_base/velocity/LICENSE)).
- Paper: Zhang and Negrut, *Learning the Right Abstraction: Neural Reduced Dynamics for Complex Robot Control*, arXiv:2608.19375.

## Contract

The same as the base policy: see the contract table in [`../../nrdlab_base/velocity/README.md`](../../nrdlab_base/velocity/README.md):
- 45-value observation and 12 actions
- 50 Hz control
- kp 20, kd 0.5
- effort limits 23.7 / 23.7 / 45.43 N m (as the study's Chrono collector)
- command clip ±1

## Check in unitree_mujoco (2026-10-25)

All ten recipe policies, the base policy and the `unitree_rl_mjlab` policy ran through `legged_rl_deploy_node` in `unitree_mujoco` (`go2/scene.xml`, flat rigid ground, MuJoCo 3.3.6), with `scripts/sim_deploy`:
- `demo_final`: 31 s, 2 runs for each policy
- `stress`: 30 s, 1 run for each policy

No policy fell (36 runs). MAE = mean |measured - command| over the profile; lower is better.

| Policy | MAE vx / vy / wz, `demo_final` | MAE vx / vy / wz, `stress` | Peak torque hip / thigh / calf, `stress` [N m] | Power, `demo_final` / `stress` [W] |
|---|---|---|---|---|
| `unitree_rl_mjlab` | 0.083 / 0.059 / 0.124 | 0.098 / 0.073 / 0.143 | 8.1 / 17.7 / 27.3 | 19 / 30 |
| `nrdlab_base` | 0.050 / 0.053 / 0.153 | 0.044 / 0.056 / 0.162 | 23.7 / 19.3 / 33.3 | 70 / 111 |
| `standard_s9` (this folder) | 0.042 / 0.038 / 0.065 | 0.041 / 0.049 / 0.076 | 22.7 / 22.4 / 30.4 | 69 / 113 |
| all ten recipe runs | 0.042 to 0.072 / 0.038 to 0.075 / 0.063 to 0.099 | 0.041 to 0.066 / 0.041 to 0.069 / 0.075 to 0.121 | up to 23.7 / 23.7 / 38.2 | 69 to 84 / 113 to 152 |

- **Yaw.** The fine-tune removes the base policy's yaw drift at zero command: 0.00 to 0.03 rad/s, against 0.04 to 0.08 rad/s for the base. The wz error is about half that of `unitree_rl_mjlab` and less than half that of the base.
- **Speed.** On this rigid ground the fine-tuned policies walk up to 19 % faster than a forward command (`standard_s9`: up to 9 %). The base walks at 0.98 of the command and `unitree_rl_mjlab` at 0.71 to 0.84.
- **Effort.** They walk like the base policy: about 4 times the mechanical power of `unitree_rl_mjlab`. In `stress`, the hip and thigh torques of some runs reach the 23.7 N m limit.
- **Weakest run.** `standard_s6` is the weakest run here, as in the study.
