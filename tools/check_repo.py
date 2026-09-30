#!/usr/bin/env python3
"""Consistency checks for the SKYFORGE V18 repo. Exit code 1 on any FAIL.

    python3 tools/check_repo.py

Checks: BOM schema, pin map vs ArduPilot param file vs geometry, PWM timer-group rate classes,
QuadPlane X motor order, CAD manifest (P1S fit), layout-check FAILs, and that the budget gates
evaluate on synthetic data. FLAG items are printed but do not fail the run.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "ALT"}
CHANGES = {"ADD", "FIX", "RESCOPE", "KEEP", "ALT"}
fails: list[str] = []
flags: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)


def check_bom() -> None:
    rows = list(csv.DictReader(open(ROOT / "bom" / "bom.csv", newline="")))
    ids = [r["id"] for r in rows]
    for d in {i for i in ids if ids.count(i) > 1}:
        fail(f"BOM: duplicate id {d}")
    for r in rows:
        rid = r["id"]
        if r["stage"] not in STAGES:
            fail(f"BOM {rid}: bad stage {r['stage']}")
        if r["change"] not in CHANGES:
            fail(f"BOM {rid}: bad change tag {r['change']}")
        if not (r["url"].startswith("https://") or r["url"].startswith("repo:")):
            fail(f"BOM {rid}: url must be https:// or repo:")
        try:
            lo, hi = float(r["row_usd_low"]), float(r["row_usd_high"])
            float(r["unit_mass_g"]); float(r["buy_qty"]); float(r["installed_qty"])
        except ValueError:
            fail(f"BOM {rid}: non-numeric qty/cost/mass")
            continue
        if lo > hi:
            fail(f"BOM {rid}: low cost > high cost")
        if not r["purchase_gate"].strip():
            fail(f"BOM {rid}: empty purchase gate")
    print(f"BOM: {len(rows)} rows checked")


def parse_params() -> dict[str, float]:
    out = {}
    for line in (ROOT / "config" / "ardupilot" / "skyforge_v18_BENCH_ONLY.param").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, v = line.split(",")
        out[k] = float(v)
    return out


def check_pins() -> None:
    params = parse_params()
    pins = list(csv.DictReader(open(ROOT / "config" / "pinmap.csv", newline="")))
    groups: dict[str, set[str]] = {}
    for p in pins:
        n = int(p["fc_output"][1:])
        want = float(p["servo_function"])
        got = params.get(f"SERVO{n}_FUNCTION")
        if got != want:
            fail(f"pinmap {p['fc_output']}: pinmap says {want:g}, param file says {got}")
        if p["rate_class"] != "none":
            groups.setdefault(p["timer_group"], set()).add(p["rate_class"])
    for g, classes in groups.items():
        if len(classes) > 1:
            fail(f"timer group {g} mixes output rate classes {sorted(classes)}")
    geo = json.loads((ROOT / "config" / "geometry.json").read_text())
    for name, m in geo["lift_motors"].items():
        row = next(p for p in pins if p["fc_output"] == m["fc_output"])
        if float(row["servo_function"]) != m["servo_function"]:
            fail(f"{name}: geometry.json function {m['servo_function']} != pinmap {row['servo_function']}")
    # ArduPilot Quad X: M1 front-right CCW, M2 rear-left CCW, M3 front-left CW, M4 rear-right CW
    lm = geo["lift_motors"]
    expect = {"M1": (-1, +1, "CCW"), "M2": (+1, -1, "CCW"), "M3": (-1, -1, "CW"), "M4": (+1, +1, "CW")}
    cx = sum(m["x"] for m in lm.values()) / 4
    for name, (sx, sy, spin) in expect.items():
        m = lm[name]
        if (m["x"] - cx) * sx <= 0 or m["y"] * sy <= 0 or m["spin"] != spin:
            fail(f"{name}: position/spin does not match ArduPilot Quad X ordering")
    for key, val in (("Q_FRAME_CLASS", 1), ("Q_FRAME_TYPE", 1), ("RC7_OPTION", 208), ("SERIAL1_PROTOCOL", 23),
                     ("SERIAL3_PROTOCOL", 5), ("BATT_CURR_PIN", 14), ("BATT_VOLT_PIN", 10)):
        if params.get(key) != val:
            fail(f"param {key} expected {val}, got {params.get(key)}")
    print(f"Pins: {len(pins)} outputs, {len(groups)} active timer groups checked")


def check_cad() -> None:
    man = ROOT / "cad" / "out" / "manifest.json"
    if not man.exists():
        flags.append("CAD outputs not built - run python3 cad/src/build.py")
        return
    parts = json.loads(man.read_text())["parts"]
    for name, info in parts.items():
        for sub, ext in (("step", "step"), ("stl", "stl")):
            if not (ROOT / "cad" / "out" / sub / f"{name}.{ext}").exists():
                fail(f"CAD {name}: missing {ext}")
        if info["printed"]:
            if not (ROOT / "cad" / "out" / "3mf" / f"{name}.3mf").exists():
                fail(f"CAD {name}: missing 3mf")
            if not info["fits_P1S"]:
                fail(f"CAD {name}: exceeds the P1S build volume")
        elif not (ROOT / "cad" / "out" / "dxf" / f"{name}.dxf").exists():
            fail(f"CAD {name}: missing DXF cutting profile")
    lc = json.loads((ROOT / "cad" / "out" / "checks" / "layout_checks.json").read_text())["checks"]
    for c in lc:
        if c["status"] == "FAIL":
            fail(f"layout {c['id']}: {c['check']} = {c['value']}")
        elif c["status"] == "FLAG":
            flags.append(f"layout {c['id']}: {c['check']} = {c['value']}")
    print(f"CAD: {len(parts)} parts, {len(lc)} layout checks")


def check_budget() -> None:
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "budget.py"), "--measurements",
                            str(ROOT / "tests" / "synthetic_measurements.json"), "--out", td],
                           capture_output=True, text=True)
        if r.returncode:
            fail(f"budget.py failed on synthetic data: {r.stderr[-400:]}")
            return
        s = json.loads(Path(td, "budget_summary.json").read_text())
        for k in ("hover_gate", "hover_minutes_gate"):
            if s[k] not in ("PASS", "FIX", "STOP"):
                fail(f"budget gate {k} did not evaluate on synthetic data ({s[k]})")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "budget.py"), "--out",
                        tempfile.mkdtemp()], capture_output=True, text=True)
    if r.returncode:
        fail("budget.py failed on config/measurements.json")
    print("Budget: synthetic-data gate evaluation OK")


def main() -> int:
    check_bom()
    check_pins()
    check_cad()
    check_budget()
    for f in flags:
        print("FLAG ", f)
    for f in fails:
        print("FAIL ", f)
    print(f"\n{len(fails)} FAIL, {len(flags)} FLAG")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
