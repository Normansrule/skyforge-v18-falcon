#!/usr/bin/env python3
"""Extract per-part data from the V18 assembly.

    python3 tools/v18_extract.py            # parts.json, cut list, G10 DXFs
    python3 tools/v18_extract.py --stl      # also write per-part STL (assembled pose) to cad/v18/stl/

Outputs:
  cad/v18/parts.json            every object: class, template, side, volume, centroid, bbox, oriented extents, P1S fit
  cad/v18/carbon_cut_list.json  CF tubes packed onto 1000 mm stock with a saw kerf
  cad/v18/dxf/*.dxf             1:1 outlines of every flat G10 plate (cut profiles, holes included if modelled)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import v18geom as g  # noqa: E402

OUT = g.ROOT / "cad" / "v18"
P1S = 256.0
KERF = 2.0
STOCK = 1000.0


def plate_outline(mesh, axis: int):
    """Section a thin plate at mid-thickness -> list of shapely polygons in the other two axes."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    lo, hi = mesh.bounds[:, axis]
    normal = np.zeros(3)
    normal[axis] = 1
    origin = mesh.bounds.mean(axis=0)
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return None, hi - lo
    keep = [i for i in range(3) if i != axis]
    polys = []
    for path in sec.discrete:
        pts = path[:, keep]
        if len(pts) >= 3:
            polys.append(Polygon(pts))
    # even-odd fill: outer contours minus holes
    polys.sort(key=lambda p: -p.area)
    shape = None
    for p in polys:
        if not p.is_valid:
            p = p.buffer(0)
        shape = p if shape is None else (shape.difference(p) if shape.contains(p) else shape.union(p))
    return unary_union(shape) if shape is not None else None, hi - lo


def write_dxf(shape, path: Path, label: str) -> None:
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    geoms = getattr(shape, "geoms", [shape])
    minx, miny = shape.bounds[0], shape.bounds[1]
    for poly in geoms:
        for ring in [poly.exterior, *poly.interiors]:
            pts = [(x - minx, y - miny) for x, y in ring.coords]
            msp.add_lwpolyline(pts, close=True)
    msp.add_text(label, height=2.0).set_placement((0, -6))
    doc.saveas(path)


def bed_fit(mesh, bed: float = P1S):
    """Best placement on a square bed. Tries the part lying on each of its three oriented-box faces and
    rotates the footprint (convex hull) in 0.5 deg steps. Returns (fits, footprint_max_mm, angle_deg, height_mm)."""
    from shapely.geometry import MultiPoint

    obb = mesh.bounding_box_oriented
    T = np.linalg.inv(obb.primitive.transform)
    v = mesh.vertices @ T[:3, :3].T + T[:3, 3]
    best = None
    for up in range(3):
        keep = [i for i in range(3) if i != up]
        hull = np.array(MultiPoint(v[:, keep].tolist()).convex_hull.exterior.coords)
        height = float(np.ptp(v[:, up]))
        for ang in np.arange(0, 90, 0.5):
            a = np.radians(ang)
            r = hull @ np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])
            w, h = np.ptp(r[:, 0]), np.ptp(r[:, 1])
            score = max(w, h)
            if height <= bed and (best is None or score < best[1]):
                best = (score <= bed, round(float(score), 1), float(ang), round(height, 1))
    return best


