"""Shared helpers for the headless unitree_mujoco deploy validation (sim_deploy).

* deploy config loading (``$WORKSPACE``-relative paths, like the C++ node),
* an exact float32 mirror of ``include/legged_rl_deploy/processor.h`` plus its inverse,
  used to turn a body-frame velocity command profile into gamepad stick values,
* the gamepad constants of ``unitree_lowlevel`` (key masks, deadzone, smoothing),
* low-level controller state inference from ``/lowcmd`` gains.

Only numpy and PyYAML are required (both ship with the unitree_ws image).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import yaml

# <ws>/src/legged_rl_deploy/scripts/sim_deploy/<this file>. With a symlinked src/ entry, set WORKSPACE.
WORKSPACE_DEFAULT = str(Path(os.path.abspath(__file__)).parents[4])

# unitree_lowlevel/include/unitree_lowlevel/gamepad.hpp (xKeySwitchUnion, LSB first)
KEY = {
    "R1": 0x0001, "L1": 0x0002, "start": 0x0004, "select": 0x0008,
    "R2": 0x0010, "L2": 0x0020, "F1": 0x0040, "F2": 0x0080,
    "A": 0x0100, "B": 0x0200, "X": 0x0400, "Y": 0x0800,
    "up": 0x1000, "right": 0x2000, "down": 0x4000, "left": 0x8000,
}
# LowLevelController constructor (lowlevel_controller.cpp:21-22)
GAMEPAD_SMOOTH = 0.2
GAMEPAD_DEAD_ZONE = 0.5
STICK_MAX = 1.0  # physical stick range
FIXSTAND_TICKS = 500  # smoothLerp(motiontime / 500) in FixStand / PreIDLE


def workspace() -> Path:
    """``$WORKSPACE`` (as the C++ node resolves it), default: the workspace that holds this file."""
    return Path(os.environ.get("WORKSPACE", WORKSPACE_DEFAULT))


def load_yaml(path: str | os.PathLike) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------------------- processor
class Processor:
    """float32 mirror of legged_rl_deploy::Processor (ops clip / scale / offset, in order).

    Without ``process_order`` the processor is the identity (keys are then ignored), exactly
    like ``Processor::TryLoad`` returning ``std::nullopt``.
    """

    def __init__(self, node: dict | None):
        self.order: list[str] = []
        self.params: dict[str, np.ndarray] = {}
        if not isinstance(node, dict) or node.get("process_order") is None:
            return
        self.order = [str(op) for op in node["process_order"]]
        for op in self.order:
            if op == "clip":
                self.params["min"] = _f32(node["min"])
                self.params["max"] = _f32(node["max"])
            elif op in ("scale", "offset"):
                self.params[op] = _f32(node[op])
            else:
                raise ValueError(f"unknown preprocess op: {op}")

    def forward(self, x: Sequence[float]) -> np.ndarray:
        y = np.asarray(x, dtype=np.float32).copy()
        for op in self.order:
            if op == "offset":
                y = (y + self.params["offset"]).astype(np.float32)
            elif op == "scale":
                y = (y * self.params["scale"]).astype(np.float32)
            else:
                y = np.minimum(np.maximum(y, self.params["min"]), self.params["max"])
        return y

    def inverse(self, y: Sequence[float]) -> tuple[np.ndarray, list[str]]:
        """Preimage of ``y`` (float64). Out-of-range targets of a clip op are clamped.

        Returns ``(x, notes)`` with one note per clamped component.
        """
        x = np.asarray(y, dtype=np.float64).copy()
        notes: list[str] = []
        for op in reversed(self.order):
            if op == "offset":
                x = x - self.params["offset"].astype(np.float64)
            elif op == "scale":
                s = np.broadcast_to(self.params["scale"].astype(np.float64), x.shape)
                if np.any(s == 0.0):
                    raise ValueError("scale 0 is not invertible")
                x = x / s
            else:
                lo = np.broadcast_to(self.params["min"].astype(np.float64), x.shape)
                hi = np.broadcast_to(self.params["max"].astype(np.float64), x.shape)
                xc = np.clip(x, lo, hi)
                for i in np.flatnonzero(xc != x):
                    notes.append(f"component {i}: {x[i]:+.4f} outside clip [{lo[i]:+.3f}, {hi[i]:+.3f}]"
                                 f" -> {xc[i]:+.4f}")
                x = xc
        return x, notes


def _f32(v: Any) -> np.ndarray:
    return np.atleast_1d(np.asarray(v, dtype=np.float32))


# ----------------------------------------------------------------------------- deploy config
@dataclass
class DeployConfig:
    """The parts of a legged_rl_deploy config the sim_deploy tools need."""

    path: Path
    ll_dt: float
    llc_kp: np.ndarray
    llc_kd: np.ndarray
    fixstand_q: np.ndarray
    base_velocity: Processor
    policy_kp_motor: list[np.ndarray] = field(default_factory=list)  # one per policy slot

    @property
    def fixstand_duration(self) -> float:
        return FIXSTAND_TICKS * self.ll_dt


def load_deploy_config(path: str | os.PathLike) -> DeployConfig:
    cfg_path = Path(path).resolve()
    cfg = load_yaml(cfg_path)
    ws = workspace()
    llc = load_yaml(ws / cfg["llc_config_file"])
    ll_dt = float(cfg.get("ll_dt", llc["ll_dt"]))

    slots: list[dict] = []
    if "fsm" in cfg:  # multi-policy: commands of the default policy drive the gamepad map
        policies = cfg["fsm"]["policies"]
        order = [cfg["fsm"]["default"]] + [p for p in policies if p != cfg["fsm"]["default"]]
        for name in order:
            entry = policies[name]
            slots.append(load_yaml(ws / entry["config"])["policy"] if "config" in entry
                         else entry["policy"])
    else:
        slots.append(cfg["policy"])

    kp_motor = []
    for p in slots:
        jmap = np.asarray(p["joint_ids_map"], dtype=int)
        kp = np.zeros(len(jmap))
        kp[jmap] = np.asarray(p["stiffness"], dtype=np.float64)
        kp_motor.append(kp)

    commands = slots[0].get("commands") or {}
    return DeployConfig(
        path=cfg_path,
        ll_dt=ll_dt,
        llc_kp=np.asarray(llc["kp"], dtype=np.float64),
        llc_kd=np.asarray(llc["kd"], dtype=np.float64),
        fixstand_q=np.asarray(llc["FixStand"]["q"], dtype=np.float64),
        base_velocity=Processor(commands.get("base_velocity")),
        policy_kp_motor=kp_motor,
    )


# ----------------------------------------------------------------------------- profile
@dataclass
class Segment:
    """One command segment: hold (vx, vy, wz) for ``t`` seconds."""

    t: float
    vx: float = 0.0
    vy: float = 0.0
    wz: float = 0.0
    name: str = ""


@dataclass
class StickPlan:
    """Stick values for one segment and the command they produce in the deploy stack."""

    segment: Segment
    lx: float
    ly: float
    rx: float
    effective: np.ndarray  # (vx, vy, wz) after deadzone + base_velocity processor
    warnings: list[str]

    def as_dict(self) -> dict:
        return {
            "name": self.segment.name, "t": self.segment.t,
            "requested": [self.segment.vx, self.segment.vy, self.segment.wz],
            "sticks": {"lx": self.lx, "ly": self.ly, "rx": self.rx},
            "effective": [float(v) for v in self.effective],
            "warnings": self.warnings,
        }


def load_profile(path: str | os.PathLike) -> list[Segment]:
    """Load a YAML/JSON profile: ``[{t, vx, vy, wz, name?}, ...]`` or ``{segments: [...]}``.

    ``t`` is the segment DURATION in seconds; vx, vy [m/s] and wz [rad/s] are the body-frame
    policy command (the value after ``commands.base_velocity``).
    """
    data = load_yaml(path)
    if isinstance(data, dict):
        data = data["segments"]
    segs = []
    for i, s in enumerate(data):
        seg = Segment(t=float(s["t"]), vx=float(s.get("vx", 0.0)), vy=float(s.get("vy", 0.0)),
                      wz=float(s.get("wz", 0.0)), name=str(s.get("name", f"seg{i}")))
        if seg.t <= 0:
            raise ValueError(f"segment {i}: t must be > 0")
        segs.append(seg)
    return segs


def sticks_to_command(proc: Processor, lx: float, ly: float, rx: float,
                      dead_zone: float = GAMEPAD_DEAD_ZONE) -> np.ndarray:
    """Steady-state command for constant raw sticks: deadzone, v = [ly, -lx, -rx], processor."""
    dz = [0.0 if abs(s) < dead_zone else s for s in (lx, ly, rx)]
    return proc.forward([dz[1], -dz[0], -dz[2]])


def plan_sticks(proc: Processor, seg: Segment, dead_zone: float = GAMEPAD_DEAD_ZONE,
                stick_max: float = STICK_MAX) -> StickPlan:
    """Invert the base_velocity processor and the axis map for one segment.

    Unreachable requests produce warnings: clip range (clamped), |stick| > ``stick_max``
    (clamped), and 0 < |stick| < ``dead_zone`` (the deploy zeroes it; snapped to the nearest
    reachable value, 0 or +-dead_zone).
    """
    x, notes = proc.inverse([seg.vx, seg.vy, seg.wz])
    warnings = [f"clip: {n}" for n in notes]
    raw = {"ly": x[0], "lx": -x[1], "rx": -x[2]}
    for k, s in raw.items():
        if abs(s) > stick_max:
            warnings.append(f"{k}={s:+.4f} beyond stick range +-{stick_max} -> clamped")
            s = float(np.sign(s) * stick_max)
        if 0.0 < abs(s) < dead_zone:
            snapped = 0.0 if abs(s) < 0.5 * dead_zone else float(np.sign(s) * dead_zone)
            warnings.append(f"{k}={s:+.4f} inside deadzone {dead_zone} (deploy would send 0)"
                            f" -> {snapped:+.4f}")
            s = snapped
        raw[k] = float(s) + 0.0  # no negative zeros
    eff = sticks_to_command(proc, raw["lx"], raw["ly"], raw["rx"], dead_zone) + np.float32(0.0)
    req = np.array([seg.vx, seg.vy, seg.wz])
    if np.max(np.abs(eff - req)) > 1e-4 and not warnings:
        warnings.append("effective command differs from request")
    return StickPlan(seg, raw["lx"], raw["ly"], raw["rx"], eff, warnings)


# ----------------------------------------------------------------------------- controller state
STATE_NAMES = ("IDLE", "FixStand", "PreIDLE", "HighController")  # lowlevel_controller.h


def infer_controller_state(kp: np.ndarray, kd: np.ndarray, tau: np.ndarray,
                           cfg: DeployConfig) -> str:
    """Classify a /lowcmd (motor order, 12 joints) into the LowLevelController state.

    FixStand and PreIDLE share the go2.yaml gains and are reported as 'FixStand'. A policy
    whose stiffness equals the go2.yaml kp cannot be told apart from FixStand.
    """
    if np.all(kp == 0.0):
        if np.allclose(kd, 3.0):
            return "EStop"
        if np.all(kd == 0.0) and np.all(tau == 0.0):
            return "IDLE"
        return "HighController"  # clip_final_tau: pure torque
    if np.allclose(kp, cfg.llc_kp, atol=1e-4) and np.allclose(kd, cfg.llc_kd, atol=1e-4):
        return "FixStand"
    return "HighController"


def write_json(path: str | os.PathLike, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")
