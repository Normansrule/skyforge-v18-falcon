#!/usr/bin/env python3
"""Search V19 configurations for the three requested directions and their combination.

    python3 tools/v19/search.py            # analysis/v19_search.json, config/v19/*.json

Directions (each with the supporting moves the long-nose direction already implied: battery in a
nose bay, FC/VTX/EDF ESC into the vacated battery bay, tail ducts/saddles in LW-PLA):
  A  long-nose falcon     wing group 150-200 mm aft of the nose; rotors stay in wing wells
  B  falcon tail          horizontal tail on a dorsal pylon over the EDF nozzle
  C  forward rotors       front rotor pair on booms ahead of the wing leading edge, front wells closed
  W  four in the wings     all four lift rotors in your V18 wells (no dx: the holes stay where you drew them),
                          rear pair on under-wing booms so the rear crossrail clears D1, falcon tail far aft
  R  boom alternative          long nose + forward rotors + falcon tail, rear rotors left in the V18 wells,
                          the cheapest combination that passes every gate with margin on balance
                          (heaviest motor <= 28 %, static margin >= 6 % wells closed; 7.5 % for W); the front
                          props sit at the 15 mm leading-edge clearance limit

In every candidate the rotor positions are set so the rotor centroid sits on that candidate's CG
(the way you would draw it), within the geometric limits (leading edge, flaps, boom length).
Masses and their positions come from the V19 construction itself (tools/v19/geometry.py, mass-only
mode: booms, pods, risers, hangers, well caps, tail booms, fins, stabiliser, fairings, nose bay), so
the variant the search picks is the one the CAD builds. The tail sits 80 mm above the wing plane to
stay clear of the EDF jet. Coarse lattice for the search; finalists are re-evaluated at full resolution.
"""
from __future__ import annotations

import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine as E  # noqa: E402
import geometry as G  # noqa: E402

ROOT = E.ROOT
SUPPORT = {"battery": "nose_bay", "avionics_forward": True, "tail_parts_lwpla": True, "cockpit_camera": True, "gps_aft": True}
MAX_LE_EXT = 120.0
MAX_BOOM = 340.0


def balance_rotors(cfg: dict, lock_rear: bool = False) -> dict:
    """Place the rotors so their centroid matches the CG (fixed-point passes on the cheap mass model).

    lock_rear keeps the rear pair in the V18 wells (only the front booms move)."""
    c = E.full(cfg)
    dw = c["wing_shift_mm"]
    for _ in range(3):
        gi = G.mass_inputs_for(c)
        M, cg, *_ = E.mass_from_geometry(c, gi)
        target = cg[0]
        if c["front_rotor"]["mode"] == "wing":
            hi = (E.FLAP_LE - 15 - E.WELL_R) - E.REAR_X           # rear well stays 15 mm ahead of the flap
            lo = -(MAX_LE_EXT - 3.5)                              # leading-edge extension limit
            d = float(np.clip(target - (330.0 + dw), lo, hi))
            c["front_rotor"]["dx"] = d
            c["rear_rotor_dx_mm"] = d
        else:
            xr = E.REAR_X + dw + c["rear_rotor_dx_mm"]
            le = E.LE_AT_WELLS + dw
            xf_max = le - E.PROP_R - 15.0
            xf_min = (E.FRONT_X + dw) - MAX_BOOM
            xf = float(np.clip(2 * target - xr, xf_min, xf_max))
            if xf != 2 * target - xr and not lock_rear:  # front limited: move the rear pair to finish the job
                hi = (E.FLAP_LE + dw - 15 - E.WELL_R) - (E.REAR_X + dw)
                c["rear_rotor_dx_mm"] = float(np.clip(2 * target - xf - (E.REAR_X + dw), -60.0, hi))
            c["front_rotor"]["x"] = xf
    return c


def evaluate(c: dict) -> dict:
    """Evaluate with the masses of the parts as the V19 geometry builds them."""
    cc = dict(c)
    cc["_geometry"] = G.mass_inputs_for(c)
    r = E.evaluate(cc)
    r["config"] = {k: v for k, v in c.items() if k != "_geometry"}
    return r


def score(r):
    pen = max(0, 5 - r["sm_closed_pct"]) * 2 + max(0, r["worst_motor_pct"] - 30) + 0.5 * max(
        0, max(abs(t["pitch_surfaces_deg"]) for t in r["trim_16ms"].values()) - 10) + (0 if r["geometry_ok"] else 10)
    return pen


def cost(r):
    c = r["config"]
    t = c["tail"]["area_m2"] if c["tail"] else 0
    boom = (E.FRONT_X + c["wing_shift_mm"] - c["front_rotor"]["x"]) if c["front_rotor"]["mode"] == "boom" else 0
    return c["wing_shift_mm"] / 50 + t * 40 + boom / 100 + r["le_extension_mm"] / 40 + (c["lwpla_density"] < 0.7) * 0.5


def tail(area, x=790.0):
    return {"area_m2": area, "aspect": 3.2, "taper": 0.55, "le_sweep_deg": 28.0, "x_le_root_mm": x,
            "incidence_deg": 0.0, "elevator_frac": 0.35, "height_mm": 80.0}


