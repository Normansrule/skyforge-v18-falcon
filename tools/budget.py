#!/usr/bin/env python3
"""SKYFORGE V18 running cost + mass + CG + hover-reserve + stability budget.

    python3 tools/budget.py [--measurements config/measurements.json] [--out docs]

Inputs (no CAD libraries needed):
  bom/bom.csv                  cost rows, stages, owned items
  analysis/mass_model.json     V18-placed masses (tools/mass_cg.py)
  analysis/aero.json           neutral-point band (tools/aero_vlm.py)
  config/power.json            battery, connector class, gate thresholds
  config/measurements.json     everything measured so far (null = not yet)
Outputs: <out>/BOM.md, <out>/BUDGET.md, <out>/budget_summary.json

site/js/budget.js implements the same arithmetic for the web calculator; tests/test_budget_parity.mjs
checks the two agree. Change both together.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "ALT"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def load_bom() -> list[dict]:
    with open(ROOT / "bom" / "bom.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("buy_qty", "installed_qty", "row_usd_low", "row_usd_high", "unit_mass_g"):
            r[k] = float(r[k])
    return rows


def interp(table, x_key, y_key, x):
    pts = sorted((float(p[x_key]), float(p[y_key])) for p in table)
    if not pts:
        return None
    if x <= pts[0][0]:
        return pts[0][1] * x / pts[0][0] if pts[0][0] else pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None  # never extrapolate beyond the measured range


def gate(v, pass_max=None, fix_max=None, pass_min=None, fix_min=None):
    if v is None or v != v:  # None or NaN
        return "UNKNOWN"
    if pass_max is not None:
        return "PASS" if v <= pass_max else ("FIX" if v <= fix_max else "STOP")
    return "PASS" if v >= pass_min else ("FIX" if v >= fix_min else "STOP")


def hover_split(total, cg, motors):
    """Minimum-norm motor thrusts balancing weight and both moments (3 x 4 system, closed form)."""
    names = list(motors)
    xs = [motors[n][0] - cg[0] for n in names]
    ys = [motors[n][1] - cg[1] for n in names]
    A = [[1.0] * 4, xs, ys]
    AAt = [[sum(A[i][k] * A[j][k] for k in range(4)) for j in range(3)] for i in range(3)]
    lam = solve3(AAt, [total, 0.0, 0.0])
    return {n: sum(A[i][k] * lam[i] for i in range(3)) for k, n in enumerate(names)}


def solve3(M, b):
    import copy

    m = copy.deepcopy(M)
    v = list(b)
    for c in range(3):
        p = max(range(c, 3), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        v[c], v[p] = v[p], v[c]
        for r in range(3):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [m[r][k] - f * m[c][k] for k in range(3)]
                v[r] -= f * v[c]
    return [v[i] / m[i][i] for i in range(3)]


def mass_state(model, lw_density, measured_g):
    """All-up mass (g) and CG (mm) for an LW-PLA density and measured component masses."""
    M, mom = 0.0, [0.0, 0.0, 0.0]
    units = model["bom_unit_g"]
    for it in model["items"]:
        m = it["g"]
        if measured_g.get(it["id"]) is not None and units.get(it["id"]):
            m *= float(measured_g[it["id"]]) / units[it["id"]]
        M += m
        for k in range(3):
            mom[k] += m * it["xyz"][k]
    for mat, e in model["polymer"].items():
        d = lw_density if mat == "LW-PLA" else model["densities_g_cm3"][mat]
        M += e["volume_cm3"] * d
        for k in range(3):
            mom[k] += e["moment_cm3_mm"][k] * d
    return M, [x / M for x in mom]


def compute(meas: dict) -> dict:
    pwr = load_json(ROOT / "config" / "power.json")
    model = load_json(ROOT / "analysis" / "mass_model.json")
    aero = load_json(ROOT / "analysis" / "aero.json")
    bom = load_bom()
    owned = set(meas.get("owned_items", {}).get("ids", []))
    measured_g = meas.get("component_masses_g", {}).get("values", {})
    g = pwr["gates"]

    aircraft = [r for r in bom if r["group"] != "Extras" and r["stage"] != "ALT"]
    extras = [r for r in bom if r["group"] == "Extras"]
    cost = {
        "aircraft": [sum(r["row_usd_low"] for r in aircraft), sum(r["row_usd_high"] for r in aircraft)],
        "extras": [sum(r["row_usd_low"] for r in extras), sum(r["row_usd_high"] for r in extras)],
    }
    cost["contingency"] = [0.15 * cost["aircraft"][0], 0.20 * cost["aircraft"][1]]
    cost["from_scratch"] = [cost["aircraft"][i] + cost["contingency"][i] + cost["extras"][i] for i in (0, 1)]
    cost["remaining"] = [sum(r["row_usd_low" if i == 0 else "row_usd_high"] for r in aircraft + extras if r["id"] not in owned)
                         + cost["contingency"][i] for i in (0, 1)]
    by_stage = {}
    for r in aircraft + extras:
        e = by_stage.setdefault(r["stage"], [0.0, 0.0])
        e[0] += r["row_usd_low"]
        e[1] += r["row_usd_high"]

    rho_meas = (meas.get("stage1") or {}).get("lwpla_effective_density_g_cm3")
    cases = {}
    lw_cases = dict(model["lwpla_cases"])
    if rho_meas:
        lw_cases = {"measured": rho_meas, **lw_cases}
    for name, d in lw_cases.items():
        M, cg = mass_state(model, d, measured_g)
        cases[name] = {"lwpla": d, "all_up_g": M, "cg_mm": cg}
    design = "measured" if rho_meas else "planning"
    M, cg = cases[design]["all_up_g"], cases[design]["cg_mm"]
    s9 = meas.get("stage9") or {}
    basis = f"MODEL ({design} LW-PLA {lw_cases[design]:.2f})"
    if s9.get("all_up_mass_g"):
        M, basis = float(s9["all_up_mass_g"]), "MEASURED mass"
    if s9.get("flight_cg_x_mm") is not None:
        cg = [float(s9["flight_cg_x_mm"]), float(s9.get("flight_cg_y_mm") or 0.0), cg[2]]
        basis += " + MEASURED CG"

    motors = {k: tuple(v) for k, v in model["motor_xy_mm"].items()}
    loads = hover_split(M, cg, motors)
    worst_name = max(loads, key=loads.get)
    worst = loads[worst_name]
    rotor_cx = sum(v[0] for v in motors.values()) / 4

    s2 = meas.get("stage2") or {}
    tmax = s2.get("max_static_thrust_g_loaded")
    table = s2.get("thrust_table") or []
    hover_frac = worst / tmax if tmax else None
    hover_current = None
    if table:
        cur = [interp(table, "thrust_g", "current_a", max(t, 0.0)) for t in loads.values()]
        if all(c is not None for c in cur):
            hover_current = sum(cur) + pwr["avionics_video_servo_avg_current_a"]
    cap_ah = pwr["battery_capacity_mah"] / 1000 * pwr["usable_capacity_fraction"]
    hover_min = cap_ah / hover_current * 60 if hover_current else None
    mass_for_pass = M * (g["hover_fraction_pass_max"] * tmax) / worst if tmax else None

    peak = s9.get("simultaneous_lift_plus_edf_peak_a")
    worst_all = None
    if s2.get("max_current_a") and s2.get("edf_max_current_a"):
        worst_all = 4 * s2["max_current_a"] + s2["edf_max_current_a"] + pwr["avionics_video_servo_avg_current_a"]
    if peak is not None:
        peak_basis = "MEASURED"
    elif table and s2.get("edf_max_current_a") and tmax:
        per = [interp(table, "thrust_g", "current_a", min(1.3 * max(t, 0.0), tmax)) for t in loads.values()]
        peak = sum(per) + s2["edf_max_current_a"] + pwr["avionics_video_servo_avg_current_a"] if all(p is not None for p in per) else None
        peak_basis = "estimated transition: lift at 1.3 x hover + EDF max + avionics"
    else:
        peak_basis = "UNKNOWN until Stage 2"
    conn_a = pwr["connector_class_continuous_a"][pwr["main_connector"]]
    batt_label_a = pwr["battery_capacity_mah"] / 1000 * pwr["battery_c_rating_continuous_label"]

    band = aero["neutral_point_band_x_mm"]
    mac = aero["planform"]["mac_m"] * 1000
    np_fwd, np_aft = min(band.values()), max(band.values())
    sm_fwd = (np_fwd - cg[0]) / mac
    sm_aft = (np_aft - cg[0]) / mac

    gates = [
        {"id": "G1", "gate": "Hover balance: |CG x - rotor centroid x|", "value": abs(cg[0] - rotor_cx), "unit": "mm",
         "status": gate(abs(cg[0] - rotor_cx), pass_max=g["cg_offset_pass_mm"], fix_max=g["cg_offset_fix_mm"]), "basis": basis},
        {"id": "G2", "gate": f"Worst motor share of weight ({worst_name})", "value": 100 * worst / M, "unit": "%",
         "status": gate(100 * worst / M, pass_max=g["worst_share_pass_pct"], fix_max=g["worst_share_fix_pct"]), "basis": basis},
        {"id": "G3", "gate": "Static margin, most forward neutral point", "value": 100 * sm_fwd, "unit": "% MAC",
         "status": gate(100 * sm_fwd, pass_min=g["static_margin_pass_pct"], fix_min=g["static_margin_fix_pct"]),
         "basis": f"{basis}; NP band x{np_fwd:.0f}-{np_aft:.0f}"},
        {"id": "G4", "gate": "Worst-motor hover fraction of measured max thrust", "value": hover_frac, "unit": "",
         "status": gate(hover_frac, pass_max=g["hover_fraction_pass_max"], fix_max=g["hover_fraction_fix_max"]),
         "basis": "Stage-2 bench"},
        {"id": "G5", "gate": f"Hover endurance at {pwr['usable_capacity_fraction']:.0%} of {pwr['battery_capacity_mah']} mAh",
         "value": hover_min, "unit": "min",
         "status": gate(hover_min, pass_min=g["hover_minutes_pass_min"], fix_min=g["hover_minutes_fix_min"]), "basis": "Stage-2 thrust table"},
        {"id": "G6", "gate": f"Transition peak current vs {pwr['main_connector']} class {conn_a} A", "value": peak, "unit": "A",
         "status": ("PASS" if peak <= conn_a else "STOP") if peak else "UNKNOWN", "basis": peak_basis},
        {"id": "G7", "gate": f"Transition peak vs 70 % of battery label ({batt_label_a:.0f} A)", "value": peak, "unit": "A",
         "status": ("PASS" if peak <= 0.7 * batt_label_a else "FIX") if peak else "UNKNOWN", "basis": peak_basis},
    ]
    return {
        "cost_usd": cost, "spend_by_stage": by_stage, "owned": sorted(owned),
        "mass_cases": cases, "design_case": design, "all_up_g": M, "cg_mm": cg, "basis": basis,
        "rotor_centroid_x_mm": rotor_cx, "motor_hover_g": loads, "worst_motor": worst_name,
        "bench_max_thrust_needed_g": {"PASS": worst / g["hover_fraction_pass_max"], "FIX": worst / g["hover_fraction_fix_max"]},
        "mass_for_hover_pass_g": mass_for_pass, "hover_current_a": hover_current, "worst_case_current_a": worst_all,
        "neutral_point_band_x_mm": band, "mac_mm": mac, "static_margin_pct": [100 * sm_fwd, 100 * sm_aft],
        "cg_window_x_mm": [np_fwd - g["static_margin_target_pct"] / 100 * mac, np_fwd - g["static_margin_pass_pct"] / 100 * mac],
        "gates": gates,
    }


def fmt(v, nd=1):
    if v is None:
        return "-"
    return f"{v:,.{nd}f}" if isinstance(v, float) else str(v)


def write_docs(res, out: Path, bom, model):
    lines = ["# Bill of materials (generated)", "",
             "> Generated by `tools/budget.py` from `bom/bom.csv` - edit the CSV, not this file.",
             "> V18 rows come from the V18 `BOM_AND_BUDGET.md` (kept in `cad/v18/`); **ADD** rows close the gaps the brief listed.",
             "> Every named part is a **reference candidate** until fit and performance are verified. Whole-row USD planning",
             "> allowances, excluding shipping/tax; verify variant, stock and price before buying.", "",
             "Change tags: **ADD** new line, **FIX** tightened gate, **RESCOPE** split out of a vague V18 row, **KEEP** V18 row retained, **ALT** optional (not counted).",
             "Placement: where the mass model puts the item - a V18 object, `xyz:` (assumed, not in the V18 model) or `geometry:` (mass from V18 meshes).", ""]
    groups = []
    for r in bom:
        if r["group"] not in groups:
            groups.append(r["group"])
    for grp in groups:
        lines += [f"## {grp}", "", "| ID | Stage | Item | Reference candidate | Buy | Inst. | USD row | Unit g | Dimensions (mm) | Purchase gate | Change |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in [x for x in bom if x["group"] == grp]:
            basis = {"vendor": "v", "estimate": "e", "computed": "c", "none": "-", "geometry": "geo"}[r["mass_basis"]]
            lines.append(f"| {r['id']} | {r['stage']} | {r['item']} | [{r['reference_candidate']}]({r['url']}) | {r['buy_qty']:g} | "
                         f"{r['installed_qty']:g} | {r['row_usd_low']:.0f}-{r['row_usd_high']:.0f} | {r['unit_mass_g']:g} ({basis}) | "
                         f"{r['dims_mm']} | {r['purchase_gate']} | {r['change']} |")
        lines.append("")
    lines += ["Mass basis: (v) vendor listing, (e) estimate - weigh it, (geo) from V18 meshes. Measured masses go in `config/measurements.json`.", ""]
    (out / "BOM.md").write_text("\n".join(lines))

    c = res["cost_usd"]
    L = ["# Running budget: cost, mass, CG, hover and stability (generated)", "",
         "> Generated by `tools/budget.py` from the BOM, the V18 mass model and the aero model. Re-run after any change.",
         f"> Basis: **{res['basis']}**.", "", "## Cost", "", "| Bucket | Low USD | High USD |", "|---|---|---|",
         f"| Aircraft subtotal (V18 rows + added rows, incl. installed FPV) | {c['aircraft'][0]:,.0f} | {c['aircraft'][1]:,.0f} |",
         f"| Contingency (15 % of low / 20 % of high) | {c['contingency'][0]:,.0f} | {c['contingency'][1]:,.0f} |",
         f"| Extras if not owned (radio, monitor, charger, tools) | {c['extras'][0]:,.0f} | {c['extras'][1]:,.0f} |",
         f"| **From scratch, excl. printer** | **{c['from_scratch'][0]:,.0f}** | **{c['from_scratch'][1]:,.0f}** |",
         f"| Remaining after owned items ({', '.join(res['owned']) or 'none listed'}) | {c['remaining'][0]:,.0f} | {c['remaining'][1]:,.0f} |", "",
         "V18 BOM aircraft subtotal for comparison: USD 728-1,221.", "", "Spend by stage:", "", "| Stage | Low | High |", "|---|---|---|"]
    for s in STAGES:
        if s in res["spend_by_stage"] and s != "ALT":
            v = res["spend_by_stage"][s]
            L.append(f"| {s} | {v[0]:,.0f} | {v[1]:,.0f} |")
    L += ["", "## Mass and centre of gravity (V18 positions)", "",
          "| LW-PLA case | Density g/cm3 | All-up g | CG x mm | CG y mm |", "|---|---|---|---|---|"]
    for k, v in res["mass_cases"].items():
        L.append(f"| {k} | {v['lwpla']:.2f} | {v['all_up_g']:,.0f} | {v['cg_mm'][0]:.1f} | {v['cg_mm'][1]:+.1f} |")
    L += ["", "The old ~1.5 kg finished-aircraft claim is not supported. CG barely moves with density: hardware and skin are both aft.", "",
          "## Hover", "", f"Rotor thrust centroid x{res['rotor_centroid_x_mm']:.0f}; CG x{res['cg_mm'][0]:.1f}.", "",
          "| Motor | Hover thrust g | Bench max needed for PASS (<= 50 %) g | ...for FIX (<= 60 %) g |", "|---|---|---|---|"]
    pw = load_json(ROOT / "config" / "power.json")["gates"]
    for k, v in res["motor_hover_g"].items():
        L.append(f"| {k} | {v:,.0f} | {max(v, 0) / pw['hover_fraction_pass_max']:,.0f} | {max(v, 0) / pw['hover_fraction_fix_max']:,.0f} |")
    L += ["", "A motor near 0 g means the CG sits on the other rotor row: the front pair is doing almost nothing.", "",
          "## Wing-borne stability", "",
          f"Neutral-point band (vortex lattice on the V18 planform, `analysis/aero.json`): x{min(res['neutral_point_band_x_mm'].values()):.0f}"
          f"-x{max(res['neutral_point_band_x_mm'].values()):.0f}; MAC {res['mac_mm']:.0f} mm.", "",
          f"Static margin at the current CG: {res['static_margin_pct'][0]:.1f} % to {res['static_margin_pct'][1]:.1f} % MAC "
          f"(negative = unstable). CG window for 5-12 % margin on the forward NP: x{res['cg_window_x_mm'][0]:.0f}-x{res['cg_window_x_mm'][1]:.0f}.", "",
          "See `docs/BALANCE_AND_STABILITY.md` for the balance study.", "",
          "## Gates", "", "| ID | Gate | Value | Status | Basis |", "|---|---|---|---|---|"]
    for gt in res["gates"]:
        v = gt["value"]
        L.append(f"| {gt['id']} | {gt['gate']} | {fmt(v, 2 if gt['unit'] == '' else 1)} {gt['unit']} | **{gt['status']}** | {gt['basis']} |")
    L += ["", "**PASS** proceed; **FIX** change something and re-check; **STOP** do not buy the remaining motors or bulk-print until redesigned; "
          "**UNKNOWN** the measurement does not exist yet. G1-G3 are model gates (V18 geometry + BOM); G4-G7 need the Stage-2 bench.", ""]
    (out / "BUDGET.md").write_text("\n".join(L))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--measurements", default=str(ROOT / "config" / "measurements.json"))
    ap.add_argument("--out", default=str(ROOT / "docs"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    meas = load_json(Path(a.measurements))
    res = compute(meas)
    write_docs(res, out, load_bom(), None)
    (out / "budget_summary.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("all_up_g", "cg_mm", "motor_hover_g", "static_margin_pct")}, default=float))
    for gt in res["gates"]:
        print(f"{gt['id']} {gt['status']:8s} {gt['gate']}: {fmt(gt['value'])} {gt['unit']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
