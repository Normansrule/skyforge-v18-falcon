#!/usr/bin/env python3
"""V18 balance study: can the CG sit on the rotor centroid AND ahead of the neutral point?

    python3 tools/balance_study.py        # analysis/balance_study.json + analysis/balance_study.png

Design knobs (all keep the falcon / blended-wing silhouette; none is applied to the V18 CAD here):
  dw   wing group shift aft relative to the body (mm): wing panels, flaps, elevons, fins, servo
       cassettes, rotors, crossrails move together; nose, body, trays, EDF stay.
  dr   rotor shift relative to the wing (mm, negative = forward): wells, motors, props, G10 motor
       plates and the two crossrails move; limited by the wing leading edge and the flaps.
  batt battery location: V18 (x362) | tray-front (battery and the lift-ESC/BEC swap ends of TRAY_A,
       x284) | nose bay (x150, needs a new nose compartment)
  tail EDF saddles + D1/D2 ducts in LW-PLA instead of PETG

Gates (same as docs/TEST_GATES.md):
  hover:  worst motor <= 30 % of weight (25 % is perfect balance)
  flight: static margin >= 5 % MAC with the wells CLOSED (forward NP bound) and <= 20 % with the
          wells OPEN (aft NP bound); |elevon trim| <= 10 deg at 15 m/s for both bounds
Linear VLM + point-mass model: a screening tool to pick the next CAD revision, not a flight clearance.
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import aero_vlm as av  # noqa: E402
import mass_cg as mc  # noqa: E402
import v18geom as g  # noqa: E402

ROOT = g.ROOT
WELL_R = 72.5
MOTOR_X = (240.0, 420.0)
MOTOR_Y = 220.0

WING_POLY = re.compile(r"^(W[RL]|FLAP_|ELEVON_|FIN_|SP1_|SC1_)")
ROTOR_HW = re.compile(r"(PURCHASE_M\d_2207|NO_PRINT_PURCHASED_PROP|motor_plate|motor_backing|CF_crossrail)")
BATT_SRC = "KEEP_OUT_BATTERY_MAX_140x50x38"
SWAP_SRC = ("KEEP_OUT_LIFT_ESC_54x46x14", "KEEP_OUT_SERVO_BEC_48x38x16")
TAIL_POLY = re.compile(r"^(EDF_saddle|D1_|D2_)")
AVIONICS_SRC = ("KEEP_OUT_FC_54x34x24", "KEEP_OUT_VTX_42x26x14", "KEEP_OUT_EDF_ESC_73x30x12_plus_margin", "xyz:520,25,12")
BATTERY = {"V18 x362": (0.0, 0.0), "tray-front x284": (-78.0, 146.0), "nose bay x150": (-212.0, 0.0)}


def rotor_limits():
    """How far the rotors can move inside the existing wing (relative to the wing)."""
    st = json.loads((ROOT / "analysis" / "aero.json").read_text())["stations"]
    near = [s for s in st if abs(s["y"] - MOTOR_Y) <= WELL_R]
    le = max(s["le"] for s in near)
    flap_le = min(p.vertices[:, 0].min() for p in g.load() if p.name.startswith("FLAP_"))
    fwd = (le + 35.0) - (MOTOR_X[0] - WELL_R)   # keep >= 35 mm of skin ahead of the front well
    aft = (flap_le - 20.0) - (MOTOR_X[1] + WELL_R)  # keep >= 20 mm ahead of the flap hinge
    return float(fwd), float(aft), float(le), float(flap_le)


def mass_state(items, poly, rho, lw, dw, dr, batt, tail, avfwd=False):
    tot, mom = 0.0, np.zeros(3)
    dxb, dxs = BATTERY[batt]
    for label, grp, m, xyz, basis, src in items:
        x = np.array(xyz, dtype=float)
        if ROTOR_HW.search(src) or ROTOR_HW.search(label):
            x[0] += dw + dr
        elif src.startswith(("SP1_", "FLAP_", "ELEVON_")):
            x[0] += dw
        elif src == BATT_SRC:
            x[0] += dxb
        elif src in SWAP_SRC:
            x[0] += dxs
        elif avfwd and src in AVIONICS_SRC:
            x[0] -= 140.0  # FC, VTX, EDF ESC, alarm move into the vacated battery bay
        tot += m
        mom += m * x
    for name, mat, v, c in poly:
        d = lw if mat == "LW-PLA" else rho[mat]
        if tail and TAIL_POLY.match(g.template_name(name)):
            d = lw
        x = np.array(c, dtype=float)
        if WING_POLY.match(name):
            x[0] += dw
        tot += v * d
        mom += v * d * x
    return tot, mom / tot


def main() -> int:
    items, poly, rho, lw_cases = mc.compute(want_items=True)
    lw = lw_cases.get("measured") or lw_cases["planning"]
    fwd, aft, le, flap_le = rotor_limits()
    motors = {"M1": (MOTOR_X[0], MOTOR_Y), "M2": (MOTOR_X[1], -MOTOR_Y), "M3": (MOTOR_X[0], -MOTOR_Y), "M4": (MOTOR_X[1], MOTOR_Y)}

    DW = [0, 60, 120, 150, 180, 210]
    # forward rotor moves beyond the existing leading edge need a leading-edge extension (styling change)
    DR = [d for d in (-40.0, -20.0, 0.0, 15.0, 30.0, 60.0) if d <= aft]
    closed, opened = {}, {}
    for dw in DW:
        P, st = av.build_v18_lattice(fill_wells=True, wing_shift_mm=dw)
        closed[dw] = av.derivatives(P, st)
        for dr in DR:
            wells = [(x + dw + dr, MOTOR_Y, WELL_R) for x in MOTOR_X]
            P, st = av.build_v18_lattice(wells=wells, wing_shift_mm=dw)
            opened[(dw, dr)] = av.derivatives(P, st)
        print(f"dw={dw}: NP closed x{closed[dw]['x_np_mm']:.0f}; open " +
              ", ".join(f"dr{dr:+.0f}:x{opened[(dw, dr)]['x_np_mm']:.0f}" for dr in DR), flush=True)

    rows = []
    for dw, dr, batt, tail, avfwd, lwc in itertools.product(DW, DR, BATTERY, (False, True), (False, True), ("planning", "best")):
        if avfwd and batt != "nose bay x150":
            continue  # the avionics only move forward once the battery has left its bay
        lwd = lw if lwc == "planning" else lw_cases["best"]
        M, cg = mass_state(items, poly, rho, lwd, dw, dr, batt, tail, avfwd)
        mot = {k: (x + dw + dr, y) for k, (x, y) in motors.items()}
        loads = mc.hover_split(M, cg[:2], {k: np.array(v) for k, v in mot.items()})
        worst = max(loads.values()) / M
        dc, do = closed[dw], opened[(dw, dr)]
        mac = dc["geo"]["mac_m"] * 1000
        sm_c = (dc["x_np_mm"] - cg[0]) / mac
        sm_o = (do["x_np_mm"] - cg[0]) / do["geo"]["mac_m"] / 1000
        trims, trims4 = [], []
        for d in (dc, do):
            trims.append(float(np.degrees(av.trim(d, cg[0], M, 15.0)[1])))
            trims4.append(float(np.degrees(av.trim(d, cg[0], M, 15.0, surf="dall")[1])))
        ok_h = worst <= 0.30
        ok_f = sm_c >= 0.05 and sm_o <= 0.20 and max(abs(t) for t in trims4) <= 10
        cost = (abs(dw) / 30 + abs(dr) / 30 + (1.5 if dr < -fwd else 0) + {"V18 x362": 0, "tray-front x284": 0.5, "nose bay x150": 2}[batt]
                + (0.3 if tail else 0) + (1.0 if avfwd else 0) + (0.5 if lwc == "best" else 0))
        rows.append({"dw_mm": dw, "dr_mm": dr, "battery": batt, "tail_lwpla": tail, "avionics_forward": avfwd,
                     "lwpla": lwc, "needs_le_extension": bool(dr < -fwd), "all_up_g": round(M, 0),
                     "cg_x_mm": round(float(cg[0]), 1), "rotor_centroid_x_mm": 330 + dw + dr,
                     "np_closed_x_mm": round(dc["x_np_mm"], 1), "np_open_x_mm": round(do["x_np_mm"], 1),
                     "sm_closed_pct": round(100 * sm_c, 1), "sm_open_pct": round(100 * sm_o, 1),
                     "worst_motor_pct_weight": round(100 * worst, 1),
                     "elevon_trim_15ms_deg": [round(t, 1) for t in trims],
                     "all4_surfaces_trim_15ms_deg": [round(t, 1) for t in trims4],
                     "hover_ok": bool(ok_h), "flight_ok": bool(ok_f), "both_ok": bool(ok_h and ok_f),
                     "change_cost": round(cost, 2)})
    base = next(r for r in rows if r["dw_mm"] == 0 and r["dr_mm"] == 0 and r["battery"] == "V18 x362"
                and not r["tail_lwpla"] and not r["avionics_forward"] and r["lwpla"] == "planning")
    feas = sorted([r for r in rows if r["both_ok"]], key=lambda r: r["change_cost"])
    best_partial = sorted(rows, key=lambda r: (max(0, 5 - r["sm_closed_pct"]) * 3 + max(0, r["worst_motor_pct_weight"] - 30)))[:8]
    # first wing shift at which ANY combination passes, and the open-wells-only relaxation
    relaxed = sorted([r for r in rows if r["hover_ok"] and r["sm_open_pct"] >= 5 and max(abs(t) for t in r["all4_surfaces_trim_15ms_deg"][1:]) <= 10],
                     key=lambda r: r["change_cost"])
    out = {"_note": __doc__.strip(), "rotor_shift_limits_mm": {"forward": round(fwd, 1), "aft": round(aft, 1),
                                                                 "wing_le_at_wells": round(le, 1), "flap_le": round(flap_le, 1)},
           "lwpla_density_used": lw, "baseline": base, "feasible": feas[:20], "n_feasible": len(feas),
           "closest_if_none_feasible": best_partial,
           "feasible_if_wells_act_open": relaxed[:10], "n_feasible_if_wells_act_open": len(relaxed), "all": rows}
    (ROOT / "analysis" / "balance_study.json").write_text(json.dumps(out, indent=1))
    plot(rows, base, ROOT / "analysis" / "balance_study.png")
    print("baseline", json.dumps(base))
    print("feasible", len(feas))
    for r in (feas[:4] or best_partial[:4]):
        print(json.dumps(r))
    print("feasible if wells act open:", len(relaxed))
    for r in relaxed[:4]:
        print(json.dumps(r))
    return 0


def plot(rows, base, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 6.5))
    for batt, mk in zip(BATTERY, "osD"):
        r = [x for x in rows if x["battery"] == batt and x["tail_lwpla"] and x["lwpla"] == "planning"]
        ax.scatter([x["sm_closed_pct"] for x in r], [x["worst_motor_pct_weight"] for x in r], marker=mk, s=28,
                   c=["#1e8449" if x["both_ok"] else "#7f8c8d" for x in r], label=f"battery {batt} (LW-PLA tail)", alpha=0.85)
    ax.scatter([base["sm_closed_pct"]], [base["worst_motor_pct_weight"]], marker="X", s=160, c="#c0392b", label="V18 as modelled")
    ax.axvline(5, color="#1e8449", ls="--", lw=1)
    ax.axhline(30, color="#1e8449", ls="--", lw=1)
    ax.fill_between([5, 40], 0, 30, color="#1e8449", alpha=0.08, label="target region")
    ax.set_xlabel("static margin, wells closed (% MAC)  ->  more stable")
    ax.set_ylabel("worst lift motor share of weight in hover (%)")
    ax.set_xlim(min(-30, base["sm_closed_pct"] - 5), 40); ax.set_ylim(20, 60)
    ax.set_title("V18 balance study: wing shift x rotor shift x battery location")
    ax.legend(fontsize=8, loc="upper right"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