def pack(cuts: list[tuple[str, float]], stock: float, kerf: float):
    """First-fit decreasing onto stock lengths."""
    bars: list[list] = []
    for name, L in sorted(cuts, key=lambda c: -c[1]):
        for b in bars:
            used = sum(l for _, l in b) + kerf * len(b)
            if used + L + kerf <= stock:
                b.append((name, L))
                break
        else:
            bars.append([(name, L)])
    return bars


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stl", action="store_true")
    args = ap.parse_args(argv)
    parts = g.load()
    rows = []
    (OUT / "dxf").mkdir(exist_ok=True)
    if args.stl:
        (OUT / "stl").mkdir(exist_ok=True)
    cuts = {}
    for p in parts:
        m = p.mesh()
        vol = abs(m.volume) / 1000 if m.is_watertight else None
        c = m.center_mass if m.is_watertight else m.centroid
        ext_obb = sorted(m.bounding_box_oriented.primitive.extents.tolist(), reverse=True)
        row = {
            "name": p.name, "class": p.cls, "template": g.template_name(p.name),
            "side": g.side(p.name, float(c[1])), "color": p.color,
            "faces": int(len(m.faces)), "watertight": bool(m.is_watertight),
            "volume_cm3": round(vol, 3) if vol is not None else None,
            "area_cm2": round(m.area / 100, 2),
            "centroid_mm": [round(float(x), 2) for x in c],
            "bbox_min_mm": [round(float(x), 2) for x in m.bounds[0]],
            "bbox_max_mm": [round(float(x), 2) for x in m.bounds[1]],
            "oriented_extents_mm": [round(x, 1) for x in ext_obb],
        }
        if p.cls == "printed":
            fits, foot, ang, hgt = bed_fit(m)
            row["fits_P1S"] = bool(fits)
            row["P1S_best_placement"] = {"footprint_max_mm": foot, "rotation_deg": ang, "height_mm": hgt,
                                         "margin_mm": round(P1S - foot, 1), "diagonal": bool(ext_obb[0] > P1S)}
        if p.cls == "carbon":
            dims = g.carbon_dims(p.name)
            row["section_mm"] = dims[:2]
            row["length_mm"] = dims[2]
            cuts.setdefault(f"{dims[0]}x{dims[1]}", []).append((p.name, float(dims[2])))
        if p.cls == "g10":
            ext = m.bounds[1] - m.bounds[0]
            axis = int(np.argmin(ext))
            row["thickness_mm"] = round(float(ext[axis]), 2)
            if ext[axis] <= 3.2:
                shape, t = plate_outline(m, axis)
                if shape is not None and not shape.is_empty:
                    fn = f"{p.name}_t{t:.1f}.dxf"
                    write_dxf(shape, OUT / "dxf" / fn, f"{p.name}  t={t:.1f} mm  G10/FR4  1:1 mm")
                    row["dxf"] = f"dxf/{fn}"
                    row["holes_in_model"] = sum(len(pg.interiors) for pg in getattr(shape, "geoms", [shape]))
            else:
                row["note"] = "not a flat plate in the model - fabricate from the 3D shape"
        if args.stl:
            m.export(OUT / "stl" / f"{p.name}.stl")
        rows.append(row)

    printed = [r for r in rows if r["class"] == "printed"]
    summary = {
        "source": g.SRC.name,
        "objects": len(rows),
        "printed_instances": len(printed),
        "printed_templates": len({r["template"] for r in printed}),
        "printed_volume_cm3": round(sum(r["volume_cm3"] for r in printed), 1),
        "brief_permanent_polymer_cm3": 1297.2,
        "largest_printed_oriented_mm": max(r["oriented_extents_mm"][0] for r in printed),
        "all_printed_fit_P1S": all(r["fits_P1S"] for r in printed),
        "tightest_P1S_margin_mm": min(r["P1S_best_placement"]["margin_mm"] for r in printed),
        "diagonal_only_parts": sorted({r["template"] for r in printed if r["P1S_best_placement"]["diagonal"]}),
        "g10_volume_cm3": round(sum(r["volume_cm3"] for r in rows if r["class"] == "g10"), 2),
    }
    (OUT / "parts.json").write_text(json.dumps({"summary": summary, "parts": rows}, indent=1))

    cut = {"stock_mm": STOCK, "kerf_mm": KERF, "sections": {}}
    for sec, lst in cuts.items():
        bars = pack(lst, STOCK, KERF)
        cut["sections"][sec] = {
            "pieces": [{"name": n, "length_mm": L} for n, L in lst],
            "total_mm": sum(L for _, L in lst),
            "bars_needed": len(bars),
            "plan": [{"bar": i + 1, "cuts": [n for n, _ in b], "offcut_mm": round(STOCK - sum(L for _, L in b) - KERF * len(b), 1)}
                     for i, b in enumerate(bars)],
        }
    (OUT / "carbon_cut_list.json").write_text(json.dumps(cut, indent=1))
    print(json.dumps(summary, indent=1))
    for sec, d in cut["sections"].items():
        print(sec, d["bars_needed"], "bars", [(b["cuts"], b["offcut_mm"]) for b in d["plan"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