def candidates():
    out = []
    for dw, dens in itertools.product((150, 175, 200), (0.8, 0.6)):
        out.append(("A", {**SUPPORT, "wing_shift_mm": dw, "lwpla_density": dens, "front_rotor": {"mode": "wing", "dx": 0.0}}))
    for dw, area, dens in itertools.product((0, 60, 120), (0.06, 0.09, 0.12, 0.15), (0.8,)):
        out.append(("B", {**SUPPORT, "wing_shift_mm": dw, "lwpla_density": dens, "tail": tail(area, 790 + max(0, dw - 60)),
                          "front_rotor": {"mode": "wing", "dx": 0.0}}))
    for dw, dens in itertools.product((0, 100, 150, 200, 225, 250, 275), (0.8, 0.6)):
        out.append(("C", {**SUPPORT, "wing_shift_mm": dw, "lwpla_density": dens, "front_rotor": {"mode": "boom", "x": 0.0}}))
    for dw, area in itertools.product((200, 225, 250), (0.05, 0.065, 0.08, 0.095)):
        out.append(("R", {**SUPPORT, "wing_shift_mm": dw, "lwpla_density": 0.8, "tail": tail(area, 790 + max(0, dw - 60)),
                          "front_rotor": {"mode": "boom", "x": 0.0}}))
    for dw, area in itertools.product((150, 175, 200, 225, 250), (0.10, 0.14, 0.18, 0.22)):
        out.append(("W", {**SUPPORT, "wing_shift_mm": dw, "lwpla_density": 0.8, "tail": tail(area, 675 + dw + 110),
                          "front_rotor": {"mode": "wing", "dx": 0.0}, "rear_rotor_dx_mm": 0.0, "no_le_ext": True,
                          "rear_support": "boom"}))
    return out


VARIANTS = {
    "A": ("v19a_long_nose", "V19-A long-nose falcon", "Wing group 200 mm aft, battery in a nose bay, rotors stay in the wing wells"),
    "B": ("v19b_falcon_tail", "V19-B falcon tail", "Horizontal tail on twin swept fins at the ends of the EDF outrigger booms; wing {dw} mm aft"),
    "C": ("v19c_forward_rotors", "V19-C forward rotors", "Front rotors on booms ahead of the leading edge, wing {dw} mm aft"),
    "W": ("v19w_four_in_wings", "V19-W four rotors in the wings", "All four lift rotors in your V18 wing wells, wing {dw} mm aft, falcon tail, pilot's-eye cockpit camera, one EDF"),
    "R": ("v19r_boom_rotors", "V19-R boom rotors", "Long nose, forward rotors on booms and a small falcon tail; rear rotors stay in the V18 wells"),
}


def pick(fam: str, fr: list) -> dict:
    if fam == "A":  # the direction as asked: 200 mm (top of the 150-200 mm range) at planning density
        return next(r for r in fr if r["config"]["wing_shift_mm"] == 200 and r["config"]["lwpla_density"] == 0.8)
    passing = [r for r in fr if r["passes"]]
    if fam == "R":
        passing = [r for r in passing if r["worst_motor_pct"] <= 28 and r["sm_closed_pct"] >= 6]
    if fam == "W":   # the coarse lattice reads ~1 % high on these tails; ask for more so the fine result keeps margin
        passing = [r for r in passing if r["worst_motor_pct"] <= 28 and r["sm_closed_pct"] >= 7.5]
    if fam == "C":
        passing = [r for r in passing if r["config"]["lwpla_density"] == 0.8]
    if passing:
        return min(passing, key=lambda r: r["cost"])
    return min(fr, key=lambda r: (r["score"], r["cost"]))


def main() -> int:
    E.MODE["res"] = "fast"
    t0 = time.time()
    rows = []
    for i, (fam, cfg) in enumerate(candidates()):
        c = E.full(cfg) if fam == "W" else balance_rotors(cfg, lock_rear=(fam == "R"))
        r = evaluate(c)
        r["family"] = fam
        r["score"] = round(score(r), 2)
        r["cost"] = round(cost(r), 2)
        rows.append(r)
        print(f"[{i:02d}] {fam} dw={c['wing_shift_mm']:>5} tail={c['tail']['area_m2'] if c['tail'] else 0:<5} "
              f"rho={c['lwpla_density']} front={r['rotor_front_x_mm']:>6} rear={r['rotor_rear_x_mm']:>6} CG={r['cg_mm'][0]:>6} "
              f"NP={r['np_closed_x_mm']}/{r['np_open_x_mm']} SM={r['sm_closed_pct']}/{r['sm_open_pct']} worst={r['worst_motor_pct']} "
              f"trim={[t['pitch_surfaces_deg'] for t in r['trim_16ms'].values()]} pass={r['passes']} ({time.time() - t0:.0f}s)", flush=True)
        E.save_cache()
    best = {fam: pick(fam, [r for r in rows if r["family"] == fam]) for fam in "ABCRW"}
    # finalists at full resolution
    E.MODE["res"] = "fine"
    final = {}
    cfg_dir = ROOT / "config" / "v19"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    for fam, r in best.items():
        slug, label, blurb = VARIANTS[fam]
        cfg = {**r["config"], "name": slug, "label": label, "summary": blurb.format(dw=round(r["config"]["wing_shift_mm"]))}
        rr = evaluate(cfg)
        rr["family"] = fam
        final[fam] = rr
        (cfg_dir / f"{slug}.json").write_text(json.dumps(cfg, indent=1, default=float) + "\n")
        print("FINAL", fam, rr["passes"], rr["cg_mm"][0], rr["np_closed_x_mm"], rr["np_open_x_mm"], rr["sm_closed_pct"], rr["worst_motor_pct"])
    E.save_cache()
    (ROOT / "analysis").mkdir(exist_ok=True)
    (ROOT / "analysis" / "v19_search.json").write_text(json.dumps({"_note": __doc__.strip(), "rows": rows, "final": final}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
