#!/usr/bin/env python3
"""Mass, centre of gravity and per-motor hover load from the V18 geometry + BOM.

    python3 tools/mass_cg.py

Every mass is placed where the V18 model puts it:
  * printed parts      V18 mesh volume x material density (config/materials.json), at the mesh centroid
  * carbon tubes       length from the V18 name x mass per metre, at the tube centroid
  * G10 plates         V18 mesh volume x 1.85 g/cm3, at the plate centroid
  * purchased hardware BOM mass at the V18 object named in bom.csv `placement`
                       (keep-out boxes, motor envelopes, prop references, gear meshes), or at `xyz:` for
                       items the V18 model does not place (flagged as assumptions)
Measured masses in config/measurements.json override estimates.

Writes analysis/mass_cg.json.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import v18geom as g  # noqa: E402

ROOT = g.ROOT
MOTORS = {"M1": "PURCHASE_M1_2207_envelope", "M2": "PURCHASE_M2_2207_envelope",
          "M3": "PURCHASE_M3_2207_envelope", "M4": "PURCHASE_M4_2207_envelope"}


def load_json(rel):
    return json.loads((ROOT / rel).read_text())


def material_for(template: str, rules) -> str:
    for r in rules:
        if re.search(r["match"], template):
            return r["material"]
    raise ValueError(f"no material rule for {template}")


def motor_positions(parts_by_name) -> dict[str, np.ndarray]:
    out = {}
    for k, n in MOTORS.items():
        v = parts_by_name[n].vertices
        out[k] = v[:, :2].min(axis=0) / 2 + v[:, :2].max(axis=0) / 2
    return out


def hover_split(total_g: float, cg_xy, motors: dict[str, np.ndarray]) -> dict[str, float]:
    """Minimum-norm thrusts that balance weight and both moments about the CG (what a symmetric
    mixer converges to in a steady hover). Returns grams per motor."""
    names = list(motors)
    P = np.array([motors[n] for n in names])
    A = np.vstack([np.ones(4), P[:, 0] - cg_xy[0], P[:, 1] - cg_xy[1]])
    b = np.array([total_g, 0.0, 0.0])
    T = A.T @ np.linalg.solve(A @ A.T, b)
    return {n: float(t) for n, t in zip(names, T)}


def lw_cases_for(mats, rho_lw_meas):
    lw = dict(mats["lwpla_cases"])
    return {"measured": rho_lw_meas, **lw} if rho_lw_meas else lw


def compute(measurements: dict | None = None, want_items: bool = False):
    mats = load_json("config/materials.json")
    meas = measurements if measurements is not None else load_json("config/measurements.json")
    parts = g.load()
    pbn = {p.name: p for p in parts}
    cache = {}

    def geo(name):
        if name not in cache:
            m = pbn[name].mesh()
            cache[name] = (abs(m.volume) / 1000, np.array(m.center_mass), m)
        return cache[name]

    rho = {k: v["value"] for k, v in mats["densities_g_cm3"].items()}
    rho_lw_meas = (meas.get("stage1") or {}).get("lwpla_effective_density_g_cm3")
    measured = (meas.get("component_masses_g") or {}).get("values", {})

    # ---------- fixed (non-polymer) items ----------
    items = []  # (label, group, mass_g, xyz, basis, source)
    t = mats["carbon_tube"]
    for p in parts:
        if p.cls == "carbon":
            a, b, L = g.carbon_dims(p.name)
            area = a * b - (a - 2 * t["wall_mm"]) * (b - 2 * t["wall_mm"])
            m = area * L / 1000 * t["density_g_cm3"]
            items.append((p.name, "Structure", m, geo(p.name)[1], "computed", p.name))
        elif p.cls == "g10":
            v, c, _ = geo(p.name)
            items.append((p.name, "Structure", v * rho["G10"], c, "computed", p.name))

    printed = [p for p in parts if p.cls == "printed"]
    poly_xyz = np.average([geo(p.name)[1] for p in printed], axis=0, weights=[geo(p.name)[0] for p in printed])
    g10_xyz = np.average([geo(p.name)[1] for p in parts if p.cls == "g10"], axis=0,
                         weights=[geo(p.name)[0] for p in parts if p.cls == "g10"])
    assumptions = []
    with open(ROOT / "bom" / "bom.csv", newline="") as fh:
        for r in csv.DictReader(fh):
            q = float(r["installed_qty"])
            if q <= 0 or r["stage"] == "ALT" or r["mass_basis"] in ("none", "geometry"):
                continue
            unit = float(measured.get(r["id"], r["unit_mass_g"]))
            basis = "measured" if r["id"] in measured else r["mass_basis"]
            total = unit * q
            pl = r["placement"].strip()
            if pl.startswith("distributed:"):
                where = {"printed": poly_xyz, "g10": g10_xyz}[pl.split(":")[1]]
                items.append((r["id"], r["group"], total, where, basis, pl))
                continue
            entries = [e for e in pl.split(";") if e]
            placed = []  # (where, xyz, weight)
            for e in entries:
                if e.startswith(("xyz:", "site:")):
                    body, _, w = e.split(":", 1)[1].partition(":")
                    xyz = np.array([float(v) for v in body.split(",")])
                    placed.append((e, xyz, float(w) if w else 1.0))
                    if e.startswith("xyz:"):
                        assumptions.append(f"{r['id']} {r['item']}: position assumed at {body} (not in the V18 model)")
                    continue
                name, _, w = e.partition(":")
                if name not in pbn:
                    raise KeyError(f"BOM {r['id']}: placement object {name} not in V18 assembly")
                placed.append((name, geo(name)[1], float(w) if w else 1.0))
            wsum = sum(w for *_, w in placed)
            for where, loc, w in placed:
                items.append((r["id"], r["group"], total * w / wsum, loc, basis, where))

    if want_items:
        return items, [(name, mat, v, c) for name, mat, v, c in
                       [(p.name, material_for(g.template_name(p.name), mats["rules"]), *geo(p.name)[:2]) for p in printed]], rho, lw_cases_for(mats, rho_lw_meas)
    fixed_mass = sum(i[2] for i in items)
    fixed_moment = sum(i[2] * np.asarray(i[3]) for i in items)

    # ---------- polymer cases ----------
    poly_rows = []
    for p in printed:
        v, c, _ = geo(p.name)
        mat = material_for(g.template_name(p.name), mats["rules"])
        poly_rows.append((p.name, mat, v, c))

    cases = {}
    lw_cases = dict(mats["lwpla_cases"])
    if rho_lw_meas:
        lw_cases = {"measured": rho_lw_meas, **lw_cases}
    for case, lw in lw_cases.items():
        pm, pmom = 0.0, np.zeros(3)
        by_mat = {}
        for name, mat, v, c in poly_rows:
            d = lw if mat == "LW-PLA" else rho[mat]
            pm += v * d
            pmom += v * d * c
            by_mat[mat] = by_mat.get(mat, 0) + v * d
        M = fixed_mass + pm
        cg = (fixed_moment + pmom) / M
        loads = hover_split(M, cg[:2], motor_positions(pbn))
        cases[case] = {
            "lwpla_density": lw, "polymer_g": round(pm, 1), "polymer_by_material_g": {k: round(v, 1) for k, v in by_mat.items()},
            "all_up_g": round(M, 1), "cg_mm": [round(float(x), 1) for x in cg],
            "motor_hover_g": {k: round(v, 1) for k, v in loads.items()},
            "worst_motor": max(loads, key=loads.get),
        }

    groups = {}
    for lab, grp, m, *_ in items:
        groups[grp] = groups.get(grp, 0) + m
    top = sorted(items, key=lambda i: -i[2])[:12]
    design = "measured" if "measured" in cases else "planning"
    out = {
        "_note": "Generated by tools/mass_cg.py. All-up mass and CG are PROVISIONAL until Stage-9 weighing.",
        "design_case": design,
        "measured_all_up_g": (meas.get("stage9") or {}).get("all_up_mass_g"),
        "measured_cg_x_mm": (meas.get("stage9") or {}).get("flight_cg_x_mm"),
        "hardware_and_structure_g": round(fixed_mass, 1),
        "hardware_by_group_g": {k: round(v, 1) for k, v in sorted(groups.items(), key=lambda kv: -kv[1])},
        "heaviest_items": [{"item": i[0], "g": round(i[2], 1), "xyz": [round(float(x)) for x in i[3]], "basis": i[4]} for i in top],
        "motor_xy_mm": {k: [round(float(x), 1) for x in v] for k, v in motor_positions(pbn).items()},
        "equal_thrust_centroid_x_mm": round(float(np.mean([v[0] for v in motor_positions(pbn).values()])), 1),
        "cases": cases,
        "assumptions": assumptions,
    }
    return out


def mass_model() -> dict:
    """Linear mass model for tools/budget.py and the web calculator (no geometry needed there):
    every hardware item with its BOM id and position, plus polymer volume/moment per material."""
    items, poly, rho, lw = compute(measurements={}, want_items=True)
    pm = {}
    for name, mat, v, c in poly:
        e = pm.setdefault(mat, {"volume_cm3": 0.0, "moment_cm3_mm": [0.0, 0.0, 0.0]})
        e["volume_cm3"] += v
        for k in range(3):
            e["moment_cm3_mm"][k] += v * float(c[k])
    for e in pm.values():
        e["volume_cm3"] = round(e["volume_cm3"], 3)
        e["moment_cm3_mm"] = [round(x, 2) for x in e["moment_cm3_mm"]]
    pbn = {p.name: p for p in g.load()}
    return {
        "_note": "Generated by tools/mass_cg.py from the V18 assembly and bom/bom.csv. Mass = sum(items) + sum(volume x density). "
                 "Items whose id is a BOM id scale with measured component masses (ratio to bom_unit_g).",
        "items": [{"id": i[0], "group": i[1], "g": round(i[2], 3), "xyz": [round(float(x), 1) for x in i[3]],
                   "basis": i[4], "where": i[5]} for i in items],
        "bom_unit_g": {r_id: u for r_id, u in _bom_units().items()},
        "polymer": pm,
        "densities_g_cm3": {k: v for k, v in rho.items()},
        "lwpla_cases": lw,
        "motor_xy_mm": {k: [round(float(x), 1) for x in v] for k, v in motor_positions(pbn).items()},
    }


def _bom_units() -> dict:
    with open(ROOT / "bom" / "bom.csv", newline="") as fh:
        return {r["id"]: float(r["unit_mass_g"]) for r in csv.DictReader(fh)}


def main() -> int:
    out = compute()
    (ROOT / "analysis").mkdir(exist_ok=True)
    (ROOT / "analysis" / "mass_cg.json").write_text(json.dumps(out, indent=1))
    (ROOT / "analysis" / "mass_model.json").write_text(json.dumps(mass_model(), indent=1))
    print(json.dumps({k: out[k] for k in ("hardware_and_structure_g", "hardware_by_group_g", "cases", "assumptions")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
