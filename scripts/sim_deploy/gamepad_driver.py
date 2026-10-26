#!/usr/bin/env python3
"""Scripted Unitree gamepad for legged_rl_deploy (no person, no /dev/input/js0).

Publishes ``unitree_go/msg/WirelessController`` on ``/wirelesscontroller`` at a fixed rate
and walks the LowLevelController state machine:

  IDLE --L2+A--> FixStand --(stand-up done)--> start --> HighController
       --profile segments (sticks)--> select --> FixStand (hold) --> exit

Every transition is CONFIRMED from ``/lowcmd`` gains (see ``infer_controller_state``);
stand-up completion is checked on ``/lowstate`` joint angles and ``/sportmodestate`` height.
The command profile is converted to sticks with the inverse of the config's
``commands.base_velocity`` processor and the axis map v = [ly, -lx, -rx]; the 0.5 raw-stick
deadzone of unitree_lowlevel makes small commands unreachable (warned, snapped).

Outputs in ``--out-dir``: ``driver_plan.json`` (stick plan + warnings), ``driver_events.csv``
(wall time, sim time, event, segment, sticks, effective command), ``driver_result.json``.
Exit code 0 on success, 2 on a failed transition / timeout, 3 on a detected fall.
"""

from __future__ import annotations

import argparse
import csv
import sys
import threading
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from unitree_go.msg import LowCmd, LowState, SportModeState, WirelessController

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_deploy_common import (KEY, DeployConfig, StickPlan, infer_controller_state,  # noqa: E402
                               load_deploy_config, load_profile, plan_sticks, write_json)

FALL_HEIGHT = 0.15  # base_link origin z [m]
FALL_TILT_COS = 0.5  # projected gravity z > -0.5  <=>  tilt > 60 deg


class GamepadDriver(Node):
    """Holds the current gamepad output and the latest robot / controller observations."""

    def __init__(self, cfg: DeployConfig, rate_hz: float):
        super().__init__("sim_gamepad_driver")
        self.cfg = cfg
        self._lock = threading.Lock()
        self._keys, self._lx, self._ly, self._rx = 0, 0.0, 0.0, 0.0
        self.pub = self.create_publisher(WirelessController, "wirelesscontroller", 10)
        self.n_published = 0
        self.ctrl_state: str | None = None
        self.q: np.ndarray | None = None
        self.quat: np.ndarray | None = None
        self.base_z: float | None = None
        self.sim_time: float | None = None
        self.create_subscription(LowCmd, "lowcmd", self._on_lowcmd, qos_profile_sensor_data)
        self.create_subscription(LowState, "lowstate", self._on_lowstate, qos_profile_sensor_data)
        self.create_subscription(SportModeState, "sportmodestate", self._on_sport,
                                 qos_profile_sensor_data)
        self.create_timer(1.0 / rate_hz, self._publish)

    # ---- output
    def set(self, keys: int = 0, lx: float = 0.0, ly: float = 0.0, rx: float = 0.0) -> None:
        with self._lock:
            self._keys, self._lx, self._ly, self._rx = int(keys), float(lx), float(ly), float(rx)

    def _publish(self) -> None:
        msg = WirelessController()
        with self._lock:
            msg.keys, msg.lx, msg.ly, msg.rx, msg.ry = self._keys, self._lx, self._ly, self._rx, 0.0
        self.pub.publish(msg)
        self.n_published += 1

    # ---- inputs
    def _on_lowcmd(self, msg: LowCmd) -> None:
        m = msg.motor_cmd[:12]
        kp = np.array([c.kp for c in m])
        kd = np.array([c.kd for c in m])
        tau = np.array([c.tau for c in m])
        self.ctrl_state = infer_controller_state(kp, kd, tau, self.cfg)

    def _on_lowstate(self, msg: LowState) -> None:
        self.q = np.array([s.q for s in msg.motor_state[:12]])
        self.quat = np.array(msg.imu_state.quaternion, dtype=np.float64)

    def _on_sport(self, msg: SportModeState) -> None:
        self.base_z = float(msg.position[2])
        self.sim_time = msg.stamp.sec + 1e-9 * msg.stamp.nanosec

    def fallen(self) -> bool:
        if self.base_z is not None and self.base_z < FALL_HEIGHT:
            return True
        if self.quat is not None:
            w, x, y, _ = self.quat
            gz = -(1.0 - 2.0 * (x * x + y * y))  # (R^T [0,0,-1])_z
            if gz > -FALL_TILT_COS:
                return True
        return False


