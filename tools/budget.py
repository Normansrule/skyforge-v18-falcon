#!/usr/bin/env python3
"""SKYFORGE V18 running mass + cost + hover-reserve budget.

Reads bom/bom.csv, config/geometry.json, config/power.json and config/measurements.json.
Writes docs/BOM.md and docs/BUDGET.md, and budget_summary.json. Re-run after ANY change to
components, measurements, battery, or geometry:

    python3 tools/budget.py

Everything computed from estimates is labelled PROVISIONAL. Gates only become PASS/FIX/STOP
when the inputs they depend on have been measured.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = ["S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10", "ALT"]


def load_json(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text())


def load_bom() -> list[dict]:
    with open(ROOT / "bom" / "bom.csv", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("buy_qty", "installed_qty", "row_usd_low", "row_usd_high", "unit_mass_g"):
            r[k] = float(r[k])
    return rows


def interp(table: list[dict], x_key: str, y_key: str, x: float):
    pts = sorted((float(p[x_key]), float(p[y_key])) for p in table)
    if not pts:
        return None
    if x <= pts[0][0]:
        return pts[0][1] * (x / pts[0][0]) if pts[0][0] else pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None  # beyond the measured range: do not extrapolate


def gate(value, pass_max=None, fix_max=None, pass_min=None, fix_min=None):
    if value is None:
        return "UNKNOWN"
    if pass_max is not None:
        return "PASS" if value <= pass_max else ("FIX" if value <= fix_max else "STOP")
    return "PASS" if value >= pass_min else ("FIX" if value >= fix_min else "STOP")


def motor_loads(mass_g: float, cg_x: float, geo: dict) -> dict:
    """Static hover thrust each motor must make (g) for a CG on the centreline.
    Front pair at x_f, rear pair at x_r; moment balance about the CG."""
    x_f = geo["lift_motors"]["M1"]["x"]
    x_r = geo["lift_motors"]["M2"]["x"]
    front_share = (x_r - cg_x) / (x_r - x_f)
    front_each = mass_g * front_share / 2
    rear_each = mass_g * (1 - front_share) / 2
    return {"M1": front_each, "M3": front_each, "M2": rear_each, "M4": rear_each,
            "front_share": front_share}


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--measurements", default="config/measurements.json")
    ap.add_argument("--out", default=None, help="write generated docs here instead of docs/ (used by tests)")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else ROOT / "docs"
    out.mkdir(parents=True, exist_ok=True)
    geo = load_json("config/geometry.json")
    pwr = load_json("config/power.json")
    meas = json.loads((ROOT / args.measurements).read_text()) if not Path(args.measurements).is_absolute() else json.loads(Path(args.measurements).read_text())
    bom = load_bom()
    owned = set(meas.get("owned_items", {}).get("ids", []))
    measured_mass = meas.get("component_masses_g", {}).get("values", {})

    # ---------- cost ----------
    aircraft = [r for r in bom if r["group"] not in ("Extras",) and r["stage"] != "ALT"]
    extras = [r for r in bom if r["group"] == "Extras"]
    ac_lo = sum(r["row_usd_low"] for r in aircraft)
    ac_hi = sum(r["row_usd_high"] for r in aircraft)
    ex_lo = sum(r["row_usd_low"] for r in extras)
    ex_hi = sum(r["row_usd_high"] for r in extras)
    cont_lo, cont_hi = 0.15 * ac_lo, 0.20 * ac_hi
    rem_lo = sum(r["row_usd_low"] for r in aircraft + extras if r["id"] not in owned) + cont_lo
    rem_hi = sum(r["row_usd_high"] for r in aircraft + extras if r["id"] not in owned) + cont_hi
    by_stage = {s: [0.0, 0.0] for s in STAGES}
    for r in aircraft + extras:
        by_stage[r["stage"]][0] += r["row_usd_low"]
        by_stage[r["stage"]][1] += r["row_usd_high"]

    # ---------- mass ----------
    hw_rows = []
    for r in bom:
        if r["installed_qty"] <= 0 or r["stage"] == "ALT":
            continue
        unit = float(measured_mass.get(r["id"], r["unit_mass_g"]))
        basis = "measured" if r["id"] in measured_mass else r["mass_basis"]
        hw_rows.append((r, unit, basis, unit * r["installed_qty"]))
    hw_mass = sum(m for *_, m in hw_rows)
    hw_measured = sum(m for _, _, b, m in hw_rows if b == "measured")
    poly = geo["polymer"]
    vol = poly["permanent_volume_cm3"]
    rho_meas = meas["stage1"].get("lwpla_effective_density_g_cm3")
    poly_cases = {
        "best (LW-PLA 0.60 assumed)": vol * poly["lwpla_best_case_density_g_cm3"],
        "planning (LW-PLA 0.80 assumed)": vol * poly["lwpla_planning_density_g_cm3"],
        "worst (solid PLA 1.24)": vol * poly["solid_pla_density_g_cm3"],
    }
    if rho_meas:
        poly_cases = {f"measured LW-PLA {rho_meas:.2f}": vol * rho_meas, **poly_cases}
    measured_auw = meas["stage9"].get("all_up_mass_g")
    totals = {k: hw_mass + v for k, v in poly_cases.items()}
    design_case = next(iter(poly_cases)) if rho_meas else "planning (LW-PLA 0.80 assumed)"
    auw = measured_auw or totals[design_case]
    auw_label = "MEASURED" if measured_auw else f"PROVISIONAL ({design_case})"

    # ---------- per-motor load & hover reserve ----------
    g = pwr["gates"]
    cg_meas = meas["stage9"].get("flight_cg_x_mm")
    sweep = [315, 320, 325, 330, 335, 340, 345, 350, 355, 360]
    cg_rows = []
    for cg in ([cg_meas] if cg_meas else []) + sweep:
        ld = motor_loads(auw, cg, geo)
        worst = max(ld["M1"], ld["M2"])
        cg_rows.append((cg, ld, worst, worst / g["hover_fraction_pass_max"],
                        worst / g["hover_fraction_fix_max"]))

    s2 = meas["stage2"]
    tmax = s2.get("max_static_thrust_g_loaded")
    table = s2.get("thrust_table") or []
    cg_for_gate = cg_meas if cg_meas else 345.0  # conservative aft-of-centroid assumption
    ld_gate = motor_loads(auw, cg_for_gate, geo)
    worst_gate = max(ld_gate["M1"], ld_gate["M2"])
    hover_frac = worst_gate / tmax if tmax else None
    hover_gate = gate(hover_frac, pass_max=g["hover_fraction_pass_max"], fix_max=g["hover_fraction_fix_max"])
    hover_current = None
    if table:
        currents = [interp(table, "thrust_g", "current_a", ld_gate[m]) for m in ("M1", "M2", "M3", "M4")]
        if all(c is not None for c in currents):
            hover_current = sum(currents) + pwr["avionics_video_servo_avg_current_a"]
    cap_ah = pwr["battery_capacity_mah"] / 1000 * pwr["usable_capacity_fraction"]
    hover_min = cap_ah / hover_current * 60 if hover_current else None
    hover_min_gate = gate(hover_min, pass_min=g["hover_minutes_pass_min"], fix_min=g["hover_minutes_fix_min"])
    mass_for_pass = None
    if tmax:
        # mass at which the worst motor hovers at exactly the PASS fraction (same CG)
        mass_for_pass = auw * (g["hover_fraction_pass_max"] * tmax) / worst_gate

    # Transition case: all four lift motors at 1.3 x hover thrust (control margin) + EDF at max.
    # Absolute worst case: everything at max. The connector/battery gates use the transition case;
    # the worst case is reported so nobody is surprised by it.
    peak = meas["stage9"].get("simultaneous_lift_plus_edf_peak_a")
    worst_all = None
    if s2.get("max_current_a") and s2.get("edf_max_current_a"):
        worst_all = 4 * s2["max_current_a"] + s2["edf_max_current_a"] + pwr["avionics_video_servo_avg_current_a"]
    if peak is not None:
        peak_label = "MEASURED"
    elif table and s2.get("edf_max_current_a") and tmax:
        per = [interp(table, "thrust_g", "current_a", min(1.3 * ld_gate[m], tmax)) for m in ("M1", "M2", "M3", "M4")]
        if all(c is not None for c in per):
            peak = sum(per) + s2["edf_max_current_a"] + pwr["avionics_video_servo_avg_current_a"]
        peak_label = "estimated transition case: lift at 1.3x hover + EDF max + avionics"
    else:
        peak_label = "UNKNOWN until Stage 2"
    conn = pwr["main_connector"]
    conn_a = pwr["connector_class_continuous_a"][conn]
    batt_c_a = pwr["battery_capacity_mah"] / 1000 * pwr["battery_c_rating_continuous_label"]

    # ---------- docs/BOM.md ----------
    lines = ["# Bill of materials (generated)", "",
             "> Generated by `tools/budget.py` from `bom/bom.csv` - edit the CSV, not this file.",
             "> Every named part is a **REFERENCE CANDIDATE** until fit and performance are verified.",
             "> Prices are whole-row USD planning allowances (no shipping/tax); verify variant, stock and price before buying.",
             "", "Change tags: **ADD** new line, **FIX** tightened gate, **RESCOPE** split out of a vague row, **KEEP** retained, **ALT** optional alternative (not counted).", ""]
    groups = []
    for r in bom:
        if r["group"] not in groups:
            groups.append(r["group"])
    for grp in groups:
        lines += [f"## {grp}", "",
                  "| ID | Stage | Item | Reference candidate | Buy | Inst. | USD row | Unit g | Dimensions (mm) | Purchase gate | Change |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in [x for x in bom if x["group"] == grp]:
            url = "../" + r["url"][5:] if r["url"].startswith("repo:") else r["url"]
            link = f"[{r['reference_candidate']}]({url})"
            unit = measured_mass.get(r["id"], r["unit_mass_g"])
            basis = "m" if r["id"] in measured_mass else {"vendor": "v", "estimate": "e", "computed": "c", "none": "-"}[r["mass_basis"]]
            lines.append(f"| {r['id']} | {r['stage']} | {r['item']} | {link} | {r['buy_qty']:g} | {r['installed_qty']:g} | "
                         f"{r['row_usd_low']:.0f}-{r['row_usd_high']:.0f} | {unit:g} ({basis}) | {r['dims_mm']} | {r['purchase_gate']} | {r['change']} |")
        lines.append("")
    lines += ["Mass basis: (v) vendor listing, (e) estimate - weigh it, (c) computed from geometry, (m) measured.", ""]
    (out / "BOM.md").write_text("\n".join(lines))

    # ---------- docs/BUDGET.md ----------
    L = ["# Running mass, cost and hover-reserve budget (generated)", "",
         "> Generated by `tools/budget.py`. Re-run after any component, battery, geometry or measurement change.",
         f"> All-up mass basis: **{auw_label}**.", "",
         "## Cost", "",
         "| Bucket | Low USD | High USD |", "|---|---|---|",
         f"| Aircraft subtotal (incl. installed FPV) | {ac_lo:,.0f} | {ac_hi:,.0f} |",
         f"| Contingency (15% of low / 20% of high) | {cont_lo:,.0f} | {cont_hi:,.0f} |",
         f"| Extras if not owned (tools, radio, charger, screen) | {ex_lo:,.0f} | {ex_hi:,.0f} |",
         f"| **From scratch, excl. printer** | **{ac_lo + cont_lo + ex_lo:,.0f}** | **{ac_hi + cont_hi + ex_hi:,.0f}** |",
         f"| Remaining spend after owned items ({', '.join(sorted(owned)) or 'none listed'}) | {rem_lo:,.0f} | {rem_hi:,.0f} |", "",
         "Spend by stage (buy only what the stage needs):", "",
         "| Stage | Low | High |", "|---|---|---|"]
    L += [f"| {s} | {v[0]:,.0f} | {v[1]:,.0f} |" for s, v in by_stage.items() if s != "ALT" and (v[0] or v[1])]
    L += ["", "## Mass", "",
          f"Installed hardware: **{hw_mass:,.0f} g** ({hw_measured:,.0f} g of it measured).", "",
          "| Polymer case (1,297.2 cm3 permanent polymer) | Polymer g | All-up g |", "|---|---|---|"]
    L += [f"| {k} | {v:,.0f} | {totals[k]:,.0f} |" for k, v in poly_cases.items()]
    if measured_auw:
        L.append(f"| **Measured all-up (Stage 9)** | - | **{measured_auw:,.0f}** |")
    L += ["", "The old ~1.5 kg finished-aircraft claim is not supported by any case above.", "",
          "Installed hardware by group:", "", "| Group | g |", "|---|---|"]
    grp_mass: dict[str, float] = {}
    for r, _, _, m in hw_rows:
        grp_mass[r["group"]] = grp_mass.get(r["group"], 0) + m
    L += [f"| {k} | {v:,.0f} |" for k, v in sorted(grp_mass.items(), key=lambda kv: -kv[1])]
    L += ["", "Heaviest installed items:", "", "| ID | Item | Qty | g each | g total | basis |", "|---|---|---|---|---|---|"]
    for r, unit, basis, m in sorted(hw_rows, key=lambda t: -t[3])[:10]:
        L.append(f"| {r['id']} | {r['item']} | {r['installed_qty']:g} | {unit:g} | {m:,.0f} | {basis} |")

    L += ["", "## Per-motor hover load vs CG", "",
          f"All-up mass used: {auw:,.0f} g ({auw_label}). Front pair at x={geo['lift_motors']['M1']['x']}, rear pair at x={geo['lift_motors']['M2']['x']}; "
          "CG assumed on the centreline. The x330 equal-thrust centroid is NOT the flight CG - the flight CG comes from Stage-9 aero work.", "",
          f"The last two columns are the **minimum measured max static thrust (loaded voltage) each lift motor must show on the Stage-2 bench** "
          f"to PASS (hover <= {g['hover_fraction_pass_max']:.0%} of max) or at least FIX (<= {g['hover_fraction_fix_max']:.0%}).", "",
          "| CG x (mm) | Front share | M1/M3 each g | M2/M4 each g | Worst motor g | Bench max needed for PASS g | ...for FIX g |",
          "|---|---|---|---|---|---|---|"]
    for cg, ld, worst, need_pass, need_fix in cg_rows:
        tag = " (measured)" if cg_meas and cg == cg_meas else ""
        L.append(f"| {cg:g}{tag} | {ld['front_share']:.0%} | {ld['M1']:,.0f} | {ld['M2']:,.0f} | {worst:,.0f} | {need_pass:,.0f} | {need_fix:,.0f} |")

    L += ["", "## Gates", "",
          "| Gate | Value | Status | Needs |", "|---|---|---|---|",
          f"| Worst-motor hover fraction at CG x{cg_for_gate:g}{' (measured)' if cg_meas else ' (assumed aft case)'} | "
          f"{'%.2f' % hover_frac if hover_frac else '-'} | **{hover_gate}** | Stage-2 `max_static_thrust_g_loaded` |",
          f"| Hover endurance at {pwr['usable_capacity_fraction']:.0%} usable of {pwr['battery_capacity_mah']} mAh | "
          f"{'%.1f min' % hover_min if hover_min else '-'} | **{hover_min_gate}** | Stage-2 `thrust_table` covering the hover thrust |",
          f"| Mass that would PASS the hover gate at this CG | {'%.0f g' % mass_for_pass if mass_for_pass else '-'} | "
          f"{'reduce by %.0f g' % (auw - mass_for_pass) if mass_for_pass and mass_for_pass < auw else ('OK' if mass_for_pass else 'UNKNOWN')} | Stage-2 bench |",
          f"| Simultaneous lift + EDF peak current ({peak_label}) | {'%.0f A' % peak if peak else '-'} | "
          f"**{('PASS' if peak <= conn_a else 'STOP') if peak else 'UNKNOWN'}** vs {conn} class {conn_a} A | Stage 2 / Stage 9 |",
          f"| Absolute worst case, everything at max (report only) | {'%.0f A' % worst_all if worst_all else '-'} | "
          f"{'exceeds ' + conn if worst_all and worst_all > conn_a else ('-' if not worst_all else 'within ' + conn)} | Cap with Q_M_BAT_CURR_MAX and THR_MAX (verify names in your firmware) if it exceeds |",
          f"| Same peak vs battery label ({pwr['battery_c_rating_continuous_label']}C = {batt_c_a:.0f} A) | {'%.0f A' % peak if peak else '-'} | "
          f"**{('PASS' if peak <= 0.7 * batt_c_a else 'FIX') if peak else 'UNKNOWN'}** (PASS <= 70% of label) | Label C is optimistic; watch loaded voltage + temperature |",
          "", "Status meanings: **PASS** proceed to the next stage; **FIX** change something (mass, prop, CG, connector) and re-measure; "
          "**STOP** do not buy the remaining motors / bulk-print until redesigned; **UNKNOWN** the measurement does not exist yet.", ""]
    (out / "BUDGET.md").write_text("\n".join(L))

    summary = {"aircraft_usd": [ac_lo, ac_hi], "contingency_usd": [cont_lo, cont_hi], "extras_usd": [ex_lo, ex_hi],
               "installed_hardware_g": hw_mass, "polymer_cases_g": poly_cases, "all_up_g": auw, "all_up_basis": auw_label,
               "hover_fraction": hover_frac, "hover_gate": hover_gate, "hover_minutes": hover_min,
               "hover_minutes_gate": hover_min_gate, "transition_peak_current_a": peak, "worst_case_current_a": worst_all,
               "bench_max_thrust_needed_for_pass_g_at_cg345": next(r[3] for r in cg_rows if r[0] == 345)}
    (out / "budget_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
