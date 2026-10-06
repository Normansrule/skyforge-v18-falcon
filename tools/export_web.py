#!/usr/bin/env python3
"""Export everything the web app (site/) and the desktop app need. Run after any analysis change.

    python3 tools/export_web.py            # site/data/*.json, site/docs/*.md, site/models/raw/*.glb
    node tools/web/compress_models.mjs     # weld + simplify + meshopt -> site/models/*.glb

The site is static and works offline: no data is fetched from anywhere but its own folder.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import v18geom as g  # noqa: E402

ROOT = g.ROOT
SITE = ROOT / "site"
DATA = SITE / "data"

WING_GROUP = re.compile(r"^(W[RL]|FLAP_|ELEVON_|FIN_|SP1_|SC1_)")
ROTOR_GROUP = re.compile(r"(PURCHASE_M\d_2207|NO_PRINT_PURCHASED_PROP|motor_plate|motor_backing|CF_crossrail)")


def layer(p) -> str:
    n = p.name
    if p.cls == "keepout":
        return "keepouts"
    if p.cls == "prop":
        return "props"
    if p.cls in ("carbon", "g10"):
        return "structure"
    if p.cls == "purchase":
        return "hardware"
    if n.startswith(("FLAP_", "ELEVON_")):
        return "controls"
    if n.startswith(("TRAY_", "CAM_", "SP1_", "SC1_", "EDF_saddle")):
        return "fittings"
    return "skin"


def balance_group(name: str) -> str:
    if ROTOR_GROUP.search(name):
        return "rotor"
    if WING_GROUP.match(name):
        return "wing"
    if name == "KEEP_OUT_BATTERY_MAX_140x50x38":
        return "battery"
    return "body"


def hexrgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def build_glb():
    import trimesh
    from trimesh.visual.material import PBRMaterial

    raw = SITE / "models" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    for p in g.load():
        m = p.mesh()
        col = hexrgb(p.color)
        alpha = 0.28 if p.cls == "keepout" else 1.0
        mat = PBRMaterial(name=p.name, baseColorFactor=[*col, alpha], metallicFactor=0.05 if p.cls != "carbon" else 0.3,
                          roughnessFactor=0.75, alphaMode="BLEND" if alpha < 1 else "OPAQUE", doubleSided=p.cls == "keepout")
        m.visual = trimesh.visual.TextureVisuals(material=mat)
        scene.add_geometry(m, node_name=p.name, geom_name=p.name)
    scene.export(raw / "v18.glb")

    # repo interface parts at their V18 sites
    sys.path.insert(0, str(ROOT / "cad" / "interface" / "src"))
    import build as ib  # noqa: E402
    import math

    s2 = trimesh.Scene()
    for name, spec in ib.PARTS.items():
        sites = spec[6]
        stl = ROOT / "cad" / "interface" / "out" / "stl" / f"{name}.stl"
        if not sites or not stl.exists():
            continue
        base = trimesh.load(stl, force="mesh")
        for i, (dx, dy, dz, rz) in enumerate(sites):
            m = base.copy()
            m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rz), [0, 0, 1]))
            m.apply_translation([dx, dy, dz])
            m.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(name=name, baseColorFactor=[0.18, 0.55, 0.42, 1.0], roughnessFactor=0.6))
            s2.add_geometry(m, node_name=f"REPO_{name}_{i}", geom_name=f"REPO_{name}_{i}")
    s2.export(raw / "repo_parts.glb")


V19_ORDER = ["v19a_long_nose", "v19b_falcon_tail", "v19c_forward_rotors", "v19r_boom_rotors", "v19w_four_in_wings", "v19s_stoop_crest"]
V19_SHORT = {"v19a_long_nose": "V19-A", "v19b_falcon_tail": "V19-B", "v19c_forward_rotors": "V19-C", "v19r_boom_rotors": "V19-R", "v19w_four_in_wings": "V19-W", "v19s_stoop_crest": "V19-S"}


def part_group(n: str) -> str:
    if re.search(r"canopy|cockpit", n):
        return "Cockpit"
    if re.search(r"nose_battery|BATTERY_NOSE", n):
        return "Nose bay"
    if n.endswith("__TRAY_A"):
        return "Avionics in Tray A"
    if re.search(r"rotor_boom|motor_pod|boom_hanger|motor_riser", n):
        return "Rotor booms"
    if re.search(r"well_cap|well_fill", n):
        return "Well caps and fills"
    if re.search(r"crest", n):
        return "Falcon crest"
    if re.search(r"wrist", n):
        return "Stoop wrist"
    if re.search(r"tail_|elevator_servo", n):
        return "Falcon tail"
    return "Fairings and glove"


def eval_subset(e: dict) -> dict:
    keys = ("all_up_g", "cg_mm", "rotor_front_x_mm", "rotor_rear_x_mm", "rotor_centroid_x_mm", "np_closed_x_mm", "np_open_x_mm",
            "mac_mm", "sm_closed_pct", "sm_open_pct", "worst_motor_pct", "motor_hover_g", "trim_16ms", "trim_20ms", "stall_speed_ms",
            "main_gear_x_mm", "hover_ok", "flight_ok", "geometry_ok", "passes", "le_extension_mm", "boom_prop_to_le_mm",
            "rear_well_to_flap_mm", "new_parts_g", "mass_basis")
    return {k: e.get(k) for k in keys}


def verdict(e: dict, ck: dict) -> str:
    bits = []
    if e["sm_closed_pct"] < 5:
        bits.append(f"static margin {e['sm_closed_pct']:.1f} % with the wells closed (needs 5 % or more): the CG is "
                    f"{e['cg_mm'][0] - e['np_closed_x_mm']:.0f} mm behind the neutral point")
    if e["worst_motor_pct"] > 30:
        bits.append(f"the heaviest motor carries {e['worst_motor_pct']:.1f} % of the weight in hover (30 % limit)")
    tr = max(abs(t["pitch_surfaces_deg"]) for t in e["trim_16ms"].values())
    if tr > 10:
        bits.append(f"pitch trim needs {tr:.0f} deg of surface at 16 m/s")
    nice = {"CF_crossrail_450_10x10x820": "the rear crossrail", "CF_crossrail_270_10x10x620": "the front crossrail",
            "D1_belly_intake": "the D1 belly intake"}
    if ck["collisions_new_vs_V18"]:
        bits.append("; ".join(f"{nice.get(c['a'], c['a'])} runs into {nice.get(c['b'], c['b'])}" for c in ck["collisions_new_vs_V18"]))
    return ("Fails: " + "; ".join(bits) + ".") if bits else "Passes every model gate."


def variants_data():
    import math
    f = ROOT / "analysis" / "v19_variants.json"
    if not f.exists():
        return None
    allv = json.loads(f.read_text())
    sys.path.insert(0, str(ROOT / "tools" / "v19"))
    import engine as E
    E.MODE["res"] = "fine"
    c18 = E.full({"no_le_ext": True})   # V18 exactly as drawn (no leading-edge extension)
    c18["_geometry"] = {"moves": {}, "removed": [], "new": [], "main_gear_x_mm": 385.0}
    v18 = eval_subset(E.evaluate(c18))
    v18["mass_basis"] = "V18 as modelled"
    E.save_cache()
    names = {p.name for p in g.load()}
    sys.path.insert(0, str(ROOT / "cad" / "interface" / "src"))
    import build as ib
    out = {"order": [s for s in V19_ORDER if s in allv], "recommended": "v19s_stoop_crest", "v18": v18, "variants": {}}
    for slug in out["order"]:
        v = allv[slug]
        cfg = json.loads((ROOT / "config" / "v19" / f"{slug}.json").read_text())
        e = v["evaluation"]
        moves = {k: [round(x, 2) for x in mv] for k, mv in v["moves"].items() if k in names}
        repo = {}
        for pname, spec in ib.PARTS.items():
            for i, (x, y, z, rz) in enumerate(spec[6]):
                obj = {240.0: "CF_crossrail_270_10x10x620", 420.0: "CF_crossrail_450_10x10x820", 385.0: "CF_gear_crossbar_10x10x340",
                       486.0: "KEEP_OUT_FC_54x34x24"}.get(x)
                if obj and obj in moves:
                    repo[f"REPO_{pname}_{i}"] = moves[obj]
        ck = v["checks"]
        p1s_fail = [k for k, r in ck["P1S_fit"].items() if r and not r.get("fits", True)]
        new = []
        for p in v["parts"]:
            q = {k: p[k] for k in ("name", "class", "material", "mass_g", "layer", "note", "mass_basis", "centroid_mm", "bbox_mm", "P1S")}
            q["group_label"] = part_group(p["name"])
            new.append(q)
        out["variants"][slug] = {
            "label": cfg["label"], "short": V19_SHORT.get(slug, slug), "summary": cfg["summary"], "eval": eval_subset(e),
            "verdict": verdict(e, ck), "length_mm": v["extent"]["length_mm"], "span_mm": v["extent"]["span_mm"],
            "moves": moves, "repo_moves": repo, "hidden": [h for h in v["hidden_in_viewer"] if h in names],
            "modified": [m["name"] for m in v["modified"]], "modified_detail": v["modified"],
            "new": new, "new_mass_g": round(sum(p["mass_g"] for p in new), 1), "changes": v["changes"], "notes": v["notes"],
            "checks": {"collisions": len(ck["collisions_new_vs_V18"]),
                       "collision_list": [f"{c['a']} x {c['b']}" for c in ck["collisions_new_vs_V18"]],
                       "intended": len(ck["intended_contacts"]), "jet": ck.get("jet_vs_tail"),
                       "p1s_ok": not p1s_fail, "p1s_fail": p1s_fail},
        }
        out["variants"][slug]["eval"]["fit_ok"] = not ck["collisions_new_vs_V18"] and not p1s_fail
    return out


def bom_rows():
    with open(ROOT / "bom" / "bom.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("buy_qty", "installed_qty", "row_usd_low", "row_usd_high", "unit_mass_g"):
            r[k] = float(r[k])
    return rows


def write_sw_manifest():
    """Precache list for site/sw.js plus a content hash so the service worker updates on change."""
    import hashlib

    files = []
    h = hashlib.sha1()
    for p in sorted(SITE.rglob("*")):
        if p.is_dir() or "models/raw" in str(p) or p.name in ("sw.js", "sw-manifest.json"):
            continue
        rel = p.relative_to(SITE).as_posix()
        files.append(rel)
        h.update(rel.encode())
        h.update(p.read_bytes())
    (SITE / "sw-manifest.json").write_text(json.dumps(["./", *files]))
    sw = (SITE / "sw.js").read_text()
    sw = re.sub(r"skyforge-v18-[0-9a-f_A-Z]+'", f"skyforge-v18-{h.hexdigest()[:10]}'", sw)
    (SITE / "sw.js").write_text(sw)


def main() -> int:
    if "--sw-only" in sys.argv:
        write_sw_manifest()
        return 0
    DATA.mkdir(parents=True, exist_ok=True)
    parts = json.loads((ROOT / "cad" / "v18" / "parts.json").read_text())
    mats = json.loads((ROOT / "config" / "materials.json").read_text())
    import mass_cg

    rules = mats["rules"]
    out_parts = []
    pbn = {p.name: p for p in g.load()}
    for r in parts["parts"]:
        p = pbn[r["name"]]
        e = {k: r[k] for k in ("name", "class", "template", "side", "color", "volume_cm3", "centroid_mm", "bbox_min_mm",
                               "bbox_max_mm", "oriented_extents_mm") if k in r}
        e["layer"] = layer(p)
        e["group"] = balance_group(r["name"])
        if r["class"] == "printed":
            e["material"] = mass_cg.material_for(r["template"], rules)
            e["fits_P1S"] = r["fits_P1S"]
            e["P1S"] = r["P1S_best_placement"]
        for k in ("length_mm", "section_mm", "thickness_mm", "dxf", "holes_in_model"):
            if k in r:
                e[k] = r[k]
        out_parts.append(e)
    dump = lambda name, obj: (DATA / name).write_text(json.dumps(obj, separators=(",", ":"), default=float))  # noqa: E731
    dump("parts.json", {"summary": parts["summary"], "parts": out_parts})
    dump("bom.json", bom_rows())
    for f in ("mass_model.json", "mass_cg.json", "aero.json", "geom_checks.json", "harness.json"):
        src = json.loads((ROOT / "analysis" / f).read_text())
        if f == "geom_checks.json":
            for v in src["C3_control_sweep"].values():
                if isinstance(v, dict):
                    v.pop("samples", None)
        dump(f, src)
    bs = json.loads((ROOT / "analysis" / "balance_study.json").read_text())
    keys = ["dw_mm", "dr_mm", "battery", "tail_lwpla", "avionics_forward", "lwpla", "needs_le_extension", "all_up_g", "cg_x_mm",
            "rotor_centroid_x_mm", "np_closed_x_mm", "np_open_x_mm", "sm_closed_pct", "sm_open_pct", "worst_motor_pct_weight",
            "all4_surfaces_trim_15ms_deg", "hover_ok", "flight_ok", "both_ok"]
    dump("balance_study.json", {"limits": bs["rotor_shift_limits_mm"], "keys": keys, "rows": [[r[k] for k in keys] for r in bs["all"]]})
    for f in ("power.json", "materials.json", "measurements.json", "stages.json"):
        shutil.copy(ROOT / "config" / f, DATA / f)
    with open(ROOT / "config" / "pinmap.csv", newline="") as fh:
        dump("pinmap.json", list(csv.DictReader(fh)))
    dump("carbon_cut_list.json", json.loads((ROOT / "cad" / "v18" / "carbon_cut_list.json").read_text()))
    dump("interface_parts.json", json.loads((ROOT / "cad" / "interface" / "out" / "manifest.json").read_text()))
    dump("synthetic_measurements.json", json.loads((ROOT / "tests" / "synthetic_measurements.json").read_text()))

    docs = SITE / "docs"
    docs.mkdir(exist_ok=True)
    order = [("README.md", "Overview"), ("BUILD_STATUS.md", "Build status"), ("docs/V19_VARIANTS.md", "V19 variants"), ("docs/BALANCE_AND_STABILITY.md", "Balance and stability"),
             ("docs/V18_CHECKS.md", "V18 geometry checks"), ("docs/TEST_GATES.md", "Build stages and gates"),
             ("docs/BUDGET.md", "Budget"), ("docs/BOM.md", "Bill of materials"), ("docs/WIRING.md", "Wiring"),
             ("docs/HARNESS.md", "Harness cut list"), ("docs/CAD_PARTS.md", "CAD parts"), ("firmware/thrust_stand/README.md", "Thrust stand"),
             ("docs/PUBLISHING.md", "Publishing this repo"), ("CHANGELOG.md", "Changelog")]
    index = []
    for src, title in order:
        sp = ROOT / src
        if sp.exists():
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            (docs / f"{slug}.md").write_text(sp.read_text())
            index.append({"slug": slug, "title": title, "source": src})
    dump("docs_index.json", index)

    for img in ("aero_planform.png", "balance_study.png", "aero_span_loading.png"):
        if (ROOT / "analysis" / img).exists():
            (SITE / "img").mkdir(exist_ok=True)
            shutil.copy(ROOT / "analysis" / img, SITE / "img" / img)

    shutil.copy(ROOT / "tests" / "data" / "synthetic_bench_log.csv", DATA / "synthetic_bench_log.csv")
    imgs = SITE / "img"
    imgs.mkdir(exist_ok=True)
    for src in [*(ROOT / "analysis").glob("*.png"), *(ROOT / "cad" / "interface" / "out" / "png").glob("*.png")]:
        shutil.copy(src, imgs / src.name)

    vd = variants_data()
    if vd:
        dump("variants.json", vd)
    build_glb()
    write_sw_manifest()
    print("site data written:", sorted(p.name for p in DATA.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
