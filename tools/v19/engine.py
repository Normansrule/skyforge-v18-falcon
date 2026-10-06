"""V19 configuration engine: apply design changes to the V18 assembly and evaluate them.

A configuration (config/v19/*.json or a dict) describes changes relative to V18:

  wing_shift_mm      wing group (wing panels, flaps, elevons, fins, servo cassettes, rear rotors,
                     crossrails) moved aft relative to the nose/body - the "long-nose falcon"
  front_rotor        {"mode": "wing", "dx": mm}  - front pair stays in wing wells, shifted within the wing
                     {"mode": "boom", "x": mm}    - front pair on forward booms ahead of the wing leading
                                                    edge (front wells closed over)
  rear_rotor_dx_mm   rear pair shifted within the wing
  battery            "v18" | "tray_front" | "nose_bay"
  avionics_forward   FC, VTX, EDF ESC, alarm move 140 mm forward into the old battery bay (needs nose_bay)
  tail_parts_lwpla   EDF saddles + D1/D2 ducts printed in LW-PLA instead of PETG
  lwpla_density      g/cm3 for LW-PLA parts (0.80 planning, 0.60 best case)
  tail               null or a horizontal "falcon tail" on a dorsal pylon:
                     {"area_m2", "aspect", "taper", "x_le_root_mm", "incidence_deg", "elevator_frac"}

Evaluation returns mass, CG, rotor positions, hover loads, neutral-point bounds (rotor wells closed /
open), static margins, trim at 16 m/s with all pitch surfaces, stall speeds, main-gear station and the
pass/fail gates used in docs/TEST_GATES.md. Point-mass + linear vortex-lattice model: a screening tool to
choose the next CAD revision, not a flight clearance.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import aero_vlm as av  # noqa: E402
import mass_cg as mc  # noqa: E402
import v18geom as g  # noqa: E402

ROOT = g.ROOT
WELL_R = 72.5
PROP_R = 63.5
MOTOR_Y = 220.0
FRONT_X, REAR_X = 240.0, 420.0
CARBON10_G_PER_M = 55.8
LE_AT_WELLS = 136.0       # most forward-reaching V18 leading edge over the well span (analysis/balance_study.json)
FLAP_LE = 587.0
SKIN_G_PER_M2_AT_08 = 1407.0  # V18 inner wing skin, LW-PLA 0.80 (computed from WRA-WRD)
TAIL_G_PER_M2_AT_08 = 1100.0  # thinner tail panel estimate (from the WRE2 falcon panel)
V_TRIM = 16.0

WING_SRC = re.compile(r"^(SP1_|FLAP_|ELEVON_)")
WING_POLY = re.compile(r"^(W[RL]|FLAP_|ELEVON_|FIN_|SP1_|SC1_)")
TAIL_POLY = re.compile(r"^(EDF_saddle|D1_|D2_)")
FRONT_HW = re.compile(r"(PURCHASE_M[13]_2207|PROP_M[13]_|motor_plate_3|motor_backing_3|PURCHASE_OR_CUT_motor_plate|PURCHASE_OR_CUT_motor_backing_plate)")
REAR_HW = re.compile(r"(PURCHASE_M[24]_2207|PROP_M[24]_|motor_plate_[24]|motor_backing_[24])")
CROSSRAIL_F = "CF_crossrail_270_10x10x620"
CROSSRAIL_R = "CF_crossrail_450_10x10x820"
MAIN_GEAR = re.compile(r"(main_gear|main_wheel|CF_gear_crossbar)")
BATT = "KEEP_OUT_BATTERY_MAX_140x50x38"
SWAP = ("KEEP_OUT_LIFT_ESC_54x46x14", "KEEP_OUT_SERVO_BEC_48x38x16")
AVIONICS = ("KEEP_OUT_FC_54x34x24", "KEEP_OUT_VTX_42x26x14", "KEEP_OUT_EDF_ESC_73x30x12_plus_margin", "xyz:520,25,12")
BATTERY_X = {"v18": 362.0, "tray_front": 284.0, "nose_bay": 150.0}

DEFAULT = {"name": "V18", "label": "V18 as modelled", "wing_shift_mm": 0.0, "front_rotor": {"mode": "wing", "dx": 0.0},
           "rear_rotor_dx_mm": 0.0, "battery": "v18", "avionics_forward": False, "tail_parts_lwpla": False,
           "lwpla_density": 0.80, "tail": None}

_ITEMS = None
_AERO_CACHE: dict = {}
CACHE_FILE = ROOT / ".cache" / "v19_aero.json"


def full(cfg: dict) -> dict:
    out = json.loads(json.dumps(DEFAULT))
    out.update(cfg)
    out["front_rotor"] = {**DEFAULT["front_rotor"], **cfg.get("front_rotor", {})}
    return out


def tail_geometry(t: dict) -> dict:
    """Straight-tapered planform from area, aspect ratio and taper (mm)."""
    S = t["area_m2"] * 1e6
    b = math.sqrt(t["aspect"] * S)
    cr = 2 * S / (b * (1 + t["taper"]))
    ct = cr * t["taper"]
    sweep = t.get("le_sweep_deg", 25.0)
    return {"y_root": 0.0, "y_tip": b / 2, "x_le_root": t["x_le_root_mm"],
            "x_le_tip": t["x_le_root_mm"] + (b / 2) * math.tan(math.radians(sweep)),
            "c_root": cr, "c_tip": ct, "incidence_deg": t.get("incidence_deg", 0.0),
            "tag": "tail", "flap_tag": "elev", "flap_frac": t.get("elevator_frac", 0.35), "span_mm": b,
            "z_mm": t.get("height_mm", 60.0)}


def rotor_layout(c: dict) -> dict:
    dw = c["wing_shift_mm"]
    fr = c["front_rotor"]
    if fr["mode"] == "boom":
        xf = fr["x"]
    else:
        xf = FRONT_X + dw + fr.get("dx", 0.0)
    xr = REAR_X + dw + c["rear_rotor_dx_mm"]
    le = LE_AT_WELLS + dw
    le_ext = 0.0
    if fr["mode"] == "wing" and not c.get("no_le_ext"):
        le_ext = max(0.0, le + 35.0 - (xf - WELL_R))
    wells = [(xr, MOTOR_Y, WELL_R)] + ([(xf, MOTOR_Y, WELL_R)] if fr["mode"] == "wing" else [])
    return {"front_x": xf, "rear_x": xr, "le_ext_mm": le_ext, "wells": wells, "wing_le_x": le - le_ext,
            "boom_clear_mm": (le - (xf + PROP_R)) if fr["mode"] == "boom" else None,
            "rear_flap_margin_mm": FLAP_LE + dw - (xr + WELL_R)}


def _items():
    global _ITEMS
    if _ITEMS is None:
        _ITEMS = mc.compute(measurements={}, want_items=True)
    return _ITEMS


def _site_xyz(src: str):
    """'site:x,y,z:mass' / 'xyz:x,y,z' -> np.array or None."""
    if src.startswith(("site:", "xyz:")):
        return np.array([float(v) for v in src.split(":")[1].split(",")[:3]])
    return None


def mass_from_geometry(c: dict, geo: dict):
    """Mass and CG with the parts where the V19 geometry puts them (cad/v19/<variant>/mass_inputs.json).

    geo = {"moves": {v18_object_or_site_src: [dx, dy, dz]}, "removed": [v18 objects],
           "new": [{"name", "mass_g", "xyz"}]}"""
    items, poly, rho, _ = _items()
    moves = geo["moves"]
    removed = set(geo.get("removed", []))
    entries = []
    for label, grp, m, xyz, basis, src in items:
        if src in removed:
            continue
        x = np.array(xyz, dtype=float) + np.array(moves.get(src, (0, 0, 0)), dtype=float)
        entries.append((label, float(m), x))
    for name, mat, v, cen in poly:
        if name in removed:
            continue
        d = c["lwpla_density"] if mat == "LW-PLA" else rho[mat]
        if c["tail_parts_lwpla"] and TAIL_POLY.match(g.template_name(name)):
            d = c["lwpla_density"]
        v = geo.get("volume_override_cm3", {}).get(name, v)
        entries.append((name, v * d, np.array(cen, dtype=float) + np.array(moves.get(name, (0, 0, 0)), dtype=float)))
    new = {}
    scale = c["lwpla_density"] / 0.80
    for n in geo["new"]:
        m = n["mass_g"] * (scale if n.get("lwpla") else 1.0)
        entries.append(("NEW " + n["name"], m, np.array(n["xyz"], dtype=float)))
        new[n["name"]] = m
    M = sum(e[1] for e in entries)
    cg = sum(e[1] * e[2] for e in entries) / M
    return M, cg, entries, new


def mass_and_cg(c: dict, gear_x: float | None = None):
    if c.get("_geometry"):
        return mass_from_geometry(c, c["_geometry"])
    items, poly, rho, _ = _items()
    dw = c["wing_shift_mm"]
    lay = rotor_layout(c)
    dxf = lay["front_x"] - FRONT_X
    dxr = lay["rear_x"] - REAR_X
    entries = []  # (label, mass, xyz)

    def add(label, m, xyz):
        entries.append((label, float(m), np.asarray(xyz, dtype=float)))

    for label, grp, m, xyz, basis, src in items:
        x = np.array(xyz, dtype=float)
        key = f"{label}|{src}"
        if FRONT_HW.search(key):
            x[0] += dxf
        elif REAR_HW.search(key) or src == CROSSRAIL_R:
            x[0] += dxr
        elif src == CROSSRAIL_F:
            x[0] += dw  # the front crossrail stays with the wing even when the front rotors go on booms
        elif WING_SRC.match(src):
            x[0] += dw
        elif src == BATT:
            x[0] = BATTERY_X[c["battery"]] if c["battery"] != "v18" else x[0]
        elif src in SWAP and c["battery"] == "tray_front":
            x[0] += 146.0
        elif src in AVIONICS and c["avionics_forward"]:
            x[0] -= 140.0
        elif MAIN_GEAR.search(src) and gear_x is not None:
            x[0] += gear_x - 385.0
        add(label, m, x)
    for name, mat, v, cen in poly:
        d = c["lwpla_density"] if mat == "LW-PLA" else rho[mat]
        if c["tail_parts_lwpla"] and TAIL_POLY.match(g.template_name(name)):
            d = c["lwpla_density"]
        x = np.array(cen, dtype=float)
        if WING_POLY.match(name):
            x[0] += dw
        add(name, v * d, x)
    scale = c["lwpla_density"] / 0.80
    new = {}
    if lay["le_ext_mm"] > 0:
        m = 2 * 0.234 * lay["le_ext_mm"] / 1000 * SKIN_G_PER_M2_AT_08 * scale
        add("NEW leading-edge extension", m, (lay["wing_le_x"] + lay["le_ext_mm"] / 2, 0, 0))
        new["leading-edge extension"] = m
    if c["front_rotor"]["mode"] == "boom":
        L = (FRONT_X + dw) - lay["front_x"] + 30.0
        m_boom = 2 * L / 1000 * CARBON10_G_PER_M + 2 * 14.0  # tubes + printed pods/fairings
        add("NEW front rotor booms + pods", m_boom, ((FRONT_X + dw + lay["front_x"]) / 2, 0, -10))
        new["front rotor booms + pods"] = m_boom
        # the front wells are closed over: add skin where the holes were
        m_fill = 2 * math.pi * WELL_R ** 2 / 1e6 * SKIN_G_PER_M2_AT_08 * scale
        add("NEW front well closures", m_fill, (FRONT_X + dw, 0, 0))
        new["front well closures"] = m_fill
    if c["tail"]:
        tg = tail_geometry(c["tail"])
        area = c["tail"]["area_m2"]
        m_tail = area * TAIL_G_PER_M2_AT_08 * scale
        m_pylon = 28.0 * scale + 12.0  # printed dorsal pylon + carbon spar stub
        m_servo = 12.0 + 5.0           # elevator servo + linkage
        x_ac = tg["x_le_root"] + 0.25 * tg["c_root"]
        add("NEW falcon tail", m_tail, (x_ac + 0.1 * tg["c_root"], 0, 60))
        add("NEW tail pylon + spar", m_pylon, (tg["x_le_root"] - 10, 0, 45))
        add("NEW elevator servo + linkage", m_servo, (tg["x_le_root"] - 30, 0, 30))
        new["falcon tail"] = m_tail
        new["tail pylon + spar"] = m_pylon
        new["elevator servo + linkage"] = m_servo
    if c["battery"] == "nose_bay":
        add("NEW nose battery bay structure", 18.0 * scale + 8.0, (150.0, 0, -18))
        new["nose battery bay structure"] = 18.0 * scale + 8.0
    M = sum(e[1] for e in entries)
    cg = sum(e[1] * e[2] for e in entries) / M
    return M, cg, entries, new


def _aero_key(kind: str, c: dict) -> str:
    lay = rotor_layout(c)
    tail = tail_geometry(c["tail"]) if c["tail"] else None
    k = {"kind": kind, "dw": round(c["wing_shift_mm"], 1), "le": round(lay["le_ext_mm"], 1),
         "wells": [[round(x, 1), y, r] for x, y, r in lay["wells"]] if kind == "open" else None,
         "tail": {kk: round(v, 2) for kk, v in tail.items() if isinstance(v, float)} if tail else None,
         "v": 4}
    if c.get("outer_shift_mm"):
        k["outer"] = round(c["outer_shift_mm"], 1)
    if tail and (tail["incidence_deg"] or c["tail"].get("mount")):
        # integer-valued fields slip past the float filter above; key them explicitly (A-W tails set x from dw alone)
        k["tail_x"] = round(float(tail["x_le_root"]), 1)
        k["inc"] = round(float(tail["incidence_deg"]), 2)
        k["mount"] = c["tail"].get("mount")
    return hashlib.sha1(json.dumps(k, sort_keys=True).encode()).hexdigest()[:16]


def _load_cache():
    if not _AERO_CACHE and CACHE_FILE.exists():
        _AERO_CACHE.update(json.loads(CACHE_FILE.read_text()))


def save_cache():
    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(_AERO_CACHE))


RES = {"fine": (10.0, 12.0), "fast": (14.0, 18.0)}
MODE = {"res": "fine"}


def aero(c: dict, kind: str) -> dict:
    """Linear derivatives about the nose for the configuration; kind = 'closed' or 'open' rotor wells."""
    _load_cache()
    key = _aero_key(kind, c) + MODE["res"]
    strip, panel = RES[MODE["res"]]
    if key in _AERO_CACHE:
        return _AERO_CACHE[key]
    lay = rotor_layout(c)
    extra = [tail_geometry(c["tail"])] if c["tail"] else None
    if kind == "open":
        P, st = av.build_v18_lattice(strip_mm=strip, panel_mm=panel, wells=lay["wells"], wing_shift_mm=c["wing_shift_mm"], le_ext_mm=lay["le_ext_mm"], extra_surfaces=extra, outer_shift_mm=c.get("outer_shift_mm", 0.0))
    else:
        P, st = av.build_v18_lattice(strip_mm=strip, panel_mm=panel, fill_wells=True, wing_shift_mm=c["wing_shift_mm"], le_ext_mm=lay["le_ext_mm"], extra_surfaces=extra, outer_shift_mm=c.get("outer_shift_mm", 0.0))
    d = av.derivatives(P, st)
    out = {k: float(v) for k, v in d.items() if k != "geo"}
    out["geo"] = {k: float(v) for k, v in d["geo"].items()}
    _AERO_CACHE[key] = out
    return out


def evaluate(cfg: dict, gates: dict | None = None) -> dict:
    c = full(cfg)
    gates = gates or {"worst_share_max_pct": 30.0, "sm_min_pct": 5.0, "sm_max_pct": 25.0, "trim_max_deg": 10.0, "gear_aft_mm": 45.0}
    lay = rotor_layout(c)
    # two passes: put the main gear 45 mm aft of the CG, then recompute
    M, cg, entries, new = mass_and_cg(c)
    gear_x = cg[0] + gates["gear_aft_mm"]
    M, cg, entries, new = mass_and_cg(c, gear_x=gear_x)
    if c.get("_geometry"):
        gear_x = c["_geometry"].get("main_gear_x_mm", gear_x)
    else:
        gear_x = cg[0] + gates["gear_aft_mm"]
    motors = {"M1": np.array([lay["front_x"], MOTOR_Y]), "M2": np.array([lay["rear_x"], -MOTOR_Y]),
              "M3": np.array([lay["front_x"], -MOTOR_Y]), "M4": np.array([lay["rear_x"], MOTOR_Y])}
    loads = mc.hover_split(M, cg[:2], motors)
    worst = max(loads.values())
    dc, do = aero(c, "closed"), aero(c, "open")
    mac = dc["geo"]["mac_m"] * 1000
    sm_c = (dc["x_np_mm"] - cg[0]) / mac
    sm_o = (do["x_np_mm"] - cg[0]) / (do["geo"]["mac_m"] * 1000)
    trims, trims20 = {}, {}
    for lab, d in (("closed", dc), ("open", do)):
        dd = dict(d)
        dd["geo"] = d["geo"]
        for V, out in ((V_TRIM, trims), (20.0, trims20)):
            a, de, CL = av.trim(dd, cg[0], M, V, surf="dpitch")
            out[lab] = {"alpha_deg": round(math.degrees(a), 1), "pitch_surfaces_deg": round(math.degrees(de), 1), "CL": round(CL, 3)}
    S = dc["geo"]["S_m2"]
    stall = {f"CLmax_{cl}": round(math.sqrt(2 * M / 1000 * 9.80665 / (1.225 * S * cl)), 1) for cl in (0.7, 0.9)}
    hover_ok = worst / M * 100 <= gates["worst_share_max_pct"]
    flight_ok = (sm_c * 100 >= gates["sm_min_pct"] and sm_o * 100 <= gates["sm_max_pct"]
                 and max(abs(t["pitch_surfaces_deg"]) for t in trims.values()) <= gates["trim_max_deg"]
                 and min(t["alpha_deg"] for t in trims.values()) > -2)
    geom_ok = (lay["rear_flap_margin_mm"] >= 15 and (lay["boom_clear_mm"] is None or lay["boom_clear_mm"] >= 15))
    cfg_out = {k: v for k, v in c.items() if k != "_geometry"}
    return {
        "config": cfg_out, "mass_basis": "V19 geometry" if c.get("_geometry") else "planning allowances",
        "all_up_g": round(M, 1), "cg_mm": [round(float(v), 1) for v in cg],
        "new_parts_g": {k: round(v, 1) for k, v in new.items()},
        "rotor_front_x_mm": round(lay["front_x"], 1), "rotor_rear_x_mm": round(lay["rear_x"], 1),
        "rotor_centroid_x_mm": round((lay["front_x"] + lay["rear_x"]) / 2, 1),
        "le_extension_mm": round(lay["le_ext_mm"], 1), "boom_prop_to_le_mm": None if lay["boom_clear_mm"] is None else round(lay["boom_clear_mm"], 1),
        "rear_well_to_flap_mm": round(lay["rear_flap_margin_mm"], 1),
        "motor_hover_g": {k: round(float(v), 1) for k, v in loads.items()},
        "worst_motor_pct": round(worst / M * 100, 1),
        "np_closed_x_mm": round(dc["x_np_mm"], 1), "np_open_x_mm": round(do["x_np_mm"], 1), "mac_mm": round(mac, 1),
        "sm_closed_pct": round(float(sm_c) * 100, 1), "sm_open_pct": round(float(sm_o) * 100, 1),
        "trim_16ms": trims, "trim_20ms": trims20, "stall_speed_ms": stall, "wing_area_m2": round(S, 4),
        "main_gear_x_mm": round(float(gear_x), 1),
        "length_mm": round(max(810.0, 675.0 + c["wing_shift_mm"], (tail_geometry(c["tail"])["x_le_root"] + tail_geometry(c["tail"])["c_root"]) if c["tail"] else 0), 1),
        "hover_ok": bool(hover_ok), "flight_ok": bool(flight_ok), "geometry_ok": bool(geom_ok),
        "passes": bool(hover_ok and flight_ok and geom_ok),
    }
