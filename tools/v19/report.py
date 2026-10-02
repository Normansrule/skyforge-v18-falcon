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

ORDER = ["v19a_long_nose", "v19b_falcon_tail", "v19c_forward_rotors", "v19r_recommended"]
SHORT = {"v19a_long_nose": "V19-A", "v19b_falcon_tail": "V19-B", "v19c_forward_rotors": "V19-C", "v19r_recommended": "V19-R"}
BUY = {  # purchases the V19-R build adds (reference candidates, same convention as bom/bom.csv)
    "servo": ("Elevator servo, 9 g digital, metal gear (reference: EMAX ES08MD II)", 1, "15-25", "https://www.amazon.com/s?k=emax+es08md+ii"),
    "linkage": ("Elevator pushrod, clevis and horn set (1.2 mm wire)", 1, "6-10", "https://www.amazon.com/s?k=rc+pushrod+clevis+control+horn+set"),
    "cf10": ("Carbon square tube 10 x 10 x 1 mm, 500 mm (rotor booms)", 2, "16-30", "https://www.amazon.com/s?k=carbon+fiber+square+tube+10mm"),
    "cf8": ("Carbon square tube 8 x 8 x 1 mm, 600 mm (tail booms, replace the 174 mm outriggers)", 2, "12-24", "https://www.amazon.com/s?k=carbon+fiber+square+tube+8mm"),
    "cf6": ("Carbon round tube 6 x 4 mm, 500 mm (stabiliser spars)", 1, "6-10", "https://www.amazon.com/s?k=carbon+fiber+tube+6mm+4mm"),
    "ustrap": ("M3 U-straps / saddle clamps for 10 mm tube, plus M3 hardware", 8, "8-14", "https://www.amazon.com/s?k=m3+u+bolt+10mm"),
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
    w("![V19-R, three-quarter view](../analysis/view_v19r_recommended.png)\n")
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
    r = allv["v19r_recommended"]
    re_ = r["evaluation"]
    w(f"**Build V19-R.** It is your long-nose falcon with the other two directions folded in: the wing group "
      f"{cfg['v19r_recommended']['wing_shift_mm']:.0f} mm aft of the nose, the front rotor pair on booms ahead of the leading "
      f"edge, and a {cfg['v19r_recommended']['tail']['area_m2']:.2f} m2 falcon tail. With the parts as modelled it weighs "
      f"{re_['all_up_g']:.0f} g, its CG sits {abs(re_['cg_mm'][0] - re_['rotor_centroid_x_mm']):.0f} mm from the rotor centroid, the "
      f"heaviest motor carries {f1(re_['worst_motor_pct'])} % in hover, and the static margin is {f1(re_['sm_closed_pct'])} % to "
      f"{f1(re_['sm_open_pct'])} %. The rear rotors stay in your V18 wells. V19-C (no tail, wing {cfg['v19c_forward_rotors']['wing_shift_mm']:.0f} mm aft) "
      "also passes and is the fallback if the tail disappoints on the bench.\n")
    w("### Why each direction alone is not enough\n")
    a, b = allv["v19a_long_nose"]["evaluation"], allv["v19b_falcon_tail"]["evaluation"]
    w(f"- **Long nose alone (V19-A).** Moving the wing aft moves the neutral point aft almost one for one, but the CG only by the "
      f"wing group's share of the mass. That helps, and the nose-bay battery helps more, yet at 200 mm the static margin is still "
      f"{f1(a['sm_closed_pct'])} % and trim needs {max(abs(t['pitch_surfaces_deg']) for t in a['trim_16ms'].values()):.0f} deg of "
      "surface: the rotors have to follow the CG forward inside the wing, which needs a leading-edge glove, and the front wells "
      "then eat the lift ahead of the CG. Search rows: 150-200 mm, 0.6-0.8 g/cm3; none passes.")
    w(f"- **Falcon tail alone (V19-B).** A horizontal tail moves the neutral point aft without moving much mass, but on V18's "
      f"short body it has a short arm. Even 0.15 m2 at a 120 mm wing shift leaves {f1(b['sm_closed_pct'])} %, and with the rotors "
      "balanced in the wing the rear crossrail lands in the D1 intake.")
    w("- **Forward rotors (V19-C).** Taking the front pair out of the wing lets the rotors balance the CG without the wing having "
      "to move under them, and closing the front wells gives back lift ahead of the CG. With the long nose it passes on its own at "
      f"{cfg['v19c_forward_rotors']['wing_shift_mm']:.0f} mm.")
    w(f"- **Together (V19-R).** With a tail a third the size of V19-B's, the wing needs to move "
      f"{cfg['v19r_recommended']['wing_shift_mm']:.0f} mm instead of {cfg['v19c_forward_rotors']['wing_shift_mm']:.0f} mm and the "
      f"rear rotors stay in your V18 wells; static margin {f1(re_['sm_closed_pct'])} %.\n")
    w("Why 250 mm and not 150-200 mm: with the modelled booms, pods, risers, tail booms and fins (about "
      f"{sum(p['mass_g'] for p in r['parts']):.0f} g of new parts, most of it aft of the CG) the 200 mm combinations miss either the "
      "5 % margin or the 30 % motor limit. 225 mm with the 0.05 m2 tail passes by a hair (5.2 %); 250 mm gives margin to spare. "
      "The search table is in `analysis/v19_search.json`.\n")

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
            w("Your V18 parts that change" + (" (modified STL beside the new parts, `*__V19.stl`):\n" if s in ("v19c_forward_rotors", "v19r_recommended")
              else " (concept variant: the cut panels are shown in the web viewer; files are exported only for V19-C and V19-R):\n"))
            for m in v["modified"]:
                w(f"- `{m['name']}`: {'; '.join(m['why'])}")
            w("")
        w(f"Checks: {len(ck['collisions_new_vs_V18'])} new collisions against V18"
          + (": " + "; ".join(f"`{c['a']}` x `{c['b']}`" for c in ck["collisions_new_vs_V18"]) if ck["collisions_new_vs_V18"] else "")
          + f"; {len(ck['intended_contacts'])} intended contacts (clamps, sockets, bonded joints, listed in `cad/v19/{s}/checks.json`).")
        if ck.get("jet_vs_tail"):
            j = ck["jet_vs_tail"]
            w(f" EDF jet: estimated jet edge {j['jet_top_at_stab_le_mm']:.0f} mm above the axis at the stabiliser, underside at "
              f"z {j['stab_underside_z_mm']:.0f}; {j['note']}")
        w("")

    # V19-R build pack
    w("## V19-R build changes\n")
    w("### Buy (in addition to the V18 BOM)\n")
    w(table([[d, q, u, f"[link]({url})"] for d, q, u, url in BUY.values()], ["Item (reference candidate)", "Qty", "USD", ""]))
    w("\nNot added to `bom/bom.csv` on purpose: that file is the V18 budget. Fold these rows in when V19-R becomes the build.\n")
    w("### Carbon and G10 cut list\n")
    import re as _re
    rows = []
    for p in r["parts"]:
        if p["class"] not in ("carbon", "g10"):
            continue
        m = _re.search(r"_(\d+x\d+)x(\d+)$", p["name"])
        size = f"{m.group(1)} section, {m.group(2)} mm long" if m else " x ".join(f"{x:.0f}" for x in p["bbox_mm"]) + " mm (outline)"
        rows.append([f"`{p['name']}`", p["material"], size])
    w(table(rows, ["Part", "Material", "Size"]))
    w("\nThe nose-bay floor profile is `cad/v19/v19r_recommended/dxf/NEW_G10_nose_battery_floor.dxf`.\n")
    w("### Print\n")
    rows = [[f"`{p['name']}`", p["material"], "fits" if p["P1S"]["fits"] else "split", p["note"]] for p in r["parts"] if p["class"] == "printed"]
    w(table(rows, ["Part", "Material", "P1S", "Notes"]))
    w("\nAll printed parts in one file: `cad/v19/v19r_recommended/v19r_recommended_print_set.3mf` (unsliced; outer mould lines - "
      "print the LW-PLA parts hollow with your V18 wing settings).\n")
    w("### Gates to add before the first hover\n")
    w("- Boom stiffness: with the motor at 50 % throttle on the stand, no visible boom-tip vibration; tap test each boom clamp.")
    w("- Prop to leading edge: measure at least 15 mm from the front prop disc to the wing leading edge (model: "
      f"{re_['boom_prop_to_le_mm']:.0f} mm, at the limit by design - keep it there).")
    w("- EDF jet on the tail: tuft the stabiliser underside and fins, run the EDF to 100 % on the bench; no tuft should stream aft.")
    w("- Elevator: +/-20 deg throw with no contact against the fins.")
    w("- Camera cradle: the 7 mm trim removes most of the cradle's lower body; check it still bolts to C1 before printing it.")
    w(f"- Weigh and balance the complete aircraft: CG within 5 mm of x {re_['cg_mm'][0]:.0f} before any hover.")
    w(f"- Trim: at 16 m/s the model needs {re_['trim_16ms']['closed']['alpha_deg']:.0f} deg of angle of attack; plan transitions "
      f"and cruise at 18-20 m/s ({re_['trim_20ms']['closed']['alpha_deg']:.0f} deg at 20 m/s) and confirm the stall speed "
      f"(model {re_['stall_speed_ms']['CLmax_0.9']:.1f} m/s at CLmax 0.9) in the glide tests.\n")
    w("## How the numbers were made\n")
    w("- `tools/v19/search.py` ran " + str(len(search["rows"])) + " configurations across the four families. In each one the "
      "rotors are placed so their centroid sits on that configuration's CG within the geometric limits, the masses come from the "
      "V19 construction (`geometry.py` mass-only mode), and the neutral points come from the vortex lattice with the wells closed "
      "and open. The cheapest passing configuration in each family becomes `config/v19/<variant>.json`.")
    w("- `tools/v19/geometry.py` builds each variant from the V18 meshes, cuts the V18 parts that must change, generates the new "
      "parts, runs a full-assembly collision check against the V18 baseline, and re-evaluates with the mass of every part where "
      "it sits (`cad/v19/<variant>/mass_inputs.json`).")
    w("- Assumptions to replace with measurements: LW-PLA at 0.80 g/cm3, new skins at the V18 skin areal density "
      f"({1407} g/m2 for both skins), tail surfaces at the V18 falcon-panel density (1100 g/m2), PETG parts solid or at the stated "
      "wall, EDF jet spread 0.1 mm per mm from a 30 mm exit radius. Not counted: the 43 g of distributed fasteners and "
      "consumables stay at their V18 position, and longer motor leads, the elevator servo lead and the boom U-straps "
      "(about 30-40 g, mostly aft of the CG, roughly -0.4 % static margin) are not modelled yet. Props are excluded from "
      "the collision check; the prop disc to leading-edge clearance is checked separately.")
    w("- Regenerate everything: `make v19` (search + geometry + this document + web data).\n")
    (ROOT / "docs" / "V19_VARIANTS.md").write_text("\n".join(L) + "\n")
    print("wrote docs/V19_VARIANTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
