# Legged RL Deploy

`legged_rl_deploy` deploys learned policies on top of `unitree_lowlevel` for Unitree Go2 and G1 robots.

It provides:

- single-policy deployment from a single `config.yaml`
- multi-policy deployment with gamepad-triggered switching via `fsm`
- ONNX Runtime and LibTorch inference backends
- local-file and Redis-based mimic motion sources
- sample policies and deployment configs for Go2 and G1

## Overview

This package inherits the low-level control loop, safety logic, and hardware adapters from [`unitree_lowlevel`](../unitree_lowlevel/README.md). The RL policy only becomes active after the low-level controller enters `HighController`.

The deployed config is passed directly to:

```bash
ros2 run legged_rl_deploy legged_rl_deploy_node <network-interface> <config-file>
```

Two config styles are supported:

- Single-policy config: top-level `policy:` section
- Multi-policy config: top-level `fsm:` section with multiple sub-policies and gamepad transitions

Video demo:

- https://renkunzhao.github.io/present/slides/phd-interview/#/5

## Policy Layout

The repository already includes several example policies:

```text
policies/
├── go2/
│   ├── My_unitree_go2_gym/
│   │   ├── trot/
│   │   ├── hop/
│   │   ├── handstand/
│   │   ├── legstand/
│   │   ├── spring_jump/
│   │   └── multi-policies.yaml
│   ├── mjlab/
│   │   ├── velocity/
│   │   ├── hop/
│   │   ├── mimic/
│   │   └── multi-policies.yaml
│   ├── unitree_rl_lab/
│   │   └── velocity/
│   ├── unitree_rl_mjlab/
│   │   └── velocity/
│   ├── nrdlab_base/
│   │   └── velocity/
│   ├── nrdlab_finetuned/
│   │   └── velocity/
│   └── aba/
│       └── velocity/
└── g1/
    ├── velocity/
    │   ├── unitree_rl_mjlab/
    │   └── mjlab/
    ├── mimic/
    │   ├── unitree_rl_lab/
    │   │   ├── dance_102/
    │   │   └── gangnam_style/
    │   ├── unitree_rl_mjlab/
    │   │   └── dance1_subject2/
    │   ├── mjlab/
    │   │   └── dance1_subject1/
    │   ├── whole_body_tracking/
    │   │   └── jumps1_subject1/
    │   └── TWIST2/
    ├── aba/
    │   ├── velocity/
    │   ├── dance102/
    │   ├── jumps1_subject1/
    │   └── multi-policies.yaml
    └── multi-policies.yaml
```

Included policy sources referenced by this repo:

