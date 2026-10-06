#!/usr/bin/env python3
"""Write docs/V19_VARIANTS.md from analysis/v19_variants.json, analysis/v19_search.json and config/v19/.

    python3 tools/v19/report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "v19"))

ORDER = ["v19a_long_nose", "v19b_falcon_tail", "v19c_forward_rotors", "v19r_boom_rotors", "v19w_four_in_wings", "v19s_stoop_crest"]
SHORT = {"v19a_long_nose": "V19-A", "v19b_falcon_tail": "V19-B", "v19c_forward_rotors": "V19-C", "v19r_boom_rotors": "V19-R",
         "v19w_four_in_wings": "V19-W", "v19s_stoop_crest": "V19-S"}
REC = "v19s_stoop_crest"
PACKS = ("v19c_forward_rotors", "v19r_boom_rotors", "v19w_four_in_wings", "v19s_stoop_crest")
BUY_FIXED = [  # purchases the recommended build adds beyond the V18 BOM (reference candidates, as in bom/bom.csv)
    ("Crest elevator servo, slim 5 g wing servo, about 20 x 18 x 9 mm (reference class: Hitec HS-40)", 1, "15-25", "https://www.amazon.com/s?k=hitec+hs-40+servo"),
    ("Elevator torque rod, horn and clevis set (1.2 mm wire)", 1, "6-10", "https://www.amazon.com/s?k=rc+pushrod+clevis+control+horn+set"),
    ("Clear PETG sheet 0.75 mm, A4 or larger (vacuum-formed canopy; two spares)", 3, "8-15", "https://www.amazon.com/s?k=petg+sheet+0.75mm+clear"),
    ("M3 U-straps / saddle clamps for 10 mm tube, plus M3 hardware", 8, "8-14", "https://www.amazon.com/s?k=m3+u+bolt+10mm"),
    ("M2 x 6 screws and washers (camera tilt)", 4, "2-5", "https://www.amazon.com/s?k=m2+x+6+screws"),
]
TUBES = {"10x10": ("Carbon square tube 10 x 10 x 1 mm", "https://www.amazon.com/s?k=carbon+fiber+square+tube+10mm"),
         "8x8": ("Carbon square tube 8 x 8 x 1 mm", "https://www.amazon.com/s?k=carbon+fiber+square+tube+8mm"),
         "6x4": ("Carbon round tube 6 x 4 mm", "https://www.amazon.com/s?k=carbon+fiber+tube+6mm+4mm")}
EDF = {  # vendor figures, checked 2026-10-04
    "single": ("Freewing E7206 64 mm 12-blade, 4S (V18 choice)", 1200, 44, 142, "https://www.freewingmodel.com/747.html"),
    "twin": ("XFly Galaxy X5 50 mm 12-blade, 4S (each)", 900, 40, 75,
             "https://www.turbines-rc.com/en/xfly-galaxy/2967-edf-ducted-fan-xfly-galaxy-x5-xfly-model-50mm-12-blades-4s-motor-4600kv.html"),
}


def f1(v):
    return f"{v:.1f}"


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(head))) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main() -> int:
    allv = json.loads((ROOT / "analysis" / "v19_variants.json").read_text())
    web = json.loads((ROOT / "site" / "data" / "variants.json").read_text())
    v18 = web["v18"]
    search = json.loads((ROOT / "analysis" / "v19_search.json").read_text())
    cfg = {s: json.loads((ROOT / "config" / "v19" / f"{s}.json").read_text()) for s in ORDER}
    L = []
    w = L.append
    w("# V19 variants: long nose, falcon tail, forward rotors\n")
    w("> Screening results from the point-mass + vortex-lattice models, with the masses of the parts as the V19 geometry "
      "models them. Nothing has been built yet. Not a flight clearance: bench and fit gates in [TEST_GATES.md](TEST_GATES.md) still decide.\n")
    w("Your three directions, each built from your V18 assembly (`tools/v19/geometry.py`), collision-checked against V18 "
      "and evaluated with the same gates as V18: heaviest motor in hover no more than 30 % of the weight, static margin "
      "5-25 % of the mean chord, pitch trim within 10 deg at 16 m/s, prop and flap clearances.\n")
    w("![V19-S, three-quarter view](../analysis/view_v19s_stoop_crest.png)\n")
    w("## The answer\n")
    rows = []
    for name, e, extra in [("V18 as designed", v18, None)] + [(SHORT[s], allv[s]["evaluation"], allv[s]) for s in ORDER]:
        trim = " / ".join(f1(t["pitch_surfaces_deg"]) for t in e["trim_16ms"].values())
        coll = "-" if extra is None else (str(len(extra["checks"]["collisions_new_vs_V18"])) if extra["checks"]["collisions_new_vs_V18"] else "0")
        length = 810 if extra is None else round(extra["extent"]["length_mm"])
        rows.append([name, f"{e['all_up_g']:.0f}", f"{e['cg_mm'][0]:.0f}", f"{e['rotor_centroid_x_mm']:.0f}",
                     f"{f1(e['sm_closed_pct'])} / {f1(e['sm_open_pct'])}", f1(e["worst_motor_pct"]), trim, length, coll,
                     "**PASS**" if e["passes"] and (extra is None or not extra["checks"]["collisions_new_vs_V18"]) else "STOP"])
    w(table(rows, ["", "Mass g", "CG x", "Rotors x", "Static margin % (wells closed / open)", "Heaviest motor %",
                   "Trim 16 m/s deg", "Length mm", "New collisions", "Gates"]))
    w("")
    r = allv[REC]
    re_ = r["evaluation"]
    rc = cfg[REC]
    rw = allv["v19w_four_in_wings"]["evaluation"]
    wc = cfg["v19w_four_in_wings"]
    w(f"**Build V19-S.** It keeps everything you asked for in V19-W - all four lift motors in your V18 wing wells, the pilot's-eye "
      "FPV camera under a clear canopy, the single V18 EDF in the jet bay - and drops the big boom tail. Two changes do the tail's "
      f"job instead. The outer falcon panels sweep {rc['outer_shift_mm']:.0f} mm back at the wrist (a 'stoop', like a falcon "
      f"tucking its wings in a dive), and a {rc['tail']['area_m2']:.2f} m2 falcon crest sits on the tips of your own V18 fins, "
      f"with no booms and no new fins. Without the tail weight to balance, the battery stays in the V18 tray and the nose bay goes. "
      f"With the parts as modelled it weighs {re_['all_up_g']:.0f} g ({rw['all_up_g'] - re_['all_up_g']:.0f} g less than V19-W), "
      f"it is {allv['v19w_four_in_wings']['extent']['length_mm'] - r['extent']['length_mm']:.0f} mm shorter, its CG sits "
      f"{abs(re_['cg_mm'][0] - re_['rotor_centroid_x_mm']):.0f} mm from the rotor centroid, the heaviest motor carries "
      f"{f1(re_['worst_motor_pct'])} % in hover, and the static margin is {f1(re_['sm_closed_pct'])} % to {f1(re_['sm_open_pct'])} %. "
      f"V19-W ({wc['tail']['area_m2']:.2f} m2 boom tail), V19-R and V19-C also pass and stay as alternatives.\n")
    w(f"![V19-S pilot's-eye view from the FPV camera](../analysis/view_v19s_cockpit.png)\n")
    w("### Why each direction alone is not enough\n")
    a, b = allv["v19a_long_nose"]["evaluation"], allv["v19b_falcon_tail"]["evaluation"]
    w(f"- **Long nose alone (V19-A).** Moving the wing aft moves the neutral point aft almost one for one, but the CG only by the "
      f"wing group's share of the mass. That helps, and the nose-bay battery helps more, yet at 200 mm the static margin is still "
      f"{f1(a['sm_closed_pct'])} % and trim needs {max(abs(t['pitch_surfaces_deg']) for t in a['trim_16ms'].values()):.0f} deg of "
      "surface. Search rows: 150-200 mm, 0.6-0.8 g/cm3; none passes.")
    w(f"- **Falcon tail alone (V19-B).** A horizontal tail moves the neutral point aft without moving much mass, but on V18's "
      f"short body it has a short arm. Even 0.15 m2 at a 120 mm wing shift leaves {f1(b['sm_closed_pct'])} %, and with the rotors "
      "balanced in the wing the rear crossrail lands in the D1 intake.")
    w("- **Forward rotors (V19-C, V19-R).** Taking the front pair out of the wing lets the rotors balance the CG without the wing "
      f"having to move under them; V19-C passes at {cfg['v19c_forward_rotors']['wing_shift_mm']:.0f} mm, V19-R at "
      f"{cfg['v19r_boom_rotors']['wing_shift_mm']:.0f} mm with a {cfg['v19r_boom_rotors']['tail']['area_m2']:.2f} m2 tail.")
    w(f"- **Four rotors in the wings (V19-W).** With the rotors fixed in your wells, the CG has to sit on their centroid, at wing "
      "station x 330. Your wing's own neutral point sits ahead of that station (x 285-332 on V18), so on its own the wing is "
      "unstable there; the tail is what moves the neutral point behind the CG. The tail's weight pulls the CG aft, so the wing "
      f"moves {cfg['v19w_four_in_wings']['wing_shift_mm']:.0f} mm aft until the rotors sit under the CG again. The rear crossrail cannot follow the wells into "
      "the D1 intake, so it stops at x 566.5 and two short carbon booms under the wing carry the rear motors.\n")
    rows_w = [x for x in search["rows"] if x["family"] == "W"]
    if rows_w:
        tab = [[x["config"]["wing_shift_mm"], f"{x['config']['tail']['area_m2']:.2f}", f1(x["sm_closed_pct"]), f1(x["worst_motor_pct"]),
                "PASS" if x["passes"] else "-"] for x in rows_w]
        w("V19-W search (wing shift x tail area; tail leading edge 110 mm behind the wing root):\n")
        w(table(tab, ["Wing aft mm", "Tail m2", "Static margin %", "Heaviest motor %", "Gates"]))
        w("\nA smaller tail needs the wing further aft for hover balance but then loses margin; a bigger tail pulls the CG behind "
          "the rotors. The pick is the cheapest row with at least 7.5 % margin on the coarse lattice (it reads about 1 % high on "
          "tails) and no motor above 28 %.\n")
    sc = cfg[REC]
    fixed = [x for x in search["rows"] if x["family"] == "S" and not x["config"]["tail"]["elevator_frac"]]
    fx = [min(abs(t["pitch_surfaces_deg"]) for t in x["trim_16ms"].values()) for x in fixed] or [0]
    fy = [max(abs(t["pitch_surfaces_deg"]) for t in x["trim_16ms"].values()) for x in fixed] or [0]
    w(f"- **No big tail (V19-S).** A tailless wing balanced on its rotors has about 0-1 % margin (the wing's neutral point sits "
      "right at the rotor station), so something has to add lift behind the CG. V19-S splits that job: the stoop moves the outer "
      f"panels' lift {sc['outer_shift_mm']:.0f} mm aft (about 1.6 % margin per 60 mm), and the crest adds a little tail lift high on "
      f"the fins, right over the EDF instead of on booms behind it. A fixed crest (no elevator) needed {min(fy):.0f}-{max(fy):.0f} deg "
      f"of elevon at 16 m/s with the wells open, outside the 10 deg gate, so the crest is set {abs(sc['tail']['incidence_deg']):.0f} deg leading edge down and has a "
      f"{100 * sc['tail']['elevator_frac']:.0f} % elevator on one slim servo.\n")
    rows_s = [x for x in search["rows"] if x["family"] == "S"]
    if rows_s:
        tab = [[x["config"]["wing_shift_mm"], x["config"]["outer_shift_mm"], f"{x['config']['tail']['area_m2']:.2f}",
                f"{x['config']['tail']['incidence_deg']:.0f}", f"{100 * x['config']['tail']['elevator_frac']:.0f}",
                f1(x["sm_closed_pct"]), f1(x["worst_motor_pct"]),
                " / ".join(f1(t["pitch_surfaces_deg"]) for t in x["trim_16ms"].values()), "PASS" if x["passes"] else "-"]
               for x in rows_s]
        w("V19-S search (coarse lattice; wing shift x stoop x crest area; the last rows are fixed crests, kept for the record):\n")
        w(table(tab, ["Wing aft mm", "Stoop mm", "Crest m2", "Incidence deg", "Elevator %", "Static margin %", "Heaviest motor %",
                      "Trim 16 m/s closed / open", "Gates"]))
        w("\nThe pick is the cheapest passing row with at least 7.5 % margin on the coarse lattice (it reads about 1 % high), no "
          "motor above 28 % and at least 1.5 deg of the trim gate in hand. More stoop or more crest adds margin; more wing shift "
          "loads the front motors.\n")
    w("### Cruise engine: one EDF or two?\n")
    sg, tw = EDF["single"], EDF["twin"]
    w(table([[f"One {sg[0]}", f"{sg[1]} g", f"{sg[2]} A", f"{sg[3]} g + 1 ESC", f"[spec]({sg[4]})"],
             [f"Two {tw[0]}", f"{2 * tw[1]} g", f"{2 * tw[2]} A", f"{2 * tw[3]} g + 2 ESCs", f"[spec]({tw[4]})"]],
            ["Option", "Static thrust", "Current", "Mass", ""]))
    w(f"\n**One EDF: keep the V18 E7206 in the jet bay.** It gives {sg[1] / re_['all_up_g']:.2f} thrust-to-weight for cruise "
      "(the lift rotors carry hover and transition), and it already fits the V18 saddles, the D1 intake and the D2 nozzle. "
      f"It also draws about half the current of a twin, which matters on one 4S pack that is feeding four lift motors during "
      "transition. Twin 50 mm fans would add a second ESC and a split intake and nozzle. They would also make a sudden yaw "
      "moment if one fails, and give no lift redundancy, because hover is on the rotors. Revisit only if the Stage 2 bench shows "
      "the E7206 short of cruise thrust.\n")
    for s in ORDER:
        v = allv[s]
        e = v["evaluation"]
        ck = v["checks"]
        w(f"## {cfg[s]['label']}\n")
        w(f"![{cfg[s]['label']}](../analysis/view_{s}.png)\n")
        w(f"_{cfg[s]['summary']}._ " + ("**Passes every model gate.**" if e["passes"] and not ck["collisions_new_vs_V18"] else
                                        f"**{web['variants'][s]['verdict']}**") + "\n")
        w("What changes:\n")
        for c in v["changes"]:
            w(f"- {c}")
        w("")
        t16, t20 = e["trim_16ms"]["closed"], e["trim_20ms"]["closed"]
        w(table([[f"{e['all_up_g']:.0f} g", f"x {e['cg_mm'][0]:.1f}", f"x {e['rotor_front_x_mm']:.1f} / {e['rotor_rear_x_mm']:.1f}",
                  f"x {e['np_closed_x_mm']:.1f} / {e['np_open_x_mm']:.1f}", " / ".join(f"{v_:.0f}" for v_ in e["motor_hover_g"].values()),
                  f"{t16['alpha_deg']:.1f} / {t16['pitch_surfaces_deg']:.1f}", f"{t20['alpha_deg']:.1f} / {t20['pitch_surfaces_deg']:.1f}",
                  f"{e['stall_speed_ms']['CLmax_0.9']:.1f}"]],
                ["Mass", "CG", "Rotors front / rear", "Neutral point closed / open", "Hover g M1/M2/M3/M4",
                 "16 m/s alpha / surfaces deg", "20 m/s alpha / surfaces deg", "Stall m/s (CLmax 0.9)"]))
        w("")
        rows = []
        for p in sorted(v["parts"], key=lambda p: p["name"]):
            if p["mass_g"] <= 0 and p["class"] == "keepout":
                continue
            fit = "-" if not p.get("P1S") else ("fits" if p["P1S"]["fits"] else "**split**")
            rows.append([f"`{p['name']}`", p["material"] or "-", f1(p["mass_g"]), p["mass_basis"], fit])
        w(f"New parts ({sum(p['mass_g'] for p in v['parts']):.0f} g), STL in `cad/v19/{s}/stl/`:\n")
        w(table(rows, ["Part", "Material", "g", "Mass basis", "P1S"]))
        w("")
        if v["modified"]:
            w("Your V18 parts that change" + (" (modified STL beside the new parts, `*__V19.stl`):\n" if s in PACKS
              else " (concept variant: the cut panels are shown in the web viewer; files are exported only for V19-C, R and W):\n"))
            for m in v["modified"]:
                w(f"- `{m['name']}`: {'; '.join(m['why'])}")
            w("")
        w(f"Checks: {len(ck['collisions_new_vs_V18'])} new collisions against V18"
          + (": " + "; ".join(f"`{c['a']}` x `{c['b']}`" for c in ck["collisions_new_vs_V18"]) if ck["collisions_new_vs_V18"] else "")
          + f"; {len(ck['intended_contacts'])} intended contacts (clamps, sockets, bonded joints, listed in `cad/v19/{s}/checks.json`).")
        if ck.get("jet_vs_tail"):
            j = ck["jet_vs_tail"]
            w(f" EDF jet: estimated jet edge {j['jet_top_at_stab_le_mm']:.0f} mm above the axis at the stabiliser, underside at "
              f"z {j['stab_underside_z_mm']:.0f}; the fins' inner faces (y {j['fin_inner_face_y_mm']:.0f}) are "
              + ("inside" if j['fin_inner_face_y_mm'] < j['jet_radius_at_fin_le_mm'] else "outside")
              + f" the estimated jet edge (radius {j['jet_radius_at_fin_le_mm']:.0f}) at the fin leading edge. {j['note']}")
        w("")

    # recommended build pack
    import math as _m
    import re as _re
    w(f"## {SHORT[REC]} build changes\n")
    w("### Buy (in addition to the V18 BOM)\n")
    need = {}
    for p in r["parts"]:
        m = _re.search(r"_(\d+x\d+)x(\d+)$", p["name"])
        if p["class"] == "carbon" and m:
            need.setdefault(m.group(1), []).append(int(m.group(2)))
    buy = []
    for sec, ls in need.items():
        stock = 1000
        bars = _m.ceil(sum(ls) * 1.05 / stock) if max(ls) <= stock else len(ls)
        d, url = TUBES.get(sec, (f"Carbon tube {sec}", ""))
        buy.append((f"{d}, {stock} mm (cut {len(ls)} x {max(ls)} mm)", bars, "8-18 each", url))
    w(table([[d, q, u, f"[link]({url})" if url else ""] for d, q, u, url in buy + BUY_FIXED], ["Item (reference candidate)", "Qty", "USD", ""]))
    w("\nNot added to `bom/bom.csv` on purpose: that file is the V18 budget. Fold these rows in when " + SHORT[REC] + " becomes the build.\n")
    w("### Carbon and G10 cut list\n")
    rows = []
    for p in r["parts"]:
        if p["class"] not in ("carbon", "g10"):
            continue
        m = _re.search(r"_(\d+x\d+)x(\d+)$", p["name"])
        size = f"{m.group(1)} section, {m.group(2)} mm long" if m else " x ".join(f"{x:.0f}" for x in p["bbox_mm"]) + " mm (outline)"
        rows.append([f"`{p['name']}`", p["material"], size])
    w(table(rows, ["Part", "Material", "Size"]))
    if (ROOT / "cad" / "v19" / REC / "dxf" / "NEW_G10_nose_battery_floor.dxf").exists():
        w(f"\nThe nose-bay floor profile is `cad/v19/{REC}/dxf/NEW_G10_nose_battery_floor.dxf`.\n")
    else:
        w("")
    w("### Print\n")
    rows = [[f"`{p['name']}`", p["material"], ("fits" if p["P1S"]["fits"] else "split") if p.get("P1S") else "-", p["note"]]
            for p in r["parts"] if p["class"] == "printed"]
    w(table(rows, ["Part", "Material", "P1S", "Notes"]))
    w(f"\nAll printed parts in one file: `cad/v19/{REC}/{REC}_print_set.3mf` (unsliced; outer mould lines - print the LW-PLA "
      "parts hollow with your V18 wing settings). The clear canopy is vacuum-formed, not printed: print the "
      "`NEW_canopy_clear_PETG` shape solid as the forming buck.\n")
    w("### Gates to add before the first hover\n")
    w("- Rear booms: with each rear motor at 50 % throttle on the stand, no visible riser or boom vibration; tap test each clamp.")
    w("- Wrist spars: with the aircraft held at the wing roots, hang 1.5 kg (about 2.5 g of manoeuvre load on one outer panel) "
      "from each outer panel's mid-span for one minute; no creak, no visible joint movement, no skin cracking at the wrist caps.")
    w("- EDF jet on the crest: tuft the crest underside and the fin tops, run the EDF to 100 % on the bench; no tuft should stream aft.")
    w("- Crest elevator: +/-20 deg throw with no contact against the fin tops; the slim servo centres within 1 deg.")
    w("- Cockpit camera: the FPV image shows the horizon with the nose in the lower edge at 0-10 deg uptilt; no canopy glare at "
      "the sun angles you fly in (matt black seat and frame).")
    w(f"- Weigh and balance the complete aircraft: CG within 5 mm of x {re_['cg_mm'][0]:.0f} before any hover.")
    w(f"- Trim: at 16 m/s the model needs {re_['trim_16ms']['closed']['alpha_deg']:.0f} deg of angle of attack; plan transitions "
      f"and cruise at 18-20 m/s ({re_['trim_20ms']['closed']['alpha_deg']:.0f} deg at 20 m/s) and confirm the stall speed "
      f"(model {re_['stall_speed_ms']['CLmax_0.9']:.1f} m/s at CLmax 0.9) in the glide tests.\n")
    w("## How the numbers were made\n")
    w("- `tools/v19/search.py` ran " + str(len(search["rows"])) + " configurations across six families. In families A-C and R the "
      "rotors are placed so their centroid sits on that configuration's CG within the geometric limits (in W and S they stay in your "
      "V18 wells and the wing shift, stoop and tail decide the balance), the masses come from the "
      "V19 construction (`geometry.py` mass-only mode), and the neutral points come from the vortex lattice with the wells closed "
      "and open. The cheapest passing configuration in each family becomes `config/v19/<variant>.json`.")
    w("- `tools/v19/geometry.py` builds each variant from the V18 meshes, cuts the V18 parts that must change, generates the new "
      "parts, runs a full-assembly collision check against the V18 baseline, and re-evaluates with the mass of every part where "
      "it sits (`cad/v19/<variant>/mass_inputs.json`).")
    w("- Assumptions to replace with measurements: LW-PLA at 0.80 g/cm3, new skins at the V18 skin areal density "
      f"({1407} g/m2 for both skins), tail surfaces at the V18 falcon-panel density (1100 g/m2), PETG parts solid or at the stated "
      "wall, EDF jet spread 0.1 mm per mm from a 30 mm exit radius. Not counted: the 43 g of distributed fasteners and "
      "consumables stay at their V18 position, and longer motor leads, the elevator servo and camera leads and the boom U-straps "
      "(about 30-40 g, mostly aft of the CG, roughly -0.4 % static margin) are not modelled yet. Props are excluded from "
      "the collision check; the prop disc to leading-edge clearance is checked separately.")
    w("- Regenerate everything: `make v19` (search + geometry + this document + web data).\n")
    (ROOT / "docs" / "V19_VARIANTS.md").write_text("\n".join(L) + "\n")
    print("wrote docs/V19_VARIANTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
