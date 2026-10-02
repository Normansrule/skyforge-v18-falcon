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
    order = [("README.md", "Overview"), ("BUILD_STATUS.md", "Build status"), ("docs/BALANCE_AND_STABILITY.md", "Balance and stability"),
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

    build_glb()
    write_sw_manifest()
    print("site data written:", sorted(p.name for p in DATA.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
