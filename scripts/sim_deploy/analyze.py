#!/usr/bin/env python3
"""Per-segment tracking summary of a run_mujoco_deploy.sh output directory.

Inputs (all written by the run): ``recording.npz`` (recorder.py), ``driver_events.csv`` and
``driver_plan.json`` (gamepad_driver.py). Segment windows come from the driver's wall-clock
events, mapped to sim time through the recorder's (wall, stamp) pairs of /sportmodestate.

Measured quantities (ground truth from the simulator):
  * v_B = R(q_imu)^T v_W: base_link-origin velocity (/sportmodestate.velocity, world frame)
    rotated into the body frame with the /lowstate IMU quaternion at the same sim time
    (the IMU site is rigidly attached to base_link, identity relative rotation).
  * wz = /lowstate gyroscope z (body frame).
Steady-state means skip the first ``--settle`` seconds of every segment (at most half of it).

Writes ``summary.json`` and ``summary.md``; prints the table.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_deploy_common import write_json  # noqa: E402

FALL_HEIGHT = 0.15
FALL_TILT_DEG = 60.0


def quat_to_rot(q: np.ndarray) -> np.ndarray:
    """(N, 4) wxyz -> (N, 3, 3) body-to-world rotation matrices."""
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    w, x, y, z = q.T
    return np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1),
    ], -2)


def load_events(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def analyze(run_dir: Path, settle: float) -> dict:
    rec = np.load(run_dir / "recording.npz")
    events = load_events(run_dir / "driver_events.csv")
    plan = json.loads((run_dir / "driver_plan.json").read_text())

    sp_wall, sp_t = rec["sportmodestate/wall"], rec["sportmodestate/stamp"]
    pos, vel_w = rec["sportmodestate/position"], rec["sportmodestate/velocity"]
    ls_t = rec["lowstate/tick"] * 1e-3
    quat, gyro = rec["lowstate/quat"], rec["lowstate/gyro"]
    if len(sp_t) < 2 or len(ls_t) < 2:
        raise RuntimeError("recording has too few samples")

    # body-frame velocity at /sportmodestate samples: IMU attitude at the nearest sim time
    order = np.argsort(ls_t, kind="stable")
    ls_t, quat, gyro = ls_t[order], quat[order], gyro[order]
    idx = np.clip(np.searchsorted(ls_t, sp_t), 1, len(ls_t) - 1)
    idx -= (sp_t - ls_t[idx - 1]) < (ls_t[idx] - sp_t)
    rot = quat_to_rot(quat[idx])
    vel_b = np.einsum("nji,nj->ni", rot, vel_w)  # R^T v
    gz_proj = -rot[:, 2, 2]  # projected gravity z = (R^T [0,0,-1])_z
    tilt_deg = np.degrees(np.arccos(np.clip(-gz_proj, -1.0, 1.0)))

    def wall_to_sim(w: float) -> float:
        return float(np.interp(w, sp_wall, sp_t))

    starts = {int(e["segment"]): e for e in events if e["event"] == "segment start"}
    ends = {int(e["segment"]): e for e in events if e["event"] in ("segment end", "FALL detected")}
    high = [e for e in events if e["event"] == "state HighController"]
    back = [e for e in events if e["event"] == "state FixStand"]
    t_high = wall_to_sim(float(high[0]["wall_time"])) if high else None
    t_back = wall_to_sim(float(back[-1]["wall_time"])) if len(back) > 1 else sp_t[-1]

    segments = []
    for i, seg in enumerate(plan["segments"]):
        if i not in starts or i not in ends:
            segments.append({"name": seg["name"], "completed": False})
            continue
        t0 = wall_to_sim(float(starts[i]["wall_time"]))
        t1 = wall_to_sim(float(ends[i]["wall_time"]))
        seg_settle = min(settle, 0.5 * (t1 - t0))  # short segments (or a fall early in one) keep samples
        m_sp = (sp_t >= t0 + seg_settle) & (sp_t < t1)
        m_ls = (ls_t >= t0 + seg_settle) & (ls_t < t1)
        if not m_sp.any() or not m_ls.any():
            segments.append({"name": seg["name"], "completed": False, "sim_window": [t0, t1],
                             "duration": t1 - t0, "settle": seg_settle, "n_samples": 0})
            continue
        cmd = np.asarray(seg["effective"])
        meas = np.array([vel_b[m_sp, 0].mean(), vel_b[m_sp, 1].mean(), gyro[m_ls, 2].mean()])
        std = np.array([vel_b[m_sp, 0].std(), vel_b[m_sp, 1].std(), gyro[m_ls, 2].std()])
        mae = np.array([np.abs(vel_b[m_sp, 0] - cmd[0]).mean(),
                        np.abs(vel_b[m_sp, 1] - cmd[1]).mean(),
                        np.abs(gyro[m_ls, 2] - cmd[2]).mean()])
        segments.append({
            "name": seg["name"], "completed": ends[i]["event"] == "segment end",
            "sim_window": [t0, t1], "duration": t1 - t0, "settle": seg_settle,
            "n_samples": int(m_sp.sum()),
            "cmd": cmd.tolist(), "mean": meas.tolist(), "std": std.tolist(), "mae": mae.tolist(),
            "base_z_mean": float(pos[m_sp, 2].mean()),
            "tilt_max_deg": float(tilt_deg[m_sp].max()),
        })

    m_run = (sp_t >= (t_high if t_high is not None else sp_t[0])) & (sp_t <= t_back)
    fell = bool(np.any(pos[m_run, 2] < FALL_HEIGHT) or np.any(tilt_deg[m_run] > FALL_TILT_DEG))
    rtf = (sp_t[-1] - sp_t[0]) / (sp_wall[-1] - sp_wall[0])
    walls = {k.split("/")[0]: rec[k] for k in rec.files if k.endswith("/wall")}
    counts = {k: int(len(w)) for k, w in walls.items()}
    rates = {k: (len(w) - 1) / (w[-1] - w[0]) if len(w) > 1 else 0.0 for k, w in walls.items()}
    return {
        "run_dir": str(run_dir),
        "config": plan["config"],
        "fell": fell,
        "min_base_z_policy": float(pos[m_run, 2].min()) if m_run.any() else None,
        "max_tilt_deg_policy": float(tilt_deg[m_run].max()) if m_run.any() else None,
        "sim_time_highcontroller": t_high,
        "real_time_factor": float(rtf),
        "samples": counts,
        "rates_hz_wall": rates,  # per topic, over its own first..last sample
        "segments": segments,
        "driver_warnings": {s["name"]: s["warnings"] for s in plan["segments"] if s["warnings"]},
    }


def to_markdown(s: dict) -> str:
    lines = [
        f"# Deploy validation: `{s['config']}`", "",
        f"- fell: **{s['fell']}** (min base z under the policy {s['min_base_z_policy']:.3f} m, "
        f"max tilt {s['max_tilt_deg_policy']:.1f} deg)",
        f"- real-time factor {s['real_time_factor']:.3f}; recorded rates (wall clock) "
        + ", ".join(f"{k} {v:.0f} Hz" for k, v in s["rates_hz_wall"].items()),
        "- measured: body-frame base_link velocity (sportmodestate, IMU-rotated) and gyro z; "
        f"means skip the first {s['segments'][0].get('settle', 0):.1f} s of each segment", "",
        "| segment | dur [s] | cmd vx | cmd vy | cmd wz | mean vx | mean vy | mean wz "
        "| MAE vx | MAE vy | MAE wz | z [m] | tilt max |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in s["segments"]:
        if "cmd" not in g:
            lines.append(f"| {g['name']} | not run | | | | | | | | | | | |")
            continue
        c, m, e = g["cmd"], g["mean"], g["mae"]
        lines.append(
            f"| {g['name']} | {g['duration']:.2f} | {c[0]:+.3f} | {c[1]:+.3f} | {c[2]:+.3f} | "
            f"{m[0]:+.3f} | {m[1]:+.3f} | {m[2]:+.3f} | {e[0]:.3f} | {e[1]:.3f} | {e[2]:.3f} | "
            f"{g['base_z_mean']:.3f} | {g['tilt_max_deg']:.1f} |")
    if s["driver_warnings"]:
        lines += ["", "Driver warnings (unreachable commands):"]
        lines += [f"- {k}: {w}" for k, ws in s["driver_warnings"].items() for w in ws]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--settle", type=float, default=1.0, help="skip at segment start [s]")
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    summary = analyze(run_dir, args.settle)
    write_json(run_dir / "summary.json", summary)
    md = to_markdown(summary)
    (run_dir / "summary.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
