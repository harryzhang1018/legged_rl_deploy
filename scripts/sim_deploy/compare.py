#!/usr/bin/env python3
"""Side-by-side comparison of scripted unitree_mujoco runs (run_mujoco_deploy.sh outputs).

    compare.py <eval_dir> [--ref LABEL] [--out compare.md]

``<eval_dir>`` holds one folder per policy label, each with one run folder per profile and
repeat: ``<eval_dir>/<label>/<profile>_r<k>/`` (the layout eval_go2_velocity.sh writes).
Every run folder needs ``summary.json`` (analyze.py), ``recording.npz`` and
``driver_events.csv``.

Per run, under the policy (driver events "state HighController" .. last "state FixStand"):
  * MAE vx, vy [m/s], wz [rad/s]: mean |measured - command| over all segments, weighted by
    samples, after the analysis settle time (analyze.py --settle). This is the per-axis
    tracking error; lower is better. Only runs that finished the profile count: a run that
    fell or stopped is in "falls", not in the MAE.
  * achieved / commanded on each commanded axis, per segment (1.00 = exact).
  * peak |tau_est| per joint type (hip, thigh, calf) [N m], mean mechanical power
    sum_j |tau_j * dq_j| [W], and mean joint-target rate |d q_target / dt| [rad/s] (/lowcmd).
Values of repeated runs are averaged; "x / y" gives the min / max over the repeats.
Only numpy is required.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

AXES = ("vx", "vy", "wz")
JOINT_TYPES = {"hip": [0, 3, 6, 9], "thigh": [1, 4, 7, 10], "calf": [2, 5, 8, 11]}  # FR FL RR RL
RUN_RE = re.compile(r"^(?P<profile>.+)_r(?P<rep>\d+)$")


def policy_window(run: Path) -> tuple[float, float] | None:
    """Wall-clock window under the policy: first HighController .. last FixStand after it."""
    with open(run / "driver_events.csv", newline="", encoding="utf-8") as f:
        events = list(csv.DictReader(f))
    t0 = next((float(e["wall_time"]) for e in events if e["event"] == "state HighController"), None)
    if t0 is None:
        return None
    back = [float(e["wall_time"]) for e in events if e["event"] == "state FixStand" and float(e["wall_time"]) > t0]
    t1 = back[-1] if back else max(float(e["wall_time"]) for e in events)
    return t0, t1


def run_metrics(run: Path) -> dict:
    s = json.loads((run / "summary.json").read_text())
    segs = [g for g in s["segments"] if g.get("completed") and "mae" in g]
    w = np.array([g["n_samples"] for g in segs], dtype=float)
    mae = np.array([g["mae"] for g in segs], dtype=float)
    completed = len(segs) == len(s["segments"])
    m = {
        "fell": bool(s["fell"]),
        "completed": completed,
        "max_tilt": s["max_tilt_deg_policy"],
        "min_z": s["min_base_z_policy"],
        "rtf": s["real_time_factor"],
        "mae": (w[:, None] * mae).sum(0) / w.sum() if completed and len(segs) else np.full(3, np.nan),
        "segments": {},
    }
    for g in s["segments"]:
        if "cmd" not in g or not g.get("completed"):
            m["segments"][g["name"]] = None
            continue
        cmd, mean = np.array(g["cmd"]), np.array(g["mean"])
        m["segments"][g["name"]] = {
            "cmd": cmd,
            "ratio": [mean[i] / cmd[i] if abs(cmd[i]) > 1e-9 else None for i in range(3)],
            "mean": mean,
        }
    win = policy_window(run)
    rec = np.load(run / "recording.npz")
    if win is not None:
        ls = (rec["lowstate/wall"] >= win[0]) & (rec["lowstate/wall"] <= win[1])
        tau, dq = rec["lowstate/tau_est"][ls], rec["lowstate/dq"][ls]
        m["tau_peak"] = {k: float(np.abs(tau[:, idx]).max()) for k, idx in JOINT_TYPES.items()}
        m["power"] = float(np.abs(tau * dq).sum(1).mean())
        lc = (rec["lowcmd/wall"] >= win[0]) & (rec["lowcmd/wall"] <= win[1])
        q, t = rec["lowcmd/q"][lc], rec["lowcmd/wall"][lc]
        m["target_rate"] = float(np.abs(np.diff(q, axis=0)).sum(0).sum() / 12.0 / (t[-1] - t[0]))
    return m


def failed_run(run: Path) -> dict:
    """Placeholder for a run without a usable summary: it counts in runs and falls only."""
    rc = None
    if (run / "driver_result.json").is_file():
        rc = json.loads((run / "driver_result.json").read_text()).get("rc")
    return {"fell": rc == 3, "completed": False, "max_tilt": None, "min_z": None, "rtf": None,
            "mae": np.full(3, np.nan), "segments": {}}


def load(eval_dir: Path) -> dict[str, dict[str, list[dict]]]:
    """{label: {profile: [run metrics]}}"""
    data: dict[str, dict[str, list[dict]]] = {}
    for label_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
        for run in sorted(p for p in label_dir.iterdir() if p.is_dir()):
            mt = RUN_RE.match(run.name)
            if not mt:
                continue
            try:
                metrics = run_metrics(run)
            except Exception as exc:  # noqa: BLE001 - count it as a failed run and continue
                print(f"{run}: no usable summary ({exc}); counted as failed", file=sys.stderr)
                metrics = failed_run(run)
            data.setdefault(label_dir.name, {}).setdefault(mt["profile"], []).append(metrics)
    return data


def nanmean_rows(rows: list[np.ndarray]) -> np.ndarray:
    a = np.array(rows, dtype=float)
    ok = np.isfinite(a)
    return np.where(ok.any(0), np.where(ok, a, 0.0).sum(0) / np.maximum(ok.sum(0), 1), np.nan)


def agg(values: list[float], fmt: str) -> str:
    v = np.array([x for x in values if x is not None and np.isfinite(x)], dtype=float)
    if not len(v):
        return "-"
    if len(v) == 1 or np.allclose(v.min(), v.max()):
        return format(v.mean(), fmt)
    return f"{format(v.mean(), fmt)} ({format(v.min(), fmt)} / {format(v.max(), fmt)})"


def profile_tables(profile: str, runs: dict[str, list[dict]], ref: str | None) -> list[str]:
    labels = list(runs)
    ref_mae = nanmean_rows([r["mae"] for r in runs[ref]]) if ref in runs else None
    lines = [f"## Profile `{profile}`", "",
             "| policy | runs | falls | MAE vx [m/s] | MAE vy [m/s] | MAE wz [rad/s] "
             + (f"| vs `{ref}` (vx / vy / wz) " if ref_mae is not None else "")
             + "| max tilt [deg] | peak tau hip / thigh / calf [N m] | power [W] | target rate [rad/s] |",
             "|---|---|---|---|---|---|" + ("---|" if ref_mae is not None else "") + "---|---|---|---|"]
    for lb in labels:
        rs = runs[lb]
        falls = sum(r["fell"] for r in rs) + sum(not r["completed"] for r in rs if not r["fell"])
        mae = [agg([r["mae"][i] for r in rs], ".3f") for i in range(3)]
        row = f"| `{lb}` | {len(rs)} | {falls} | " + " | ".join(mae) + " | "
        if ref_mae is not None:
            m = nanmean_rows([r["mae"] for r in rs])
            row += " / ".join(f"{100 * (m[i] - ref_mae[i]) / ref_mae[i]:+.0f}%"
                              if np.isfinite(m[i]) and np.isfinite(ref_mae[i]) and ref_mae[i] > 0 else "-"
                              for i in range(3)) + " | "
        tau = " / ".join(agg([r.get("tau_peak", {}).get(k) for r in rs], ".1f").split(" (")[0] for k in JOINT_TYPES)
        row += (f"{agg([r['max_tilt'] for r in rs], '.1f')} | {tau} | "
                f"{agg([r.get('power') for r in rs], '.0f')} | {agg([r.get('target_rate') for r in rs], '.2f')} |")
        lines.append(row)
    lines += ["", "Achieved / commanded on each commanded axis (mean of the repeats):", ""]
    seg_names: list[str] = []
    for lb in labels:
        for r in runs[lb]:
            seg_names += [n for n in r["segments"] if n not in seg_names]
    lines += ["| segment | command (vx, vy, wz) | " + " | ".join(f"`{lb}`" for lb in labels) + " |",
              "|---|---|" + "---|" * len(labels)]
    for name in seg_names:
        found = [r["segments"][name] for lb in labels for r in runs[lb] if r["segments"].get(name) is not None]
        if not found:
            continue
        cmd = found[0]["cmd"]
        cells = []
        for lb in labels:
            vals = []
            for i in range(3):
                if abs(cmd[i]) < 1e-9:
                    continue
                rs = [r["segments"].get(name) for r in runs[lb]]
                v = [g["ratio"][i] for g in rs if g is not None and g["ratio"][i] is not None]
                vals.append(f"{np.mean(v):.2f}" if v else "-")
            if not vals:  # zero command: show the drift (mean |v|) instead
                rs = [r["segments"].get(name) for r in runs[lb]]
                v = [np.abs(g["mean"]).max() for g in rs if g is not None]
                vals.append(f"drift {np.mean(v):.2f}" if v else "-")
            cells.append(" / ".join(vals))
        lines.append(f"| {name} | ({cmd[0]:+.1f}, {cmd[1]:+.1f}, {cmd[2]:+.1f}) | " + " | ".join(cells) + " |")
    return lines + [""]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("eval_dir", type=Path)
    ap.add_argument("--ref", help="label the MAE change is relative to (default: the first label)")
    ap.add_argument("--out", type=Path, help="markdown output (default: <eval_dir>/compare.md)")
    args = ap.parse_args()
    data = load(args.eval_dir)
    if not data:
        print(f"no runs under {args.eval_dir}", file=sys.stderr)
        return 1
    ref = args.ref or next(iter(data))
    profiles = sorted({p for d in data.values() for p in d})
    lines = [f"# unitree_mujoco comparison: `{args.eval_dir}`", "",
             "MAE = mean |measured - command| over the completed segments (lower is better). "
             "falls = runs that fell or did not finish. tau = /lowstate tau_est under the policy.", ""]
    for prof in profiles:
        runs = {lb: d[prof] for lb, d in data.items() if prof in d}
        lines += profile_tables(prof, runs, ref if ref in runs else None)
    md = "\n".join(lines)
    out = args.out or args.eval_dir / "compare.md"
    out.write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
