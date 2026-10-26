# Go2 velocity: NeDM Study 4 fine-tuned policy (NRDLab base, fine-tuned for CRM soil)

NeDM Study 4 (Kyle Sha; [uwsbel/NeDM](https://github.com/uwsbel/NeDM), branch `kyle/quadruped-pipeline`) takes the NRDLab base policy ([`../../nrdlab_base/velocity`](../../nrdlab_base/velocity/README.md)) and fine-tunes it for a Go2 on Chrono CRM granular soil:

1. It records the base policy as it walks on CRM.
2. It trains a neural reduced model of the robot on that soil.
3. It fine-tunes the policy with PPO inside that model, for 1000 iterations.
4. It scores every result in full Chrono, paired against the base policy.

The fine-tune changes the weights by about 5.5 % and keeps the network and the contract. Thus `config.yaml` here is the base config with only `model_path` changed.

| File | Content |
|---|---|
| `config.yaml` | Single-policy deploy config (`model_path: .../nrdlab_finetuned/velocity/policy.onnx`) |
| `get_policy.py` | Downloads `policies/recipe_iteration1000/<run>/policy_ft.pt` from the gated Hugging Face dataset [`ksha23/nedm-study4-go2-crm`](https://huggingface.co/datasets/ksha23/nedm-study4-go2-crm) at revision `66caa72b`. It checks the sha256 and exports `policy.onnx` with `scripts/pt_to_onnx.py --check` |
| `policy.onnx`, `policy_source.json` | Written by `get_policy.py`. They are not in git (`.gitignore`), because the dataset author gates the files |

## Get the policy

1. Request access on the dataset page. Then log in with `hf auth login`, or set `HF_TOKEN`.
2. Run `get_policy.py` on the host or in the container. It needs `pip install huggingface_hub torch onnx onnxruntime`; CPU torch is enough:

   ```bash
   python3 src/legged_rl_deploy/policies/go2/nrdlab_finetuned/velocity/get_policy.py                    # standard_s9
   python3 src/legged_rl_deploy/policies/go2/nrdlab_finetuned/velocity/get_policy.py --run standard_s8  # the study's reference seed
   ```

   `--run` selects one of the ten recipe runs, one for each surrogate seed. The default is `standard_s9`, the best of the ten in the check below. `--pt <file>` uses a local `policy_ft.pt` instead of a download.
3. Run it like the other policies: see "Simulation: Go2 velocity policies" in the [root README](../../../../README.md). `scripts/sim_deploy/eval_go2_velocity.sh` includes it when `policy.onnx` exists.

## Source and license

- Dataset `ksha23/nedm-study4-go2-crm`, revision `66caa72be7118c78a13262d0fb90d14a393980fe` (2026-09-29). Its `MANIFEST.tsv` gives the sha256 of each file; `get_policy.py` pins them.
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
| this folder, `standard_s9` | 0.042 / 0.038 / 0.065 | 0.041 / 0.049 / 0.076 | 22.7 / 22.4 / 30.4 | 69 / 113 |
| this folder, all ten runs | 0.042 to 0.072 / 0.038 to 0.075 / 0.063 to 0.099 | 0.041 to 0.066 / 0.041 to 0.069 / 0.075 to 0.121 | up to 23.7 / 23.7 / 38.2 | 69 to 84 / 113 to 152 |

- **Yaw.** The fine-tune removes the base policy's yaw drift at zero command: 0.00 to 0.03 rad/s, against 0.04 to 0.08 rad/s for the base. The wz error is about half that of `unitree_rl_mjlab` and less than half that of the base.
- **Speed.** On this rigid ground the fine-tuned policies walk up to 19 % faster than a forward command (`standard_s9`: up to 9 %). The base walks at 0.98 of the command and `unitree_rl_mjlab` at 0.71 to 0.84.
- **Effort.** They walk like the base policy: about 4 times the mechanical power of `unitree_rl_mjlab`. In `stress`, the hip and thigh torques of some runs reach the 23.7 N m limit.
- **Weakest run.** `standard_s6` is the weakest run here, as in the study.
