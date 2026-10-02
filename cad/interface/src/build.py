#!/usr/bin/env python3
"""Interface parts that fill V18 gaps, placed and collision-checked inside the V18 assembly.

    python3 cad/interface/src/build.py

Outputs (cad/interface/out/): step/, stl/, 3mf/ (printed parts, unsliced), dxf/ (G10 profiles),
png/parts_sheet.png, manifest.json, fit_check.json (each part placed at its V18 site and tested
for collisions against every V18 object except the tubes it is meant to clamp).
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import cadquery as cq
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import params as P  # noqa: E402

sys.path.insert(0, str(P.ROOT / "tools"))
import v18geom as g  # noqa: E402

warnings.filterwarnings("ignore", category=FutureWarning)
OUT = P.ROOT / "cad" / "interface" / "out"
for sub in ("step", "stl", "3mf", "dxf", "png"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


def cross_clamp(t: float = P.XC_T, hole: float | None = None) -> cq.Workplane:
    """Plate for a square-tube crossing: tube along Y is CR wide in X, tube along X is KEEL wide in Y."""
    hole = hole or P.M3_CLEAR
    hx = P.CR / 2 + P.XC_HOLE_GAP + P.M3_CLEAR / 2
    hy = P.KEEL / 2 + P.XC_HOLE_GAP + P.M3_CLEAR / 2
    L = 2 * (hx + P.M3_CLEAR / 2 + P.XC_EDGE)
    W = 2 * (hy + P.M3_CLEAR / 2 + P.XC_EDGE)
    return (cq.Workplane("XY").rect(L, W).extrude(t).edges("|Z").fillet(1.5)
            .faces(">Z").workplane().pushPoints([(sx * hx, sy * hy) for sx in (1, -1) for sy in (1, -1)]).hole(hole))


def drill_template() -> cq.Workplane:
    return cross_clamp(2.0, 1.5)


def _edf_frame():
    half = P.KEEL / 2
    out_lim = P.SKIN_GAP_Y - P.OUTRIGGER_Y - 1.0          # stop 1 mm short of the F4 skin
    web_in = -(half + 0.1 + P.WEB_T)                         # inboard face of the web
    tab_in = -(P.OUTRIGGER_Y - P.HOUSING_R - 2.0)            # stop 2 mm short of the housing
    return half, out_lim, web_in, tab_in


def edf_ear_bracket_lower() -> cq.Workplane:
    """C-bracket on the 8x8 EDF outrigger (local frame: tube along X at the origin, F4 skin at +Y,
    EDF housing at -Y). Wraps the inboard, top-free and bottom faces only - V18 leaves ~1.4 mm between
    the outrigger and the F4 skin. Lower flange + web + slotted ear tab; the upper flange bolts down
    through the web with two M3. Rotate 180 deg about Z for the left side."""
    half, out_lim, web_in, tab_in = _edf_frame()
    L = P.CLAMP_LEN
    lower = cq.Workplane("XY").box(L, out_lim - web_in, P.FLANGE_T, centered=(True, False, False)).translate((0, web_in, -half - 0.05 - P.FLANGE_T))
    web = cq.Workplane("XY").box(L, P.WEB_T, 2 * half + 0.1 + P.FLANGE_T, centered=(True, False, False)).translate((0, web_in, -half - 0.05 - P.FLANGE_T))
    tab = cq.Workplane("XY").box(L + 6, web_in - tab_in, P.EAR_TAB_T, centered=(True, False, True)).translate((0, tab_in, 0))
    s = lower.union(web).union(tab)
    s = s.cut(cq.Workplane("XY").center(0, (tab_in + web_in) / 2).slot2D(P.EAR_SLOT_LEN, P.M3_CLEAR, 0).extrude(20).translate((0, 0, -10)))
    bolt_y = web_in + P.WEB_T / 2
    s = s.cut(cq.Workplane("XY").pushPoints([(-6, bolt_y), (6, bolt_y)]).circle(1.25).extrude(40).translate((0, 0, -20)))  # M3 tap drill
    return s


def edf_ear_bracket_upper() -> cq.Workplane:
    half, out_lim, web_in, tab_in = _edf_frame()
    L = P.CLAMP_LEN
    s = cq.Workplane("XY").box(L, out_lim - web_in, P.FLANGE_T, centered=(True, False, False)).translate((0, web_in, half + 0.05 + 0.1))
    bolt_y = web_in + P.WEB_T / 2
    return s.cut(cq.Workplane("XY").pushPoints([(-6, bolt_y), (6, bolt_y)]).circle(P.M3_CLEAR / 2).extrude(30).translate((0, 0, -10)))


def fc_iso_pad() -> cq.Workplane:
    t = P.FC_PAD_T
    s = cq.Workplane("XY").rect(P.FC_PAD_L, P.FC_PAD_W).extrude(t).edges("|Z").fillet(3)
    x0, x1 = P.FC_SLOT_X
    y0, y1 = P.FC_SLOT_Y
    for sx in (1, -1):
        for sy in (1, -1):
            s = s.cut(cq.Workplane("XY").center(sx * (x0 + x1) / 2, sy * (y0 + y1) / 2)
                      .slot2D(math.hypot(x1 - x0, y1 - y0) + P.M3_CLEAR, P.M3_CLEAR,
                              math.degrees(math.atan2(sy * (y1 - y0), sx * (x1 - x0)))).extrude(t + 1))
    return s.cut(cq.Workplane("XY").rect(18, 10).extrude(t + 1))


def nose_steer_collar() -> cq.Workplane:
    c = (cq.Workplane("XY").circle(P.COLLAR_OD / 2).extrude(P.COLLAR_H)
         .union(cq.Workplane("XY").center(P.ARM_LEN / 2, 0).rect(P.ARM_LEN, 7).extrude(4).edges("|Z").fillet(1.5))
         .union(cq.Workplane("XY").center(P.ARM_LEN, 0).circle(3.5).extrude(4)))
    c = c.cut(cq.Workplane("XY").circle((P.NOSE_WIRE_D + 0.15) / 2).extrude(P.COLLAR_H + 1))
    c = c.cut(cq.Workplane("XY").pushPoints([(r, 0) for r in P.ARM_HOLES_R]).circle(P.PUSHROD_HOLE / 2).extrude(5))
    c = c.cut(cq.Workplane("YZ").workplane(offset=-P.COLLAR_OD).center(0, P.COLLAR_H / 2).circle(P.M3_CLEAR / 2).extrude(P.COLLAR_OD))
    nut_x = -(P.NOSE_WIRE_D / 2 + 1.2 + P.M3_NUT_H / 2)
    c = c.cut(cq.Workplane("XY").workplane(offset=P.COLLAR_H / 2 - P.M3_NUT_AF / 2).center(nut_x, 0)
              .rect(P.M3_NUT_H, P.M3_NUT_AF).extrude(P.COLLAR_H))
    return c


# name: (builder, printed, material, label, qty, notes, placements [(dx, dy, dz, rot_z_deg)], exclude-from-fit)
def sites_cross():
    out = []
    for x, y, kind in P.XC_SITES:
        if kind == "rail_over_keel":   # crossrail top z=-10, keel bottom z=-28
            out += [(x, y, -10.0 + 0.05, 0), (x, y, -28.0 - P.XC_T - 0.05, 0)]
        else:                          # keel top z=-20; the gear crossbar runs through the belly skin
            out += [(x, y, -20.0 + 0.05, 0)]
    return out


def sites_belly():
    return [(x, y, P.BELLY_STRAP_Z, 0) for x, y, kind in P.XC_SITES if kind != "rail_over_keel"]


EDF_SITES = [(P.EDF_AXIS_X, P.OUTRIGGER_Y, 0.0, 0), (P.EDF_AXIS_X, -P.OUTRIGGER_Y, 0.0, 180)]
PARTS = {
    "SF_XC_crossing_clamp_G10_2p0": (cross_clamp, False, "G10/FR4 2.0 mm", "EXPERIMENTAL", 10,
                                     "Crossrails over keels: plate above and below (x4 crossings = 8). Keels over the gear crossbar: "
                                     "plate above only (x2) - the crossbar runs through the belly skin; see the belly strap. "
                                     "M3 x 25 nylock. V18 left these joints undefined.", sites_cross(), ("CF_",)),
    "SF_XC_belly_strap_G10_2p0": (cross_clamp, False, "G10/FR4 2.0 mm", "EXPERIMENTAL", 2,
                                  "Same plate used OUTSIDE the belly under each keel/gear-crossbar crossing, through the skin "
                                  "cut-out the crossbar already needs; shim to the skin. M3 x 35.", sites_belly(), ("CF_",)),
    "SF_XC_drill_template_PLA": (drill_template, True, "PLA", "PROTOTYPE-READY", 1,
                                 "Tool only: scribe and centre-punch the G10 plates. Print flat, no supports.", [], ()),
    "SF_EDF_ear_bracket_lower": (edf_ear_bracket_lower, True, "PA-CF (or PETG for the fit test)", "EXPERIMENTAL", 2,
                                 "C-bracket on each 8x8 EDF outrigger: lower flange + web + slotted ear tab. Stays 1 mm off the F4 "
                                 "skin. Fit test until the E7206 ear position is measured. Rotate 180 deg for the left side.",
                                 EDF_SITES, ("CF_EDF_outrigger",)),
    "SF_EDF_ear_bracket_upper": (edf_ear_bracket_upper, True, "PA-CF (or PETG for the fit test)", "EXPERIMENTAL", 2,
                                 "Upper flange; two M3 into the tapped web pull it onto the tube.", EDF_SITES, ("CF_EDF_outrigger",)),
    "SF_FC_iso_pad_TPU": (fc_iso_pad, True, "TPU 95A", "EXPERIMENTAL", 1,
                          "52 x 32 x 3 isolation pad inside the V18 FC keep-out (54 x 34). Slotted: FC hole pattern unconfirmed.",
                          [(486.0, -17.0, -4.0 + 0.05, 0)], ("KEEP_OUT_FC",)),
    "SF_nose_steer_collar": (nose_steer_collar, True, "PETG", "EXPERIMENTAL", 1,
                             "Clamps the 4 mm nose leg (MEASURE); M3 set screw + nut; clevis holes at 10/13/16 mm. Print on end.",
                             [], ()),
}


def export(name, shape, printed):
    cq.exporters.export(shape, str(OUT / "step" / f"{name}.step"))
    cq.exporters.export(shape, str(OUT / "stl" / f"{name}.stl"), tolerance=0.05, angularTolerance=0.1)
    if printed:
        cq.exporters.export(shape, str(OUT / "3mf" / f"{name}.3mf"), tolerance=0.05, angularTolerance=0.1)
    bb = shape.val().BoundingBox()
    return {"bbox_mm": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)], "volume_cm3": round(shape.val().Volume() / 1000, 3)}


def fit_check(name, placements, exclude):
    import trimesh
    from trimesh.collision import CollisionManager

    if not placements:
        return {"status": "not placed (no V18 site)"}
    mesh = trimesh.load(OUT / "stl" / f"{name}.stl", force="mesh")
    cm = CollisionManager()
    for p in g.load():
        if p.cls == "prop" or (exclude and p.name.startswith(exclude)):
            continue
        cm.add_object(p.name, p.mesh())
    res = []
    for dx, dy, dz, rz in placements:
        m = mesh.copy()
        m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rz), [0, 0, 1]))
        m.apply_translation([dx, dy, dz])
        hit, names = cm.in_collision_single(m, return_names=True)
        dist, nearest = cm.min_distance_single(m, return_name=True)
        res.append({"at": [dx, dy, dz, rz], "collides_with": sorted(names) if hit else [],
                    "min_clearance_mm": round(float(dist), 2), "nearest": nearest})
    return {"status": "FAIL" if any(r["collides_with"] for r in res) else "PASS", "sites": res}


def parts_sheet(names):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import trimesh
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    cols = 3
    rows = math.ceil(len(names) / cols)
    fig = plt.figure(figsize=(4.2 * cols, 3.6 * rows))
    light = np.array([0.4, -0.5, 0.8]) / np.linalg.norm([0.4, -0.5, 0.8])
    for i, n in enumerate(names):
        m = trimesh.load(OUT / "stl" / f"{n}.stl", force="mesh")
        ax = fig.add_subplot(rows, cols, i + 1, projection="3d")
        sh = 0.35 + 0.6 * np.clip(m.face_normals @ light, 0, 1)
        ax.add_collection3d(Poly3DCollection(m.triangles, facecolors=np.c_[sh * 0.62, sh * 0.66, sh * 0.72], edgecolor="none"))
        lo, hi = m.bounds
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(28, -55); ax.set_axis_off()
        e = hi - lo
        ax.set_title(f"{n}\n{e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "png" / "parts_sheet.png", dpi=110)


def main() -> int:
    manifest = {"_note": "Repo interface parts for V18 gaps. Labels per brief. Unsliced - no slicer validation performed.", "parts": {}}
    fits = {}
    for name, (build, printed, mat, label, qty, notes, sites, excl) in PARTS.items():
        shape = build()
        info = export(name, shape, printed)
        if not printed:
            face = shape.faces("<Z").val()
            cq.exporters.export(cq.Workplane("XY").add(face), str(OUT / "dxf" / f"{name}.dxf"))
        info.update({"printed": printed, "material": mat, "label": label, "qty_per_aircraft": qty, "notes": notes,
                     "fits_P1S": max(info["bbox_mm"]) <= 256 if printed else None})
        fits[name] = fit_check(name, sites, excl)
        info["v18_fit"] = fits[name]["status"]
        manifest["parts"][name] = info
        print(f"{name:32s} {info['bbox_mm']} {info['volume_cm3']} cm3 {label} fit={info['v18_fit']}")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (OUT / "fit_check.json").write_text(json.dumps(fits, indent=1))
    parts_sheet(list(PARTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