| Source | Link |
| --- | --- |
| unitree_rl_lab | [github.com/unitreerobotics/unitree_rl_lab](https://github.com/unitreerobotics/unitree_rl_lab) |
| My_unitree_go2_gym | [github.com/yusongmin1/My_unitree_go2_gym](https://github.com/yusongmin1/My_unitree_go2_gym) |
| mjlab | [github.com/mujocolab/mjlab](https://github.com/mujocolab/mjlab) |
| unitree_rl_mjlab | [github.com/unitreerobotics/unitree_rl_mjlab](https://github.com/unitreerobotics/unitree_rl_mjlab) |
| rl_sar (`robot_lab` Go2, used as the NRDLab base policy) | [github.com/fan-ziqi/rl_sar](https://github.com/fan-ziqi/rl_sar) |
| NeDM Study 4 (fine-tunes of the NRDLab base policy) | [huggingface.co/datasets/ksha23/nedm-study4-go2-crm](https://huggingface.co/datasets/ksha23/nedm-study4-go2-crm) |

Some configs in this repo are experiment-specific derivatives or internally retargeted motions.

## Dependencies

### Required

- [`unitree_lowlevel`](https://github.com/Renkunzhao/unitree_lowlevel) built in the same workspace
- ROS 2 workspace already initialized and buildable with `colcon`

### Recommended for the bundled policies

Most bundled policies use `backend: ort`, so ONNX Runtime is effectively required for the default examples:

```bash
cd $WORKSPACE/src/legged_rl_deploy
./scripts/get_ort.sh
```

This downloads ONNX Runtime into `thirdparty/onnxruntime`.

### Optional: LibTorch

Use LibTorch only if your policy config sets `backend: libtorch` or `backend: torch`.

Helper script:

```bash
cd $WORKSPACE/src/legged_rl_deploy
./scripts/get_torch.sh
```

Platform-specific notes are in [LibTorch.md](LibTorch.md).

### Optional: Redis mimic source

Redis support is compiled in only when `hiredis` is available at build time:

```bash
sudo apt install -y libhiredis-dev redis-tools
```

This is only needed for configs using `mimic.params.source: redis`, such as `policies/g1/mimic/TWIST2/config.yaml`.

## Build

Clone the repository into the workspace:

```bash
cd unitree_ws/src
git clone https://github.com/Renkunzhao/legged_rl_deploy.git
```

If you plan to use:

- ONNX Runtime: run `./scripts/get_ort.sh` first
- LibTorch: install it and set environment variables as described in [LibTorch.md](LibTorch.md) before building
- Redis mimic: install `libhiredis-dev` before building

Then build:

```bash
cd unitree_ws
source /opt/ros/<ros-distro>/setup.bash
colcon build --packages-up-to legged_rl_deploy --cmake-args -DPython3_EXECUTABLE=/usr/bin/python3
source install/setup.bash
```

> Note: The explicit `Python3_EXECUTABLE` avoids clean-build failures when `python3` points to a Conda environment without the ROS build dependencies.

## Running

### Hardware preparation

`legged_rl_deploy` still relies on the low-level controller setup from `unitree_lowlevel`.

For Go2 hardware, stop the default controller once after each boot:

```bash
source src/unitree_lowlevel/scripts/setup.sh <network-interface> <ros-distro>
$WORKSPACE/build/unitree_sdk2/bin/go2_stand_example <network-interface>
```

For G1 hardware, enter `Debug Mode` first as described in the [`unitree_lowlevel` documentation](../unitree_lowlevel/README.md).

### Recommended launcher

From the workspace root, use the helper wrapper:

```bash
./src/legged_rl_deploy/scripts/run.sh <network-interface> <ros-distro> ros2 run legged_rl_deploy legged_rl_deploy_node <network-interface> <config-file>
```

The wrapper:

- sources `unitree_lowlevel/scripts/setup.sh`
- sets `CMAKE_PREFIX_PATH` and `LD_LIBRARY_PATH` for Torch on x86_64
- sets the corresponding Torch paths from Python on aarch64

### Runtime behavior

The node inherits the same safety confirmation as `unitree_lowlevel`:

```text
WARNING: Make sure the robot is hung up or lying on the ground.
Press Enter to continue...
```

In practice, the flow is:

1. Start the node
2. Confirm the safety prompt
3. Use the low-level controller gamepad flow to reach `FixStand`
4. Press `START` to enter `HighController`
5. The RL policy then takes control

If you are using a multi-policy config, policy switching is handled by the `fsm.policies.*.transitions` entries in the YAML file.

## Simulation: Go2 velocity policies

These Go2 velocity policies run in [`unitree_mujoco`](https://github.com/Renkunzhao/unitree_mujoco) (Kunzhao Ren's fork) with the same node and gamepad flow as on the robot.
They, the `gait_phase` term and `scripts/sim_deploy` are in the fork [harryzhang1018/legged_rl_deploy](https://github.com/harryzhang1018/legged_rl_deploy) (`master`): clone it in place of the upstream repo in [Build](#build).

| Config | Policy | Observation | Command clip (vx, vy, wz) |
| --- | --- | --- | --- |
| `policies/go2/unitree_rl_mjlab/velocity/config.yaml` | unitree_rl_mjlab `Unitree-Go2-Flat`, 10k iterations | 47, with `gait_phase` | [-0.5, 1], [-0.5, 0.5], [-1, 1] |
| `policies/go2/nrdlab_base/velocity/config.yaml` | NRDLab Go2 base policy, not fine-tuned (rl_sar `robot_lab` Go2) | 45 | [-1, 1] on each axis |
| `policies/go2/nrdlab_finetuned/velocity/config.yaml` | NeDM Study 4 fine-tune of the base policy (surrogate seed 9) | 45 | [-1, 1] on each axis |

1. From the workspace root, clone the simulator before the `unitree_lowlevel` build. `colcon-config.sh` builds `src/unitree_mujoco/simulate`, but it does not clone it. Then get ONNX Runtime before the first `colcon build` of `legged_rl_deploy`, because CMake looks for it only at configure time:

   ```bash
   git clone https://github.com/Renkunzhao/unitree_mujoco.git src/unitree_mujoco
   ./src/unitree_lowlevel/scripts/colcon-config.sh <ros-distro> Release
   ./src/legged_rl_deploy/scripts/get_ort.sh
   ```

   Then build `legged_rl_deploy` as in [Build](#build).

2. Connect a gamepad. Keep `use_joystick: 1` (the default) in `src/unitree_mujoco/simulate/config.yaml`.
3. Terminal 1, from the workspace root, start the simulator:

   ```bash
   source src/unitree_lowlevel/scripts/setup.sh lo <ros-distro>
   $WORKSPACE/src/unitree_mujoco/simulate/build/unitree_mujoco -r go2 -s scene.xml -i 0 -n lo
   ```

4. Terminal 2, from the workspace root, start the policy (use another config of the table for another policy):

   ```bash
   ./src/legged_rl_deploy/scripts/run.sh lo <ros-distro> ros2 run legged_rl_deploy legged_rl_deploy_node lo \
     src/legged_rl_deploy/policies/go2/unitree_rl_mjlab/velocity/config.yaml
   ```

5. Press Enter at the safety prompt. Then `L2 + A` stands the robot up (`FixStand`), and `START` gives control to the policy. The left stick commands vx and vy, and the right stick commands wz. `SELECT` returns to `FixStand`.

Scripted evaluation, one command (no gamepad; set `use_joystick: 0` first). From the workspace root:

```bash
./src/legged_rl_deploy/scripts/sim_deploy/eval_go2_velocity.sh
```

It runs each policy above on two command profiles in a headless simulator, then writes a comparison table (`compare.md`: falls, tracking error, torque, power). See [scripts/sim_deploy/README.md](scripts/sim_deploy/README.md).

Notes:

- `unitree_lowlevel` sets each stick axis to 0 while |value| < 0.5, and it does not rescale larger values. Thus each command axis is 0 or at least 0.5 in magnitude. For `unitree_rl_mjlab`, vy is 0 or ±0.5, and backward vx is -0.5.
- `gait_phase` (new observation term, unitree_rl_mjlab): `[sin, cos](2 pi fmod(k * step_dt, period) / period)`, where `k` counts the policy steps since `START` and `step_dt = round(policy_dt / ll_dt) * ll_dt` (0.02 s here). It is `[0, 0]` while the norm of the processed `base_velocity` command is below `command_threshold`. Parameters: `params: {period: 0.6, command_threshold: 0.1}`.
- Each of these policy folders has a `README.md` with its source and its observation and action contract.

## Config Notes

Single-policy configs typically define:

- `llc_config_file`: low-level config from `unitree_lowlevel`
- `ll_dt`: low-level timestep override
- `policy.backend`: `ort`, `onnxruntime`, `torch`, or `libtorch`
- `policy.model_path`: model file path relative to `$WORKSPACE`
- `policy.observations`: observation terms and assembly layout
- `policy.actions`: output post-processing
- `policy.commands`: command preprocessing

Multi-policy configs additionally define:

- `clip_final_tau`: optional torque-mode output instead of PD targets
- `fsm.default`: policy activated when entering `HighController`
- `fsm.policies.<name>.config`: sub-policy config path
- `fsm.policies.<name>.transitions`: button mappings for switching

## Teleop and Redis Mimic

For Redis-based mimic motion:

```bash
sudo apt install -y libhiredis-dev redis-tools
```

Rebuild `legged_rl_deploy` after installing `hiredis`, otherwise Redis support will remain disabled in the compiled binary.

You can inspect Redis keys with:

```bash
redis-cli -h 127.0.0.1 -p 6379 -n 0 --scan
```

## Troubleshooting

### `backend=onnxruntime requested, but built without USE_ORT`

Run:

```bash
cd $WORKSPACE/src/legged_rl_deploy
./scripts/get_ort.sh
```

Then rebuild the package.

### `backend=libtorch requested, but built without USE_TORCH`

Install LibTorch, export the required paths from [LibTorch.md](LibTorch.md), and rebuild the package.

### Redis mimic complains that hiredis is missing

Install `libhiredis-dev`, then rebuild the package so `USE_HIREDIS` is enabled.

### CMake CUDA dialect error

If you see an error like:

```text
Target "cmTC_xxxx" requires the language dialect "CUDA17", but CMake does not know the compile flags to use to enable it.
```

Update CMake to a newer version that supports CUDA17.
