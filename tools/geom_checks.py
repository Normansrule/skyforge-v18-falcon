#!/usr/bin/env python3
"""Geometry checks on the V18 assembly - BOTH sides, continuous control sweeps.

    python3 tools/geom_checks.py          # analysis/geom_checks.json

C1  Prop tip to well wall: section all wing panels at the prop plane (z = 24, 26, 28) and measure the
    smallest radial distance from each motor axis to the wall, minus the 63.5 mm prop radius.
C2  Seams crossing a rotor well: which printed parts form each well wall (more than one = a seam
    crosses the opening; assemble with the 145 mm gauge through the full opening).
C3  Control-surface sweep: rotate FLAP_R/L and ELEVON_R/L about a hinge axis estimated from their
    leading edge (centre of the nose radius), -25..+25 deg in 1 deg steps, and test collision and
    minimum clearance against every nearby printed part, both sides. The hinge axis is an
    ESTIMATE - confirm it against the V18 hinge design before trusting a pass.
C4  Main wheels inside a rear-rotor well footprint (plan view).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import v18geom as g  # noqa: E402

PROP_R = 63.5


def motor_axes(pbn):
    out = {}
    for k in ("M1", "M2", "M3", "M4"):
        v = pbn[f"PURCHASE_{k}_2207_envelope"].vertices
        out[k] = (v[:, :2].min(0) + v[:, :2].max(0)) / 2
    return out


def well_checks(parts, pbn):
    import trimesh

    wings = [p for p in parts if p.cls == "printed" and p.name.startswith("W")]
    res = {}
    for k, (mx, my) in motor_axes(pbn).items():
        best, owners = None, set()
        for z in (24.0, 26.0, 28.0):
            for p in wings:
                v = p.vertices
                if v[:, 2].min() > z or v[:, 2].max() < z:
                    continue
                if np.hypot(np.clip(mx, v[:, 0].min(), v[:, 0].max()) - mx, np.clip(my, v[:, 1].min(), v[:, 1].max()) - my) > 90:
                    continue
                segs = trimesh.intersections.mesh_plane(p.mesh(), [0, 0, 1], [0, 0, z])
                if len(segs) == 0:
                    continue
                pts = segs.reshape(-1, 3)[:, :2]
                d = np.hypot(pts[:, 0] - mx, pts[:, 1] - my)
                near = d < PROP_R + 25
                if near.any():
                    owners.add(p.name)
                dm = float(d.min())
                if best is None or dm < best[0]:
                    best = (dm, p.name, z)
        clear = best[0] - PROP_R
        res[k] = {"axis_xy": [round(float(mx), 1), round(float(my), 1)], "wall_radius_mm": round(best[0], 2),
                  "tip_clearance_mm": round(clear, 2), "closest_part": best[1], "at_z": best[2],
                  "well_wall_parts": sorted(owners), "seam_crosses_well": len(owners) > 1,
                  "status": "PASS" if clear >= 8.0 else ("FLAG" if clear >= 5.0 else "FAIL")}
    return res


def hinge_axis(mesh):
    """Hinge line estimate: centre of the leading-edge nose radius at several span stations."""
    import trimesh

    lo, hi = mesh.bounds
    pts = []
    for y in np.linspace(lo[1] + 0.12 * (hi[1] - lo[1]), hi[1] - 0.12 * (hi[1] - lo[1]), 7):
        segs = trimesh.intersections.mesh_plane(mesh, [0, 1, 0], [0, y, 0])
        if len(segs) == 0:
            continue
        s = segs.reshape(-1, 3)
        xmin = s[:, 0].min()
        band = s[s[:, 0] < xmin + 3.0]
        t = band[:, 2].max() - band[:, 2].min()
        pts.append([xmin + max(t, 1.0) / 2, y, (band[:, 2].max() + band[:, 2].min()) / 2])
    P = np.array(pts)
    c = P.mean(0)
    d = np.linalg.svd(P - c)[2][0]
    d = d if d[1] > 0 else -d
    return c, d, P


def rot_about(points, c, d, ang):
    d = d / np.linalg.norm(d)
    K = np.array([[0, -d[2], d[1]], [d[2], 0, -d[0]], [-d[1], d[0], 0]])
    R = np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K
    return (points - c) @ R.T + c


def sweep_checks(parts, step_deg=1.0, limit=25.0):
    import trimesh
    from trimesh.collision import CollisionManager

    pbn = {p.name: p for p in parts}
    out = {}
    for name in ("FLAP_R", "FLAP_L", "ELEVON_R_falcon", "ELEVON_L_falcon"):
        cs = pbn[name].mesh()
        c, d, P = hinge_axis(cs)
        lo, hi = cs.bounds
        r = np.linalg.norm(hi - lo)
        cm = CollisionManager()
        neigh = []
        for p in parts:
            if p.name == name or p.cls in ("keepout", "prop"):
                continue
            v = p.vertices
            plo, phi = v.min(0), v.max(0)
            if np.all(plo < hi + 25) and np.all(phi > lo - 25):
                cm.add_object(p.name, p.mesh())
                neigh.append(p.name)
        rows = []
        for a in np.arange(-limit, limit + 1e-9, step_deg):
            m = trimesh.Trimesh(rot_about(cs.vertices, c, d, np.radians(a)), cs.faces, process=False)
            hit, names = cm.in_collision_single(m, return_names=True)
            dist, nm = cm.min_distance_single(m, return_name=True)
            rows.append({"deg": float(a), "collides": bool(hit), "with": sorted(names) if hit else [],
                         "min_clearance_mm": round(float(dist), 2), "nearest": nm})
        bad = [x for x in rows if x["collides"]]
        free = [x["deg"] for x in rows if not x["collides"]]
        clear_rows = [x for x in rows if not x["collides"]]
        tight = min(clear_rows, key=lambda x: x["min_clearance_mm"]) if clear_rows else rows[0]
        out[name] = {"hinge_point_mm": [round(float(x), 1) for x in c], "hinge_dir": [round(float(x), 4) for x in d],
                     "neighbours_checked": neigh, "angles_checked": len(rows),
                     "colliding_angles": [x["deg"] for x in bad],
                     "colliding_with": sorted({n for x in bad for n in x["with"]}),
                     "free_range_deg": [min(free), max(free)] if free else None,
                     "tightest": tight,
                     "collides_at_neutral": any(x["collides"] and x["deg"] == 0 for x in rows),
                     "clearance_at_pm5_mm": [next(x["min_clearance_mm"] for x in rows if x["deg"] == -5.0),
                                             next(x["min_clearance_mm"] for x in rows if x["deg"] == 5.0)],
                     "status": "PASS" if not bad else "FAIL",
                     "samples": rows[:: max(1, int(5 / step_deg))]}
    # left/right symmetry of results
    for a, b in (("FLAP_R", "FLAP_L"), ("ELEVON_R_falcon", "ELEVON_L_falcon")):
        out[f"{a}_vs_{b}_symmetric"] = out[a]["colliding_angles"] == out[b]["colliding_angles"]
    return out


def gear_well_check(pbn):
    ax = motor_axes(pbn)
    res = {}
    for w in ("PURCHASE_main_wheel_-1", "PURCHASE_main_wheel_1"):
        v = pbn[w].vertices
        cx, cy = (v[:, :2].min(0) + v[:, :2].max(0)) / 2
        inside = [k for k, (mx, my) in ax.items() if np.hypot(cx - mx, cy - my) < 72.5]
        res[w] = {"wheel_xy": [round(float(cx), 1), round(float(cy), 1)], "inside_well_footprint_of": inside,
                  "z_top_mm": round(float(v[:, 2].max()), 1),
                  "status": "FLAG" if inside else "PASS"}
    return res


def main() -> int:
    parts = g.load()
    pbn = {p.name: p for p in parts}
    out = {"_note": __doc__.strip(), "C1_C2_wells": well_checks(parts, pbn), "C4_gear": gear_well_check(pbn)}
    print(json.dumps(out["C1_C2_wells"], indent=1))
    out["C3_control_sweep"] = sweep_checks(parts)
    for k, v in out["C3_control_sweep"].items():
        if isinstance(v, dict):
            print(k, v["status"], "free", v["free_range_deg"], "collides with", v["colliding_with"], "tightest", v["tightest"]["deg"], v["tightest"]["min_clearance_mm"])
        else:
            print(k, v)
    (g.ROOT / "analysis" / "geom_checks.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
