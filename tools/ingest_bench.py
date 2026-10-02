#!/usr/bin/env python3
"""Turn a thrust-stand log (firmware/thrust_stand) into Stage-2 measurements.

    python3 tools/ingest_bench.py LOG.csv [--prop "APC B5x3E"] [--edf] [--settle 5] [--write]

For every throttle step the LAST `--settle` seconds are averaged (the first seconds of each step
include spin-up and stand ringing). Prints the table; with --write it updates
config/measurements.json:
  lift motor run -> stage2.thrust_table, max_static_thrust_g_loaded, max_current_a, prop
  --edf run      -> stage2.edf_max_thrust_g, edf_max_current_a
Then run `python3 tools/budget.py` to re-evaluate the gates.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse(text: str):
    rows = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if rows and rows[0].startswith("t_ms"):
        rows = rows[1:]
    reader = csv.reader(io.StringIO("\n".join(rows)))
    out = []
    for r in reader:
        if len(r) < 7 or r[1] != "step":
            continue
        try:
            out.append({"t": int(r[0]) / 1000, "pct": int(r[2]), "thrust": float(r[4]), "current": float(r[5]),
                        "voltage": float(r[6]), "temp": float(r[7]) if len(r) > 7 and r[7] else None})
        except ValueError:
            continue
    return out


def steps(rows, settle: float):
    by = {}
    for r in rows:
        by.setdefault(r["pct"], []).append(r)
    table = []
    for pct in sorted(by):
        rs = by[pct]
        t_end = max(r["t"] for r in rs)
        tail = [r for r in rs if r["t"] >= t_end - settle]
        if len(tail) < 3:
            continue
        temps = [r["temp"] for r in rs if r["temp"] is not None]
        n = len(tail)
        table.append({"throttle_pct": pct,
                      "thrust_g": round(sum(r["thrust"] for r in tail) / n, 1),
                      "current_a": round(sum(r["current"] for r in tail) / n, 2),
                      "voltage_v": round(sum(r["voltage"] for r in tail) / n, 3),
                      "thrust_spread_g": round(max(r["thrust"] for r in tail) - min(r["thrust"] for r in tail), 1),
                      "motor_temp_c_max": round(max(temps), 1) if temps else None,
                      "samples": n})
    return table


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log")
    ap.add_argument("--prop", default=None)
    ap.add_argument("--edf", action="store_true")
    ap.add_argument("--settle", type=float, default=5.0)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--measurements", default=str(ROOT / "config" / "measurements.json"))
    a = ap.parse_args(argv)
    table = steps(parse(Path(a.log).read_text()), a.settle)
    if not table:
        print("no complete steps found - check the log", file=sys.stderr)
        return 1
    print(f"{'pct':>4} {'thrust g':>9} {'A':>7} {'V':>7} {'V/cell':>7} {'temp C':>7} {'spread g':>9}")
    for t in table:
        print(f"{t['throttle_pct']:>4} {t['thrust_g']:>9.1f} {t['current_a']:>7.2f} {t['voltage_v']:>7.3f} "
              f"{t['voltage_v'] / 4:>7.3f} {t['motor_temp_c_max'] if t['motor_temp_c_max'] is not None else '-':>7} {t['thrust_spread_g']:>9.1f}")
    top = max(table, key=lambda t: t["thrust_g"])
    if a.write:
        p = Path(a.measurements)
        m = json.loads(p.read_text())
        s2 = m.setdefault("stage2", {})
        if a.edf:
            s2["edf_max_thrust_g"] = top["thrust_g"]
            s2["edf_max_current_a"] = max(t["current_a"] for t in table)
        else:
            s2["thrust_table"] = [{k: t[k] for k in ("throttle_pct", "thrust_g", "current_a", "voltage_v", "motor_temp_c_max")} for t in table]
            s2["max_static_thrust_g_loaded"] = top["thrust_g"]
            s2["max_current_a"] = max(t["current_a"] for t in table)
            if a.prop:
                s2["prop"] = a.prop
        p.write_text(json.dumps(m, indent=2) + "\n")
        print(f"updated {p} - now run: python3 tools/budget.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
