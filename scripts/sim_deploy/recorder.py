#!/usr/bin/env python3
"""Record a unitree_mujoco + legged_rl_deploy run to NPZ (+ per-topic CSV).

Topics (best-effort readers, so the recorder can never back-pressure sim or deploy):

* ``/sportmodestate``  ground-truth base_link origin position / world-frame velocity, sim stamp
* ``/lowstate``        tick (sim ms), IMU quaternion wxyz / gyro / accelerometer, q, dq, tau_est,
                       foot_force (motor order FR, FL, RR, RL)
* ``/lowcmd``          q, dq, kp, kd, tau of the 12 motors (what the deploy node sent)
* ``/wirelesscontroller`` lx, ly, rx, ry, keys (what the scripted gamepad published)

Every sample also stores ``wall`` = time.time() at reception, which links the streams to the
driver's event log. Stop with SIGINT/SIGTERM; the files are written on exit:
``recording.npz`` with keys ``<topic>/<field>`` and ``<topic>.csv`` for each topic.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from unitree_go.msg import LowCmd, LowState, SportModeState, WirelessController

QOS = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST,
                 depth=1000)

# column layout per topic: (field name, width)
LAYOUT: dict[str, list[tuple[str, int]]] = {
    "sportmodestate": [("wall", 1), ("stamp", 1), ("position", 3), ("velocity", 3)],
    "lowstate": [("wall", 1), ("tick", 1), ("quat", 4), ("gyro", 3), ("acc", 3), ("q", 12),
                 ("dq", 12), ("tau_est", 12), ("foot_force", 4)],
    "lowcmd": [("wall", 1), ("q", 12), ("dq", 12), ("kp", 12), ("kd", 12), ("tau", 12)],
    "wirelesscontroller": [("wall", 1), ("lx", 1), ("ly", 1), ("rx", 1), ("ry", 1), ("keys", 1)],
}


class Recorder(Node):
    def __init__(self, ready_file: Path | None):
        super().__init__("sim_deploy_recorder")
        self.rows: dict[str, list[list[float]]] = {k: [] for k in LAYOUT}
        self.ready_file = ready_file
        self.create_subscription(SportModeState, "sportmodestate", self._sport, QOS)
        self.create_subscription(LowState, "lowstate", self._low, QOS)
        self.create_subscription(LowCmd, "lowcmd", self._cmd, QOS)
        self.create_subscription(WirelessController, "wirelesscontroller", self._joy, QOS)

    def _sport(self, m: SportModeState) -> None:
        self.rows["sportmodestate"].append(
            [time.time(), m.stamp.sec + 1e-9 * m.stamp.nanosec, *m.position, *m.velocity])

    def _low(self, m: LowState) -> None:
        ms = m.motor_state[:12]
        imu = m.imu_state
        self.rows["lowstate"].append(
            [time.time(), float(m.tick), *imu.quaternion, *imu.gyroscope, *imu.accelerometer,
             *(s.q for s in ms), *(s.dq for s in ms), *(s.tau_est for s in ms), *m.foot_force])
        if self.ready_file is not None:
            self.ready_file.write_text(f"{time.time():.6f}\n")
            self.ready_file = None

    def _cmd(self, m: LowCmd) -> None:
        mc = m.motor_cmd[:12]
        self.rows["lowcmd"].append(
            [time.time(), *(c.q for c in mc), *(c.dq for c in mc), *(c.kp for c in mc),
             *(c.kd for c in mc), *(c.tau for c in mc)])

    def _joy(self, m: WirelessController) -> None:
        self.rows["wirelesscontroller"].append([time.time(), m.lx, m.ly, m.rx, m.ry, m.keys])

    def save(self, out_dir: Path) -> dict[str, int]:
        arrays: dict[str, np.ndarray] = {}
        counts = {}
        for topic, layout in LAYOUT.items():
            width = sum(w for _, w in layout)
            data = np.asarray(self.rows[topic], dtype=np.float64).reshape(-1, width)
            counts[topic] = len(data)
            header, col = [], 0
            for name, w in layout:
                arrays[f"{topic}/{name}"] = data[:, col] if w == 1 else data[:, col:col + w]
                header += [name] if w == 1 else [f"{name}_{i}" for i in range(w)]
                col += w
            np.savetxt(out_dir / f"{topic}.csv", data, delimiter=",", header=",".join(header),
                       comments="", fmt="%.9g")
        np.savez_compressed(out_dir / "recording.npz", **arrays)
        return counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--ready-file", default=None, help="touched on the first /lowstate")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    stop = {"flag": False}

    def _handler(signum, _frame):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = Recorder(Path(args.ready_file) if args.ready_file else None)
    print("[recorder] running", flush=True)
    while not stop["flag"]:
        rclpy.spin_once(node, timeout_sec=0.1)
    counts = node.save(out)
    print(f"[recorder] saved {counts} to {out}", flush=True)
    node.destroy_node()
    rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
