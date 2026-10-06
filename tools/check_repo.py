#!/usr/bin/env python3
"""Consistency checks for the SKYFORGE V18 repo. Exit code 1 on any FAIL; FLAGs are printed.

    python3 tools/check_repo.py

Needs only the standard library (CI runs it before installing anything).
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "ALT"}
CHANGES = {"ADD", "FIX", "RESCOPE", "KEEP", "ALT"}
fails: list[str] = []
flags: list[str] = []


def j(rel):
    return json.loads((ROOT / rel).read_text())


def check_bom(v18_names: set[str]) -> None:
    rows = list(csv.DictReader(open(ROOT / "bom" / "bom.csv", newline="")))
    ids = [r["id"] for r in rows]
    for d in {i for i in ids if ids.count(i) > 1}:
        fails.append(f"BOM: duplicate id {d}")
    for r in rows:
        rid = r["id"]
        if r["stage"] not in STAGES:
            fails.append(f"BOM {rid}: bad stage {r['stage']}")
        if r["change"] not in CHANGES:
            fails.append(f"BOM {rid}: bad change tag {r['change']}")
        if not (r["url"].startswith("https://") or r["url"].startswith("repo:")):
            fails.append(f"BOM {rid}: url must be https:// or repo:")
        try:
            if float(r["row_usd_low"]) > float(r["row_usd_high"]):
                fails.append(f"BOM {rid}: low cost > high cost")
            q = float(r["installed_qty"])
            float(r["unit_mass_g"])
        except ValueError:
            fails.append(f"BOM {rid}: non-numeric qty/cost/mass")
            continue
        if not r["purchase_gate"].strip():
            fails.append(f"BOM {rid}: empty purchase gate")
        pl = r["placement"].strip()
        installed_mass = q > 0 and r["stage"] != "ALT" and r["mass_basis"] not in ("none",)
        if installed_mass and not pl:
            fails.append(f"BOM {rid}: installed item has no placement")
        for e in [e for e in pl.split(";") if e]:
            if e.startswith(("xyz:", "site:", "distributed:", "geometry:")):
                continue
            name = e.split(":")[0]
            if name not in v18_names:
                fails.append(f"BOM {rid}: placement {name} is not a V18 object")
    stage_ids = {i for s in j("config/stages.json")["stages"] for i in s["buy"]}
    for i in stage_ids - set(ids):
        fails.append(f"stages.json buys unknown BOM id {i}")
    print(f"BOM: {len(rows)} rows")


def check_v18(parts) -> None:
    s = parts["summary"]
    if s["printed_templates"] != 35:
        fails.append(f"V18: expected 35 printed templates, found {s['printed_templates']}")
    if s["printed_instances"] != 42:
        fails.append(f"V18: expected 42 installed printed pieces, found {s['printed_instances']}")
    if abs(s["printed_volume_cm3"] - s["brief_permanent_polymer_cm3"]) > 10:
        fails.append("V18: printed volume differs from the brief's 1,297.2 cm3 by more than 10 cm3")
    if not s["all_printed_fit_P1S"]:
        fails.append("V18: a printed part does not fit the P1S bed")
    for d in s.get("diagonal_only_parts", []):
        flags.append(f"V18 {d}: longer than the 256 mm bed edge - print rotated (see parts.json P1S_best_placement)")
    geo = j("config/geometry.json")
    env = {p["name"]: p for p in parts["parts"]}
    for m, v in geo["lift_motors"].items():
        e = env[f"PURCHASE_{m}_2207_envelope"]
        cx = (e["bbox_min_mm"][0] + e["bbox_max_mm"][0]) / 2
        cy = (e["bbox_min_mm"][1] + e["bbox_max_mm"][1]) / 2
        if abs(cx - v["x"]) > 0.5 or abs(cy - v["y"]) > 0.5:
            fails.append(f"geometry.json {m} ({v['x']},{v['y']}) does not match the V18 envelope ({cx:.1f},{cy:.1f})")
    print(f"V18: {s['objects']} objects, {s['printed_templates']} templates, {s['printed_volume_cm3']} cm3")


def check_pins() -> None:
    params = {}
    for line in (ROOT / "config" / "ardupilot" / "skyforge_v18_BENCH_ONLY.param").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            k, v = line.split(",")
            params[k] = float(v)
    pins = list(csv.DictReader(open(ROOT / "config" / "pinmap.csv", newline="")))
    groups: dict[str, set[str]] = {}
    for p in pins:
        n = int(p["fc_output"][1:])
        if params.get(f"SERVO{n}_FUNCTION") != float(p["servo_function"]):
            fails.append(f"pinmap {p['fc_output']}: {p['servo_function']} vs param {params.get(f'SERVO{n}_FUNCTION')}")
        if p["rate_class"] != "none":
            groups.setdefault(p["timer_group"], set()).add(p["rate_class"])
    for gname, cls in groups.items():
        if len(cls) > 1:
            fails.append(f"timer group {gname} mixes output rate classes {sorted(cls)}")
    geo = j("config/geometry.json")["lift_motors"]
    cx = sum(m["x"] for m in geo.values()) / 4
    expect = {"M1": (-1, 1, "CCW"), "M2": (1, -1, "CCW"), "M3": (-1, -1, "CW"), "M4": (1, 1, "CW")}
    for name, (sx, sy, spin) in expect.items():
        m = geo[name]
        if (m["x"] - cx) * sx <= 0 or m["y"] * sy <= 0 or m["spin"] != spin:
            fails.append(f"{name}: position/spin does not match ArduPilot Quad X ordering")
    for key, val in (("Q_FRAME_CLASS", 1), ("Q_FRAME_TYPE", 1), ("RC7_OPTION", 208), ("SERIAL1_PROTOCOL", 23),
                     ("SERIAL3_PROTOCOL", 5), ("BATT_CURR_PIN", 14), ("BATT_VOLT_PIN", 10)):
        if params.get(key) != val:
            fails.append(f"param {key} expected {val}, got {params.get(key)}")
    print(f"Pins: {len(pins)} outputs, {len(groups)} active timer groups")


def check_analysis() -> None:
    for f in ("mass_cg.json", "mass_model.json", "aero.json", "geom_checks.json", "balance_study.json", "harness.json"):
        if not (ROOT / "analysis" / f).exists():
            fails.append(f"analysis/{f} missing - run the analysis tools")
    aero = j("analysis/aero.json")
    if not aero["selftest"]["pass"]:
        fails.append("VLM self-test did not pass")
    gc = j("analysis/geom_checks.json")
    for k, w in gc["C1_C2_wells"].items():
        if w["status"] == "FAIL":
            fails.append(f"well {k}: prop tip clearance {w['tip_clearance_mm']} mm")
        if w["seam_crosses_well"]:
            flags.append(f"well {k}: seam between {', '.join(w['well_wall_parts'])} crosses the opening")
    for k, v in gc["C3_control_sweep"].items():
        if isinstance(v, dict) and v["status"] == "FAIL":
            flags.append(f"{k}: interference at {v['colliding_angles']} deg with {', '.join(v['colliding_with'])} (V18 geometry - see docs/V18_CHECKS.md)")
    for k, v in gc["C4_gear"].items():
        if v["status"] != "PASS":
            flags.append(f"{k}: inside the rear-well footprint {v['inside_well_footprint_of']}")
    bs = j("analysis/balance_study.json")
    if bs["n_feasible"] == 0:
        flags.append("balance study: no silhouette-preserving V18 combination passes hover AND static margin - see docs/V19_VARIANTS.md (V19-S, V19-W, V19-R and V19-C pass)")
    man = ROOT / "cad" / "interface" / "out" / "manifest.json"
    if man.exists():
        for name, info in json.loads(man.read_text())["parts"].items():
            if info["v18_fit"] == "FAIL":
                fails.append(f"interface part {name} collides with V18 geometry")
            for ext, sub in (("step", "step"), ("stl", "stl")):
                if not (ROOT / "cad" / "interface" / "out" / sub / f"{name}.{ext}").exists():
                    fails.append(f"interface part {name}: missing {ext}")
    else:
        fails.append("cad/interface/out missing - run python3 cad/interface/src/build.py")


def check_generated() -> None:
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "budget.py"), "--out", td], capture_output=True, text=True)
        if r.returncode:
            fails.append(f"budget.py failed: {r.stderr[-300:]}")
            return
        for f in ("BOM.md", "BUDGET.md"):
            if (Path(td) / f).read_text() != (ROOT / "docs" / f).read_text():
                fails.append(f"docs/{f} is stale - run python3 tools/budget.py")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "budget.py"), "--measurements",
                            str(ROOT / "tests" / "synthetic_measurements.json"), "--out", td], capture_output=True, text=True)
        s = json.loads((Path(td) / "budget_summary.json").read_text())
        if any(gt["status"] == "UNKNOWN" for gt in s["gates"]):
            fails.append("budget gates did not all evaluate on synthetic data")
    # site data mirrors the analysis
    for f in ("mass_model.json", "aero.json"):
        a = j(f"analysis/{f}")
        b = j(f"site/data/{f}")
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            fails.append(f"site/data/{f} is stale - run python3 tools/export_web.py")
    bom_site = j("site/data/bom.json")
    bom_csv = list(csv.DictReader(open(ROOT / "bom" / "bom.csv", newline="")))
    if [r["id"] for r in bom_site] != [r["id"] for r in bom_csv]:
        fails.append("site/data/bom.json is stale - run python3 tools/export_web.py")
    for f in ("index.html", "sw.js", "manifest.webmanifest", "models/v18.glb", "vendor/three/build/three.module.js"):
        if not (ROOT / "site" / f).exists():
            fails.append(f"site/{f} missing")
    listed = set(json.loads((ROOT / "site" / "sw-manifest.json").read_text()))
    for p in (ROOT / "site").rglob("*"):
        rel = p.relative_to(ROOT / "site").as_posix()
        if p.is_file() and "models/raw" not in rel and p.name not in ("sw.js", "sw-manifest.json") and rel not in listed:
            fails.append(f"site/{rel} is not in the offline cache list - run python3 tools/export_web.py --sw-only")
    # versions agree
    v = {json.loads((ROOT / "package.json").read_text())["version"], json.loads((ROOT / "desktop" / "package.json").read_text())["version"],
         json.loads((ROOT / "desktop" / "src-tauri" / "tauri.conf.json").read_text())["version"]}
    cargo = re.search(r'^version = "([^"]+)"', (ROOT / "desktop" / "src-tauri" / "Cargo.toml").read_text(), re.M).group(1)
    v.add(cargo)
    if len(v) != 1:
        fails.append(f"version mismatch across package.json / desktop / tauri.conf / Cargo.toml: {sorted(v)}")


def check_v19() -> None:
    """V19 variants: configs, geometry outputs, web data and the recommendation agree."""
    vf = ROOT / "analysis" / "v19_variants.json"
    if not vf.exists():
        flags.append("analysis/v19_variants.json missing - run make v19")
        return
    allv = json.loads(vf.read_text())
    web = j("site/data/variants.json")
    for slug in web["order"]:
        if not (ROOT / "config" / "v19" / f"{slug}.json").exists():
            fails.append(f"config/v19/{slug}.json missing")
        if not (ROOT / "site" / "models" / f"{slug}.glb").exists():
            fails.append(f"site/models/{slug}.glb missing - run npm run models")
        if slug not in allv:
            fails.append(f"{slug} not in analysis/v19_variants.json")
            continue
        a, w = allv[slug]["evaluation"], web["variants"][slug]["eval"]
        if abs(a["cg_mm"][0] - w["cg_mm"][0]) > 0.05 or a["passes"] != w["passes"]:
            fails.append(f"{slug}: site/data/variants.json is stale - run python3 tools/export_web.py")
        for c in allv[slug]["checks"]["collisions_new_vs_V18"]:
            flags.append(f"{slug}: new collision {c['a']} x {c['b']}")
    rec = allv.get(web["recommended"])
    if not rec or not rec["evaluation"]["passes"] or rec["checks"]["collisions_new_vs_V18"]:
        fails.append("the recommended V19 variant does not pass its gates cleanly")
    for slug in ("v19c_forward_rotors", "v19r_boom_rotors", "v19w_four_in_wings", "v19s_stoop_crest", "v19f_swift_stoop"):
        out = ROOT / "cad" / "v19" / slug
        for f in ("parts.json", "checks.json", "mass_inputs.json", f"{slug}_print_set.3mf"):
            if not (out / f).exists():
                fails.append(f"cad/v19/{slug}/{f} missing - run python3 tools/v19/geometry.py")
        if slug in allv:
            for pnm in allv[slug]["parts"]:
                if pnm["class"] in ("printed", "g10", "carbon") and not (out / "stl" / f"{pnm['name']}.stl").exists():
                    fails.append(f"cad/v19/{slug}/stl/{pnm['name']}.stl missing")
    doc = ROOT / "docs" / "V19_VARIANTS.md"
    if not doc.exists() or "V19-R" not in doc.read_text():
        fails.append("docs/V19_VARIANTS.md missing or stale - run python3 tools/v19/report.py")


def main() -> int:
    parts = j("cad/v18/parts.json")
    names = {p["name"] for p in parts["parts"]}
    check_v18(parts)
    check_bom(names)
    check_pins()
    check_analysis()
    check_generated()
    check_v19()
    for f in flags:
        print("FLAG ", f)
    for f in fails:
        print("FAIL ", f)
    print(f"\n{len(fails)} FAIL, {len(flags)} FLAG")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
