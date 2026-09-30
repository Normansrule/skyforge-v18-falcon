#!/usr/bin/env python3
"""Generate the SKYFORGE V18 repo interface parts, the layout reference assembly, drawings and checks.

    python3 cad/src/build.py

Outputs (cad/out/):
  step/  native STEP per part + layout assembly
  stl/   STL per part (printable parts and G10 profiles for viewing)
  3mf/   3MF per PRINTED part (unsliced - no slicer validation has been performed)
  dxf/   2D cutting profiles for G10 parts
  glb/   layout reference for quick viewing
  png/   top-view layout drawing
  checks/layout_checks.json  computed clearance checks (PASS/FLAG/FAIL)

These parts FILL V18 interface gaps (brief section 4). They do not replace the V18 airframe
templates, which live in cad/v18_baseline/ when the V18 archives are added.
"""
from __future__ import annotations

import json
import math
import sys
import warnings
from pathlib import Path

import cadquery as cq

sys.path.insert(0, str(Path(__file__).parent))
import params as P  # noqa: E402

warnings.filterwarnings("ignore", category=FutureWarning)
OUT = P.ROOT / "cad" / "out"
for sub in ("step", "stl", "3mf", "dxf", "glb", "png", "checks"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------------------------
# Parts
# ----------------------------------------------------------------------------------------------
def motor_pad(thick: float, hole: float | None = None) -> cq.Workplane:
    """G10 motor pad. Motor screws (16x16) clear the beam (beam is +/-4 in Y, screws at +/-8).
    Clamp bolts at x=+/-PAD_CLAMP_X straddle the beam and pull an RC8 cradle up underneath it."""
    h = P.MOTOR_PATTERN / 2
    cy = P.BEAM_W / 2 + P.M3_CLEAR / 2 + 1.0
    hole = hole or P.M3_CLEAR
    s = (cq.Workplane("XY").circle(P.HUB_D / 2).extrude(thick)
         .union(cq.Workplane("XY").rect(P.PAD_TAB_L, P.PAD_TAB_W).extrude(thick)))
    s = s.edges("|Z").fillet(2.0)
    s = s.faces(">Z").workplane().pushPoints([(h, h), (-h, h), (h, -h), (-h, -h)]).hole(hole)
    s = s.faces(">Z").workplane().hole(P.MOTOR_RELIEF_D)
    s = s.faces(">Z").workplane().pushPoints([(sx * P.PAD_CLAMP_X, sy * cy) for sx in (1, -1) for sy in (1, -1)]).hole(hole)
    return s


def cross_clamp(thick: float, hole: float | None = None) -> cq.Workplane:
    """One of two G10 plates sandwiching a beam/spar crossing; four M3 bolts in the quadrants."""
    bx = P.SPAR_W / 2 + P.M3_CLEAR / 2 + 1.0   # along X (spar width is in X)
    by = P.BEAM_W / 2 + P.M3_CLEAR / 2 + 1.0   # along Y (beam width is in Y)
    L = 2 * (bx + P.M3_CLEAR / 2 + 3.0)
    W = 2 * (by + P.M3_CLEAR / 2 + 3.0)
    return (cq.Workplane("XY").rect(L, W).extrude(thick).edges("|Z").fillet(2.0)
            .faces(">Z").workplane().pushPoints([(sx * bx, sy * by) for sx in (1, -1) for sy in (1, -1)])
            .hole(hole or P.M3_CLEAR))


def drill_templates() -> cq.Workplane:
    """Printed PLA scribe/centre-punch templates for the G10 pad and cross-clamp (tools, NOT flight parts)."""
    return motor_pad(2.0, 1.5).union(cross_clamp(2.0, 1.5).translate((0, 40, 0)))


def rail_cradle(rail_w: float, rail_h: float) -> cq.Workplane:
    """Printed cradle under a square carbon rail. Two M3 bolts pass either side of the rail, up
    through the G10 bridge above it; tightening squeezes the rail between cradle and bridge."""
    bolt_y = rail_w / 2 + P.M3_CLEAR / 2 + 1.0
    width = 2 * (bolt_y + P.M3_NUT_AF / 2 + P.CRADLE_WALL)
    chan_d = rail_h - P.CRADLE_PRELOAD
    height = P.CRADLE_FLOOR + chan_d
    body = cq.Workplane("XY").box(P.CRADLE_LEN, width, height, centered=(True, True, False))
    body = body.edges("|X").fillet(1.5)
    chan = (cq.Workplane("XY").workplane(offset=P.CRADLE_FLOOR - P.PAD_POCKET)
            .rect(P.CRADLE_LEN + 2, rail_w + 0.3).extrude(chan_d + P.PAD_POCKET + 1))
    body = body.cut(chan)
    bolts = cq.Workplane("XY").pushPoints([(0, bolt_y), (0, -bolt_y)]).circle(P.M3_CLEAR / 2).extrude(height + 1)
    nuts = (cq.Workplane("XY").pushPoints([(0, bolt_y), (0, -bolt_y)])
            .polygon(6, P.M3_NUT_AF / math.cos(math.pi / 6)).extrude(P.M3_NUT_H))
    return body.cut(bolts).cut(nuts)


def fc_iso_carrier() -> cq.Workplane:
    t = P.FC_CARRIER_T
    s = (cq.Workplane("XY").rect(P.FC_CARRIER_L, P.FC_CARRIER_W).extrude(t).edges("|Z").fillet(4))
    # slotted FC holes (range) - four quadrants
    x0, x1 = P.FC_SLOT_X
    y0, y1 = P.FC_SLOT_Y
    for sx in (1, -1):
        for sy in (1, -1):
            slot = (cq.Workplane("XY").center(sx * (x0 + x1) / 2, sy * (y0 + y1) / 2)
                    .slot2D(math.hypot(x1 - x0, y1 - y0) + P.M3_CLEAR, P.M3_CLEAR,
                            math.degrees(math.atan2(sy * (y1 - y0), sx * (x1 - x0))))
                    .extrude(t + 1))
            s = s.cut(slot)
    # wiring window + tray screws (M2) in the corners
    s = s.cut(cq.Workplane("XY").rect(20, 12).extrude(t + 1))
    corners = [(sx * (P.FC_CARRIER_L / 2 - 4), sy * (P.FC_CARRIER_W / 2 - 4)) for sx in (1, -1) for sy in (1, -1)]
    s = s.cut(cq.Workplane("XY").pushPoints(corners).circle(P.M2_CLEAR / 2).extrude(t + 1))
    return s


def edf_thrust_plate() -> cq.Workplane:
    """G10 plate normal to the thrust line. Fan opening is clear; the ear ring is left UNDRILLED so it
    can be drilled to the measured EDF. Rail-clamp holes at the sides."""
    t = P.G10_THICK_EDF
    s = (cq.Workplane("YZ").rect(P.EDF_PLATE_W, P.EDF_PLATE_H).extrude(t).edges("|X").fillet(6)
         .faces(">X").workplane().hole(P.EDF_FAN_ID + 1.0))
    rail_pts = [(sy * P.EDF_RAIL_HALF, sz * 30.0) for sy in (1, -1) for sz in (1, -1)]
    s = s.faces(">X").workplane().pushPoints(rail_pts).hole(P.M3_CLEAR)
    return s


def nose_steer_collar() -> cq.Workplane:
    c = (cq.Workplane("XY").circle(P.COLLAR_OD / 2).extrude(P.COLLAR_H)
         .union(cq.Workplane("XY").center(P.ARM_LEN / 2, 0).rect(P.ARM_LEN, 7).extrude(4)
                .edges("|Z").fillet(1.5))
         .union(cq.Workplane("XY").center(P.ARM_LEN, 0).circle(3.5).extrude(4)))
    c = c.cut(cq.Workplane("XY").circle((P.NOSE_WIRE_D + 0.15) / 2).extrude(P.COLLAR_H + 1))
    c = c.cut(cq.Workplane("XY").pushPoints([(r, 0) for r in P.ARM_HOLES_R]).circle(P.PUSHROD_HOLE / 2).extrude(5))
    # radial M3 set screw on the side opposite the arm, with a nut trap
    c = c.cut(cq.Workplane("YZ").workplane(offset=-P.COLLAR_OD).center(0, P.COLLAR_H / 2)
              .circle(P.M3_CLEAR / 2).extrude(P.COLLAR_OD))
    c = c.cut(cq.Workplane("YZ").workplane(offset=-(P.NOSE_WIRE_D / 2 + 1.2 + P.M3_NUT_H))
              .center(0, P.COLLAR_H / 2).polygon(6, P.M3_NUT_AF / math.cos(math.pi / 6)).extrude(P.M3_NUT_H)
              .union(cq.Workplane("XY").workplane(offset=P.COLLAR_H / 2)
                     .center(-(P.NOSE_WIRE_D / 2 + 1.2 + P.M3_NUT_H / 2), 0)
                     .rect(P.M3_NUT_H, P.M3_NUT_AF).extrude(P.COLLAR_H)))
    return c


PARTS = {
    # name: (builder, printed?, material, label, qty per aircraft, notes)
    "SF_MP_motor_pad_G10_2p5": (lambda: motor_pad(P.G10_THICK_MB), False, "G10/FR4 2.5 mm", "EXPERIMENTAL", 4,
                                "Cut from G10 via DXF. Motor screws must not bottom on the beam - check length."),
    "SF_XC_cross_clamp_G10_2p5": (lambda: cross_clamp(P.XCLAMP_T), False, "G10/FR4 2.5 mm", "EXPERIMENTAL", 16,
                                  "Two per beam/spar crossing, 8 crossings. M3 x 25 through the 18 mm stack."),
    "SF_G10_drill_templates_PLA": (drill_templates, True, "PLA", "PROTOTYPE-READY", 1,
                                   "Flat, no supports. Tool only - scribe outline and centre-punch holes on G10."),
    "SF_RC8_rail_cradle": (lambda: rail_cradle(P.BEAM_W, P.BEAM_H), True, "PETG or PA-CF", "EXPERIMENTAL", 8,
                           "Under the 8x8 motor beam, two per motor pad. Print floor-up so nut traps bridge; 5 walls."),
    "SF_RC10_rail_cradle": (lambda: rail_cradle(P.SPAR_W, P.SPAR_H), True, "PETG or PA-CF", "EXPERIMENTAL", 0,
                            "For clamping G10 plates (gear, EDF) to 10x10 spars - quantity set by the V18 rail layout."),
    "SF_FC_iso_carrier_TPU": (fc_iso_carrier, True, "TPU 95A", "EXPERIMENTAL", 1,
                              "Flat, no supports. Slots span a range because the FC hole pattern is unconfirmed."),
    "SF_EDF_thrust_plate_G10_2p0": (edf_thrust_plate, False, "G10/FR4 2.0 mm", "EXPERIMENTAL", 1,
                                    "Cut from G10 via DXF; drill EDF ears to the measured unit."),
    "SF_nose_steer_collar": (nose_steer_collar, True, "PETG", "EXPERIMENTAL", 1,
                             "Print standing on the collar end; supports off. Test piece until the real leg is measured."),
}


def export_part(name: str, shape: cq.Workplane, printed: bool) -> dict:
    cq.exporters.export(shape, str(OUT / "step" / f"{name}.step"))
    cq.exporters.export(shape, str(OUT / "stl" / f"{name}.stl"), tolerance=0.05, angularTolerance=0.1)
    if printed:
        cq.exporters.export(shape, str(OUT / "3mf" / f"{name}.3mf"), tolerance=0.05, angularTolerance=0.1)
    bb = shape.val().BoundingBox()
    vol = shape.val().Volume()
    return {"bbox_mm": [round(bb.xlen, 2), round(bb.ylen, 2), round(bb.zlen, 2)], "volume_cm3": round(vol / 1000, 3)}


def export_dxf(name: str, shape: cq.Workplane, plane: str) -> None:
    """Export the flat face as a 1:1 cutting profile (outline + holes)."""
    face = shape.faces("<Z" if plane == "XY" else "<X").val()
    cq.exporters.export(cq.Workplane(plane).add(face), str(OUT / "dxf" / f"{name}.dxf"))


# ----------------------------------------------------------------------------------------------
# Layout reference
# ----------------------------------------------------------------------------------------------
HALF_LE = [(0, 0), (20, 50), (55, 100), (90, 150), (118, 210), (140, 270), (172, 330), (250, 420), (350, 500)]
HALF_TE = [(420, 500), (600, 390), (610, 330), (560, 260), (545, 180), (620, 120), (700, 70), (800, 30), (810, 0)]
SPAR_HALF = (240.0, 300.0, 300.0)


def planform_points() -> list[tuple[float, float]]:
    right = HALF_LE + HALF_TE
    left = [(x, -y) for x, y in reversed(right) if y != 0]
    return right + left


def seg_dist(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def point_in_poly(p, poly) -> bool:
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def layout_assembly() -> cq.Assembly:
    pts = planform_points()
    skin = cq.Workplane("XY").polyline(pts).close().extrude(6).translate((0, 0, -3))
    for (mx, my) in P.MOTORS.values():
        skin = skin.cut(cq.Workplane("XY").center(mx, my).circle(P.WELL_D / 2).extrude(20).translate((0, 0, -10)))
    a = cq.Assembly(name="SKYFORGE_V18_layout_reference")
    a.add(skin, name="planform_proxy_NOT_V18_SHAPE", color=cq.Color(0.6, 0.6, 0.62, 0.35))
    for sx, half in zip(P.SPAR_X, SPAR_HALF):
        a.add(cq.Workplane("XY").box(P.SPAR_W, 2 * half, P.SPAR_H).translate((sx, 0, -P.SPAR_H / 2 - 3)),
              name=f"spar_x{int(sx)}", color=cq.Color(0.1, 0.1, 0.1))
    pad = motor_pad(P.G10_THICK_MB)
    xc = cross_clamp(P.XCLAMP_T)
    beam_top = -3 - P.SPAR_H          # beams pass under the spars
    for name, (mx, my) in P.MOTORS.items():
        x0 = max(sx for sx in P.SPAR_X if sx < mx)
        beam_len = P.BEAM_SPAN + 2 * P.BEAM_OVERHANG
        a.add(cq.Workplane("XY").box(beam_len, P.BEAM_W, P.BEAM_H).translate((x0 + P.BEAM_SPAN / 2, my, beam_top - P.BEAM_H / 2)),
              name=f"{name}_beam_8x8", color=cq.Color(0.1, 0.1, 0.1))
        a.add(pad.translate((mx, my, beam_top)), name=f"{name}_pad", color=cq.Color(0.85, 0.8, 0.3))
        for sx in (x0, x0 + P.BEAM_SPAN):
            a.add(xc.translate((sx, my, -3)), name=f"{name}_xclamp_top_x{int(sx)}", color=cq.Color(0.85, 0.8, 0.3))
            a.add(xc.translate((sx, my, beam_top - P.BEAM_H - P.XCLAMP_T)), name=f"{name}_xclamp_bot_x{int(sx)}",
                  color=cq.Color(0.85, 0.8, 0.3))
        mz = beam_top + P.G10_THICK_MB
        a.add(cq.Workplane("XY").circle(P.MOTOR_FOOT_D / 2).extrude(33).translate((mx, my, mz)), name=f"{name}_motor",
              color=cq.Color(0.2, 0.2, 0.25))
        a.add(cq.Workplane("XY").circle(P.PROP_D / 2).extrude(1.5).translate((mx, my, mz + 30)), name=f"{name}_prop_disc",
              color=cq.Color(0.2, 0.5, 0.9, 0.3))
    a.add(cq.Workplane("YZ").circle(P.EDF_HOUSING_OD / 2).extrude(80).translate((680, 0, 0)), name="EDF_64mm_envelope",
          color=cq.Color(0.3, 0.3, 0.3))
    a.add(cq.Workplane("XY").box(136, 44, 31).translate((300, 0, -25)), name="battery_136x44x31_PLACEMENT_TBD",
          color=cq.Color(0.8, 0.2, 0.2))
    for sy in (1, -1):
        a.add(cq.Workplane("XY").box(32, 11.5, 24).translate((P.SERVO_X, sy * P.SERVO_Y, -8)), name=f"servo_outer_{'R' if sy > 0 else 'L'}",
              color=cq.Color(0.1, 0.1, 0.1))
        a.add(cq.Workplane("XZ").circle(25).extrude(12).translate((P.GEAR_X, sy * P.MAIN_TRACK / 2 + 6, -120)),
              name=f"main_wheel_{'R' if sy > 0 else 'L'}", color=cq.Color(0.05, 0.05, 0.05))
    a.add(cq.Workplane("XZ").circle(22).extrude(10).translate((P.NOSE_X, 5, -120)), name="nose_wheel", color=cq.Color(0.05, 0.05, 0.05))
    return a


def layout_checks() -> dict:
    poly = planform_points()
    res = []

    def add(cid, desc, value, ok, level="FAIL", note=""):
        res.append({"id": cid, "check": desc, "value": value, "status": "PASS" if ok else level, "note": note})

    margin = (P.WELL_D - P.PROP_D) / 2
    add("L1", "Prop tip radial margin in the 145 mm well (mm)", margin, margin >= 8.0)
    web = (P.MOTORS["M2"][0] - P.MOTORS["M3"][0]) - P.WELL_D
    add("L2", "Fore/aft web between wells, same side (mm) >= spar + 2 x 5", web, web >= P.SPAR_W + 10)
    for name, (mx, my) in P.MOTORS.items():
        d = min(seg_dist((mx, my), a, b) for a, b in zip(poly, poly[1:] + poly[:1])) - P.WELL_D / 2
        add(f"L3-{name}", f"{name} well edge to planform-proxy edge (mm) - proxy outline, informational", round(d, 1),
            d >= P.EDGE_GAP - 5, "FLAG", "Proxy planform only; the V18 CAD edge gap is 35 mm by construction")
    for sy in (1, -1):
        d = min(math.hypot(P.SERVO_X - mx, sy * P.SERVO_Y - my) for mx, my in P.MOTORS.values()) - P.WELL_D / 2
        add(f"L4-{'R' if sy > 0 else 'L'}", "Outer servo centre to nearest well edge (mm) >= 25", round(d, 1), d >= 25)
    for sy in (1, -1):
        wheel = (P.GEAR_X, sy * P.MAIN_TRACK / 2)
        inside = [n for n, (mx, my) in P.MOTORS.items() if math.hypot(wheel[0] - mx, wheel[1] - my) < P.WELL_D / 2]
        add(f"L5-{'R' if sy > 0 else 'L'}", "Main wheel contact point outside every rotor-well footprint (plan view)",
            f"({wheel[0]}, {wheel[1]:+.0f}) inside {inside}" if inside else "clear", not inside, "FLAG",
            "Wheel sits under a rear well: attach the leg inboard of |y|=147.5, keep leg + wheel below the rotor wash, "
            "and include the leg in the Stage-2/9 thrust measurement.")
    for cg in (330, 345, 360):
        add(f"L6-{cg}", f"Main-gear axle aft of CG x{cg} (mm) - tip-back margin, informational", P.GEAR_X - cg,
            P.GEAR_X - cg >= 40, "FLAG", "Check the 15 deg rule with the measured CG height at Stage 9")
    disc = math.pi * (P.PROP_D / 2) ** 2
    pad_area = motor_pad(P.G10_THICK_MB).faces("<Z").val().Area() + 4 * math.pi * (P.M3_CLEAR / 2) ** 2 \
        + 4 * math.pi * (P.M3_CLEAR / 2) ** 2 + math.pi * (P.MOTOR_RELIEF_D / 2) ** 2   # outline area
    beam_area = P.BEAM_W * P.PROP_D
    overlap = P.BEAM_W * P.PAD_TAB_L
    foot = math.pi * (P.MOTOR_FOOT_D / 2) ** 2
    frac = (beam_area + pad_area - overlap - foot) / disc
    add("L7", "Beam + pad blockage of the prop disc outside the motor footprint (fraction)", round(frac, 3), frac <= 0.10,
        "FLAG", "Bench the prop WITH the beam and pad under it at Stage 2 to measure the real thrust loss.")
    for sx, half in zip(P.SPAR_X, SPAR_HALF):
        ends_inside = point_in_poly((sx, half - 5), poly) and point_in_poly((sx + P.SPAR_W / 2, half), poly)
        add(f"L8-x{int(sx)}", f"Spar x{int(sx)} (+/-{half:g}) inside planform proxy", ends_inside, ends_inside, "FLAG")
    return {"note": "Computed from config/geometry.json + cad/src/params.py. PASS/FAIL are geometric only; FLAG = needs a "
                    "decision or a real-part check. The planform is a proxy, NOT the V18 shape.", "checks": res}


def draw_layout_png() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon, Rectangle

    fig, ax = plt.subplots(figsize=(10, 8.8))
    pts = [(y, x) for x, y in planform_points()]  # plot span horizontally, x downward
    ax.add_patch(Polygon(pts, closed=True, fc="#d9dade", ec="#555", lw=1.2, label="planform proxy (not V18 shape)"))
    for sx, half in zip(P.SPAR_X, SPAR_HALF):
        ax.add_patch(Rectangle((-half, sx - P.SPAR_W / 2), 2 * half, P.SPAR_W, fc="#222", ec="none"))
    for n, (mx, my) in P.MOTORS.items():
        ax.add_patch(Circle((my, mx), P.WELL_D / 2, fc="white", ec="#333", lw=1))
        ax.add_patch(Circle((my, mx), P.PROP_D / 2, fc="#8fb6e8", ec="#2a64b0", alpha=0.45))
        x0 = max(sx for sx in P.SPAR_X if sx < mx)
        ax.add_patch(Rectangle((my - P.BEAM_W / 2, x0 - P.BEAM_OVERHANG), P.BEAM_W, P.BEAM_SPAN + 2 * P.BEAM_OVERHANG, fc="#333"))
        ax.add_patch(Rectangle((my - P.PAD_TAB_W / 2, mx - P.PAD_TAB_L / 2), P.PAD_TAB_W, P.PAD_TAB_L, fc="#d7c35a", ec="#8a7a20"))
        ax.text(my, mx, n, ha="center", va="center", fontsize=10, weight="bold")
    for sy in (1, -1):
        ax.add_patch(Rectangle((sy * P.SERVO_Y - 5.75, P.SERVO_X - 16), 11.5, 32, fc="#111"))
        ax.plot(sy * P.MAIN_TRACK / 2, P.GEAR_X, "ks", ms=9)
    ax.plot(0, P.NOSE_X, "ks", ms=8)
    ax.axhspan(315, 360, color="#f3a", alpha=0.12, label="CG sweep x315-360 (budget table)")
    ax.axhline(P.CENTROID_X, color="#c03", ls="--", lw=1, label="equal-thrust centroid x330 (NOT flight CG)")
    ax.add_patch(Rectangle((-P.EDF_HOUSING_OD / 2, 680), P.EDF_HOUSING_OD, 80, fc="#555", alpha=0.6, label="EDF envelope"))
    ax.set_xlim(-560, 560)
    ax.set_ylim(840, -30)
    ax.set_aspect("equal")
    ax.set_xlabel("y (mm, + starboard)")
    ax.set_ylabel("x (mm, + aft from nose)")
    ax.set_title("SKYFORGE V18 - layout reference (top view)\nwells, 127 mm props, candidate spars x150/330/510, 8x8 motor beams + G10 pads, gear, servos")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "png" / "layout_top.png", dpi=130)


def draw_parts_sheet(names: list[str]) -> None:
    """Isometric contact sheet of every part, rendered from the exported STLs."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import trimesh
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    cols = 4
    rows = math.ceil(len(names) / cols)
    fig = plt.figure(figsize=(4 * cols, 3.6 * rows))
    light = np.array([0.4, -0.5, 0.8]) / np.linalg.norm([0.4, -0.5, 0.8])
    for i, n in enumerate(names):
        m = trimesh.load(OUT / "stl" / f"{n}.stl", force="mesh")
        ax = fig.add_subplot(rows, cols, i + 1, projection="3d")
        shade = 0.35 + 0.6 * np.clip(m.face_normals @ light, 0, 1)
        pc = Poly3DCollection(m.triangles, facecolors=np.c_[shade * 0.85, shade * 0.8, shade * 0.55], edgecolor="none")
        ax.add_collection3d(pc)
        lo, hi = m.bounds
        c, r = (lo + hi) / 2, (hi - lo).max() / 2
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.set_box_aspect((1, 1, 1)); ax.view_init(28, -55); ax.set_axis_off()
        ext = hi - lo
        ax.set_title(f"{n}\n{ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "png" / "parts_sheet.png", dpi=110)


def main() -> int:
    manifest = {"_note": "Repo interface parts. Label per brief: FINISHED / PROTOTYPE-READY / EXPERIMENTAL. "
                         "Files are unsliced; no slicer validation performed.", "parts": {}}
    for name, (build, printed, material, label, qty, orient) in PARTS.items():
        shape = build()
        info = export_part(name, shape, printed)
        info.update({"printed": printed, "material": material, "label": label, "qty_per_aircraft": qty, "notes": orient,
                     "fits_P1S": max(info["bbox_mm"]) <= 256 if printed else None})
        if not printed:
            export_dxf(name, shape, "YZ" if "EDF" in name else "XY")
        manifest["parts"][name] = info
        print(f"{name:32s} {info['bbox_mm']}  {info['volume_cm3']} cm3  {label}")
    assy = layout_assembly()
    assy.save(str(OUT / "step" / "SF_LAYOUT_V18_reference.step"))
    assy.save(str(OUT / "glb" / "SF_LAYOUT_V18_reference.glb"))
    (OUT / "checks" / "layout_checks.json").write_text(json.dumps(layout_checks(), indent=2))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    draw_layout_png()
    draw_parts_sheet(list(PARTS))
    print("layout + checks written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