class Scenario:
    """Sequential button / stick script running next to the executor thread."""

    def __init__(self, node: GamepadDriver, plans: list[StickPlan], args: argparse.Namespace):
        self.node, self.plans, self.args = node, plans, args
        self.t0 = time.time()
        out = Path(args.out_dir)
        self._csv_file = open(out / "driver_events.csv", "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._csv_file)
        self._csv.writerow(["wall_time", "sim_time", "event", "segment", "name", "keys", "lx",
                            "ly", "rx", "cmd_vx", "cmd_vy", "cmd_wz", "ctrl_state"])
        self.result: dict = {"ok": False, "events": []}

    def log(self, event: str, seg: int = -1, keys: int = 0, plan: StickPlan | None = None) -> None:
        n = self.node
        sticks = (plan.lx, plan.ly, plan.rx) if plan else (0.0, 0.0, 0.0)
        cmd = tuple(float(v) for v in plan.effective) if plan else (0.0, 0.0, 0.0)
        row = [f"{time.time():.6f}", "" if n.sim_time is None else f"{n.sim_time:.6f}", event, seg,
               plan.segment.name if plan else "", keys, *sticks, *cmd, n.ctrl_state]
        self._csv.writerow(row)
        self._csv_file.flush()
        print(f"[driver] t={time.time() - self.t0:7.3f}s sim={row[1] or '-':>10} {event}"
              f"{' ' + plan.segment.name if plan else ''} state={n.ctrl_state}", flush=True)

    def wait_for(self, pred, timeout: float, what: str) -> bool:
        t_end = time.time() + timeout
        while time.time() < t_end:
            if pred():
                return True
            time.sleep(0.01)
        self.log(f"TIMEOUT {what}")
        return False

    def press(self, keys: int, hold: float) -> None:
        self.node.set(keys=keys)
        time.sleep(hold)
        self.node.set(keys=0)
        time.sleep(hold)

    def transition(self, keys: int, target: str, label: str, retries: int = 3) -> bool:
        for attempt in range(retries):
            self.log(f"press {label}" + (f" (retry {attempt})" if attempt else ""), keys=keys)
            self.press(keys, self.args.key_hold)
            if self.wait_for(lambda: self.node.ctrl_state == target, 1.0, f"{label} -> {target}"):
                self.log(f"state {target}")
                return True
        return False

    def run(self) -> int:
        n, a = self.node, self.args
        if not self.wait_for(lambda: n.ctrl_state is not None and n.q is not None,
                             a.startup_timeout, "first /lowcmd + /lowstate"):
            return 2
        self.log("deploy alive")
        n.set(keys=0)
        time.sleep(0.5)
        if n.ctrl_state != "IDLE":
            self.log(f"WARN controller not in IDLE ({n.ctrl_state})")

        if not self.transition(KEY["L2"] | KEY["A"], "FixStand", "L2+A"):
            return 2
        t_fix = time.time()

        def stood_up() -> bool:
            if time.time() - t_fix < n.cfg.fixstand_duration + a.stand_settle:
                return False
            q_err = np.max(np.abs(n.q - n.cfg.fixstand_q)) if n.q is not None else np.inf
            return q_err < a.stand_tol and (n.base_z or 0.0) > a.stand_height

        if not self.wait_for(stood_up, n.cfg.fixstand_duration + a.stand_timeout, "stand-up"):
            return 2
        self.log(f"stood up (base z {n.base_z:.3f} m, max|q-q_fix| "
                 f"{np.max(np.abs(n.q - n.cfg.fixstand_q)):.3f} rad)")

        if not self.transition(KEY["start"], "HighController", "start", retries=1):
            return 2

        fell = False
        for i, plan in enumerate(self.plans):
            n.set(lx=plan.lx, ly=plan.ly, rx=plan.rx)
            self.log("segment start", i, plan=plan)
            t_end = time.time() + plan.segment.t
            while time.time() < t_end:
                if n.fallen():
                    fell = True
                    break
                time.sleep(0.01)
            if fell:
                self.log("FALL detected", i, plan=plan)
                break
            self.log("segment end", i, plan=plan)
        n.set()

        if not fell or a.select_after_fall:
            time.sleep(0.2)
            ok = self.transition(KEY["select"], "FixStand", "select")
            time.sleep(a.end_hold)
            self.log("end hold done")
            if not ok:
                return 2
        if fell:
            return 3
        self.result["ok"] = True
        return 0

    def close(self, rc: int) -> None:
        self.result.update(rc=rc, n_published=self.node.n_published)
        write_json(Path(self.args.out_dir) / "driver_result.json", self.result)
        self._csv_file.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--config", required=True, help="legged_rl_deploy config.yaml")
    ap.add_argument("--profile", required=True, help="YAML/JSON command profile")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--rate", type=float, default=100.0, help="publish rate [Hz]")
    ap.add_argument("--key-hold", type=float, default=0.25, help="button hold / release [s]")
    ap.add_argument("--startup-timeout", type=float, default=30.0)
    ap.add_argument("--stand-settle", type=float, default=0.5,
                    help="extra wait after the 500-tick FixStand interpolation [s]")
    ap.add_argument("--stand-timeout", type=float, default=10.0)
    ap.add_argument("--stand-tol", type=float, default=0.25, help="max |q - q_FixStand| [rad]")
    ap.add_argument("--stand-height", type=float, default=0.22, help="min base z [m]")
    ap.add_argument("--end-hold", type=float, default=3.0, help="FixStand hold at the end [s]")
    ap.add_argument("--select-after-fall", action="store_true",
                    help="still press select (FixStand) after a fall")
    ap.add_argument("--plan-only", action="store_true", help="print the stick plan and exit")
    args = ap.parse_args()

    cfg = load_deploy_config(args.config)
    plans = [plan_sticks(cfg.base_velocity, s) for s in load_profile(args.profile)]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    print(f"[driver] config {cfg.path}  ll_dt {cfg.ll_dt}  FixStand {cfg.fixstand_duration:.2f} s")
    print(f"[driver] {'segment':<12}{'t':>5}  {'requested (vx,vy,wz)':<24}{'sticks (lx,ly,rx)':<26}"
          f"effective")
    for p in plans:
        s = p.segment
        print(f"[driver] {s.name:<12}{s.t:5.1f}  ({s.vx:+.3f},{s.vy:+.3f},{s.wz:+.3f})    "
              f"({p.lx:+.3f},{p.ly:+.3f},{p.rx:+.3f})    ({p.effective[0]:+.3f},"
              f"{p.effective[1]:+.3f},{p.effective[2]:+.3f})")
        for w in p.warnings:
            print(f"[driver] WARNING {s.name}: {w}")
    write_json(out / "driver_plan.json", {"config": str(cfg.path), "ll_dt": cfg.ll_dt,
                                          "segments": [p.as_dict() for p in plans]})
    if args.plan_only:
        return 0

    rclpy.init()
    node = GamepadDriver(cfg, args.rate)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    stop = threading.Event()

    def _spin() -> None:
        while not stop.is_set():
            executor.spin_once(timeout_sec=0.05)

    spin = threading.Thread(target=_spin)
    spin.start()
    scenario = Scenario(node, plans, args)
    rc = 2
    try:
        rc = scenario.run()
    except KeyboardInterrupt:
        scenario.log("interrupted")
    finally:
        node.set()
        time.sleep(0.1)  # a few zero-stick messages
        scenario.close(rc)
        stop.set()
        spin.join()  # never tear rclpy down under a spinning thread
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()
    print(f"[driver] exit {rc}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
