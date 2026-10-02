#!/usr/bin/env python3
"""Build the V19 variant assemblies from your V18 meshes plus the new parts each variant needs.

    python3 tools/v19/geometry.py                 # every config/v19/*.json
    python3 tools/v19/geometry.py v19r_recommended

For each variant this moves V18 objects as the configuration says (wing group aft, rotors, gear, nose-bay
battery, Tray A, avionics), cuts the V18 panels where the variant needs it (moved wells, crossrail and
hanger slots, tail-boom exits in F4), generates the new parts, collision-checks the whole assembly against
the V18 baseline, and evaluates mass, CG, hover split and stability with the masses of the parts as modelled.

Outputs
  cad/v19/<variant>/stl/*.stl            new and modified parts (printed parts are outer mould lines:
                                         print hollow with the V18 wing settings)
  cad/v19/<variant>/<variant>_print_set.3mf   the same printed parts in one file (unsliced)
  cad/v19/<variant>/dxf/*.dxf            new G10 plates
  cad/v19/<variant>/parts.json           new and modified parts: material, mass basis, centroid, P1S fit
  cad/v19/<variant>/checks.json          collisions new versus V18, clearances, jet, P1S
  cad/v19/<variant>/mass_inputs.json     where every mass sits (read by tools/v19/engine.py)
  site/models/raw/<variant>.glb          new + modified parts for the web viewer (V18 parts are moved there)
  analysis/v19_variants.json             evaluation of every variant with geometry masses

Axes as V18: +X aft from the nose, +Y starboard, +Z up, millimetres. A screening model, not a release.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from trimesh.collision import CollisionManager
from scipy.interpolate import RegularGridInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import engine as E  # noqa: E402
import v18geom as g  # noqa: E402
from v18_extract import bed_fit  # noqa: E402

ROOT = g.ROOT
OUT = ROOT / "cad" / "v19"
CACHE = ROOT / ".cache"

# ---------------------------------------------------------------------------------------------------
# design constants (mm) - every one is a V19 drawing decision, documented in docs/V19_VARIANTS.md
WING_GROUP = re.compile(r"^(W[RL]|FLAP_|ELEVON_|FIN_|SP1_|SC1_)")
FRONT_HW = re.compile(r"^(PURCHASE_M[13]_2207|NO_PRINT_PURCHASED_PROP_M[13]_|G10_motor_plate_3|G10_motor_backing_3|PURCHASE_OR_CUT_motor_plate|PURCHASE_OR_CUT_motor_backing_plate)")
REAR_HW = re.compile(r"^(PURCHASE_M[24]_2207|NO_PRINT_PURCHASED_PROP_M[24]_|G10_motor_plate_[24]|G10_motor_backing_[24])")
BACKING = re.compile(r"(motor_backing)")
MAIN_GEAR = re.compile(r"(main_gear|main_wheel|CF_gear_crossbar)")
TRAY_A = ("TRAY_A_battery_power_cassette", "G10_cassette_A_support_left", "PURCHASE_OR_CUT_cassette_A_support_strip",
          "KEEP_OUT_LIFT_ESC_54x46x14", "KEEP_OUT_SERVO_BEC_48x38x16")
AVIONICS = ("KEEP_OUT_FC_54x34x24", "KEEP_OUT_VTX_42x26x14", "KEEP_OUT_EDF_ESC_73x30x12_plus_margin")
CAM = ("CAM_19mm_cradle", "KEEP_OUT_RX_antenna_free_zone")
BATT = "KEEP_OUT_BATTERY_MAX_140x50x38"
OUTRIGGERS = ("CF_EDF_outrigger_54_8x8x174", "CF_EDF_outrigger_-54_8x8x174")
CR_F, CR_R = "CF_crossrail_270_10x10x620", "CF_crossrail_450_10x10x820"

TRAY_A_AFT = 16.0            # Tray A slides aft so the nose-bay pack clears it
CAM_RAISE = 7.0              # camera cradle base raised (cradle trimmed, camera stays at its V18 height)
PACK = (136.0, 44.0, 31.0)   # reference pack (BOM E01: CNHL 3300 4S)
BAY_X0 = 87.0                # nose-bay envelope starts here (from the collision scan)
FLOOR_T = 1.5                # G10 battery floor on the keel tops
KEEL_TOP = -20.0
AVIONICS_DX = -140.0 + TRAY_A_AFT
GEAR_DROP = -1.5             # main gear 1.5 mm lower so the crossbar clears the thickest wing section above it
# V18 avionics envelopes and where they go in the Tray A battery pocket (x 308-448 once Tray A slides aft):
# FC rotated 90 deg with the VTX stacked on it, EDF ESC rotated so its 73 mm runs fore-aft
AVIONICS_V18_CENTRE = {"KEEP_OUT_FC_54x34x24": (486.0, -17.0, 8.0), "KEEP_OUT_VTX_42x26x14": (488.0, 30.0, 5.0),
                       "KEEP_OUT_EDF_ESC_73x30x12_plus_margin": (538.0, 0.0, 5.0)}
AVIONICS_TRAY_A = {"KEEP_OUT_FC_54x34x24": ((339.0, 0.0, 8.0), (54.0, 34.0, 24.0)),
                   "KEEP_OUT_VTX_42x26x14": ((339.0, 0.0, 27.0), (42.0, 26.0, 14.0)),
                   "KEEP_OUT_EDF_ESC_73x30x12_plus_margin": ((406.0, 0.0, 2.0), (73.0, 30.0, 12.0))}
REAR_RAIL_MAX_X = 566.5      # most aft body station for a crossrail ahead of D1 / the outrigger connectors
BOOM_SEC = 10.0              # rotor booms 10x10x1 carbon
TAIL_SEC = 8.0               # tail booms 8x8x1 carbon (V18 outrigger section)
CAP_T = 0.9                  # well-closure skin (V18 skin areal density / 2 at 0.80 g/cm3)
RHO = {"PETG": 1.27, "G10": 1.85, "LW-PLA": 0.80, "TPU": 1.21}
G_PER_M = {10: 55.8, 8: 43.4, "rod6": 24.3}
SKIN_G_M2 = E.SKIN_G_PER_M2_AT_08     # both skins, per planform area
TAIL_G_M2 = E.TAIL_G_PER_M2_AT_08

BUILD_PACKS = {"v19c_forward_rotors", "v19r_recommended"}   # variants that pass get the full file set

COLORS = {"printed": "#9AA3AD", "new_printed": "#5E8DB8", "carbon": "#2A2F35", "g10": "#C9B98A", "purchase": "#1E2227",
          "keepout": "#E5A34E", "new_keepout": "#E5A34E", "petg": "#3E5F80"}


# ---------------------------------------------------------------------------------------------------
# mesh helpers
def box(x0, x1, y0, y1, z0, z1) -> trimesh.Trimesh:
    b = trimesh.creation.box([x1 - x0, y1 - y0, z1 - z0])
    b.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return b


def mirror_y(m: trimesh.Trimesh) -> trimesh.Trimesh:
    m = m.copy()
    m.vertices[:, 1] *= -1
    m.invert()
    return m


def surface_solid(P: np.ndarray, N: np.ndarray, H: np.ndarray) -> trimesh.Trimesh:
    """Closed mesh between P + H*N and P - H*N over a structured (nv, nu) grid. H >= 0.03 everywhere."""
    nv, nu, _ = P.shape
    H = np.maximum(H, 0.03)[..., None]
    top = (P + H * N).reshape(-1, 3)
    bot = (P - H * N).reshape(-1, 3)
    V = np.vstack([top, bot])
    off = nv * nu
    idx = np.arange(nv * nu).reshape(nv, nu)
    a, b, c, d = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(), idx[1:, 1:].ravel(), idx[1:, :-1].ravel()
    F = [np.c_[a, b, c], np.c_[a, c, d], np.c_[a + off, c + off, b + off], np.c_[a + off, d + off, c + off]]
    loop = list(idx[0, :]) + list(idx[1:, -1]) + list(idx[-1, -2::-1]) + list(idx[-2:0:-1, 0])
    loop = np.array(loop)
    nxt = np.roll(loop, -1)
    F += [np.c_[nxt, loop, loop + off], np.c_[nxt, loop + off, nxt + off]]
    m = trimesh.Trimesh(V, np.vstack(F), process=False)
    if m.volume < 0:
        m.invert()
    return m


def loft_rings(rings: list[np.ndarray], cap_start=True, cap_end=True, start_point=None) -> trimesh.Trimesh:
    """Closed mesh through a list of closed rings (each (k, 3), same k); start_point closes the first ring to an apex."""
    k = len(rings[0])
    V = np.vstack(rings)
    F = []
    for i in range(len(rings) - 1):
        for j in range(k):
            a, b = i * k + j, i * k + (j + 1) % k
            F += [[a, b, b + k], [a, b + k, a + k]]
    extra = []
    if cap_start:
        extra.append(rings[0].mean(0) if start_point is None else np.asarray(start_point, float))
        ci = len(V) + len(extra) - 1
        F += [[ci, (j + 1) % k, j] for j in range(k)]
    if cap_end:
        extra.append(rings[-1].mean(0))
        ci = len(V) + len(extra) - 1
        base = (len(rings) - 1) * k
        F += [[ci, base + j, base + (j + 1) % k] for j in range(k)]
    if extra:
        V = np.vstack([V, np.array(extra)])
    m = trimesh.Trimesh(V, np.array(F), process=False)
    if m.volume < 0:
        m.invert()
    return m


def naca_t(u: np.ndarray, t: float) -> np.ndarray:
    """Half-thickness of a NACA 00xx section as a fraction of chord (closed trailing edge)."""
    return 5 * t * (0.2969 * np.sqrt(u) - 0.1260 * u - 0.3516 * u ** 2 + 0.2843 * u ** 3 - 0.1036 * u ** 4)


def diff(a, *cutters):
    if not cutters:
        return a
    return trimesh.boolean.difference([a, *cutters], engine="manifold")


def union(*ms):
    return trimesh.boolean.union(list(ms), engine="manifold")


# ---------------------------------------------------------------------------------------------------
# V18 wing surfaces (starboard, V18 frame), wells filled the way the lattice fills them
class WingField:
    def __init__(self, parts: dict):
        self.mesh = trimesh.util.concatenate([parts[n].mesh() for n in parts if re.match(r"^WR[A-C]_", n)])
        self.full = trimesh.util.concatenate([parts[n].mesh() for n in parts if re.match(r"^WR[A-D]_", n)])
        self.body = trimesh.util.concatenate([parts[n].mesh() for n in ("F3_hollow_body", "F4_hollow_body")])
        self.cache = CACHE / "v19_wingfield.npz"
        self._fields = {}

    def field(self, key, xs, ys, full=False):
        if key in self._fields:
            return self._fields[key]
        f = CACHE / f"v19_field_{key}.npz"
        if f.exists():
            z = np.load(f)
            out = (z["xs"], z["ys"], z["zt"], z["zb"])
            self._fields[key] = out
            return out
        X, Y = np.meshgrid(xs, ys)
        o_top = np.c_[X.ravel(), Y.ravel(), np.full(X.size, 200.0)]
        o_bot = np.c_[X.ravel(), Y.ravel(), np.full(X.size, -200.0)]
        zt = np.full(X.size, np.nan)
        zb = np.full(X.size, np.nan)
        mesh = self.full if full else self.mesh
        loc, ri, _ = mesh.ray.intersects_location(o_top, np.tile([0, 0, -1.0], (X.size, 1)), multiple_hits=True)
        for r in np.unique(ri):
            zz = loc[ri == r, 2]
            zt[r] = zz.max()
            zb[r] = zz.min()
        zt = zt.reshape(X.shape)
        zb = zb.reshape(X.shape)
        # the V18 panels carry crossrail tunnels across the wells: treat the well discs as holes
        for wx in (E.FRONT_X, E.REAR_X):
            inside = (X - wx) ** 2 + (Y - E.MOTOR_Y) ** 2 < (E.WELL_R + 1.0) ** 2
            zt[inside] = np.nan
            zb[inside] = np.nan
        # fill gaps (wells) along x between the first and last covered sample, like the lattice does
        for arr in (zt, zb):
            for i in range(arr.shape[0]):
                row = arr[i]
                ok = ~np.isnan(row)
                if ok.sum() < 2:
                    continue
                a, b = np.where(ok)[0][[0, -1]]
                seg = row[a:b + 1]
                good = ~np.isnan(seg)
                seg[~good] = np.interp(np.where(~good)[0], np.where(good)[0], seg[good])
                row[a:b + 1] = seg
        CACHE.mkdir(exist_ok=True)
        np.savez_compressed(f, xs=xs, ys=ys, zt=zt, zb=zb)
        self._fields[key] = (xs, ys, zt, zb)
        return xs, ys, zt, zb

    def interp(self, key, xs, ys, full=False):
        xs, ys, zt, zb = self.field(key, xs, ys, full)

        def mk(a):
            a = a.copy()
            # extend each row's edges so interpolation near the leading edge stays finite
            for i in range(a.shape[0]):
                row = a[i]
                ok = ~np.isnan(row)
                if ok.any():
                    first, last = np.where(ok)[0][[0, -1]]
                    row[:first] = row[first]
                    row[last + 1:] = row[last]
                else:
                    row[:] = 0.0
            return RegularGridInterpolator((ys, xs), a, bounds_error=False, fill_value=None)
        return mk(zt), mk(zb), (xs, ys, zt, zb)

    def body_half_width(self, x: float, z0: float = -30.0, z1: float = 30.0) -> float:
        zs = np.linspace(z0, z1, 13)
        o = np.c_[np.full(zs.size, x), np.full(zs.size, 200.0), zs]
        loc, _, _ = self.body.ray.intersects_location(o, np.tile([0, -1.0, 0], (zs.size, 1)))
        return float(loc[:, 1].max()) if len(loc) else 0.0


# ---------------------------------------------------------------------------------------------------
class Builder:
    def __init__(self, slug: str, cfg: dict | None = None, light: bool = False):
        global WINGFIELD
        if WINGFIELD is None:
            WINGFIELD = WingField(g.by_name())
        self.slug = slug
        self.light = light
        self.cfg_raw = cfg if cfg is not None else json.loads((ROOT / "config" / "v19" / f"{slug}.json").read_text())
        self.c = E.full(self.cfg_raw)
        self.lay = E.rotor_layout(self.c)
        self.parts = g.by_name()
        self.wf = WINGFIELD
        self.dw = self.c["wing_shift_mm"]
        self.boom = self.c["front_rotor"]["mode"] == "boom"
        self.out = OUT / slug
        if not light:
            for sub in ("stl", "dxf"):
                (self.out / sub).mkdir(parents=True, exist_ok=True)
        self.moves: dict[str, list] = {}
        self.removed: list[str] = []
        self.modified: dict[str, trimesh.Trimesh] = {}   # V18 name -> mesh in the V18 frame (before its move)
        self.new: list[dict] = []
        self.allow: list[tuple] = []                     # (regex a, regex b, reason) intended contacts
        self.notes: list[str] = []
        self.gear_x = 385.0

    # ---------------- placement of V18 objects
    def place(self):
        c, lay, dw = self.c, self.lay, self.dw
        dxf = lay["front_x"] - E.FRONT_X
        dxr = lay["rear_x"] - E.REAR_X
        self.rear_rail_x = (E.REAR_X + dxr) if not self.boom else min(E.REAR_X + dw, REAR_RAIL_MAX_X)
        self.front_rail_x = (E.FRONT_X + dxf) if not self.boom else E.FRONT_X + dw
        for n, p in self.parts.items():
            mv = [0.0, 0.0, 0.0]
            if WING_GROUP.match(n):
                mv[0] = dw
            elif FRONT_HW.match(n):
                mv[0] = dxf
                if self.boom and BACKING.search(n):
                    mv[2] = self.boom_bot - 0.1 - (-20.0)   # backing plate becomes the clamp plate under the boom
            elif REAR_HW.match(n):
                mv[0] = dxr
                if self.boom and BACKING.search(n):
                    mv[2] = self.boom_bot - 0.1 - (-20.0)
            elif n == CR_F:
                mv[0] = self.front_rail_x - E.FRONT_X
            elif n == CR_R:
                mv[0] = self.rear_rail_x - E.REAR_X
            elif MAIN_GEAR.search(n) or n in ("G10_main_gear_left", "PURCHASE_OR_CUT_main_gear_plate"):
                mv[0] = self.gear_x - 385.0
                mv[2] = GEAR_DROP if dw > 0 else 0.0
            elif n in TRAY_A and c["battery"] == "nose_bay":
                mv[0] = TRAY_A_AFT
            elif n in AVIONICS and c["avionics_forward"]:
                mv[:] = (np.array(AVIONICS_TRAY_A[n][0]) - np.array(AVIONICS_V18_CENTRE[n])).tolist()
            elif n == "KEEP_OUT_RX_antenna_free_zone" and c["battery"] == "nose_bay":
                mv[2] = CAM_RAISE
            if any(mv):
                self.moves[n] = mv
        # mass-model placements that are not V18 objects
        site = {"site:240,24,-19:2.8": CR_F, "site:240,-24,-19:2.8": CR_F, "site:420,24,-19:2.8": CR_R,
                "site:420,-24,-19:2.8": CR_R, "site:385,24,-31:2.8": "CF_gear_crossbar_10x10x340",
                "site:385,-24,-31:2.8": "CF_gear_crossbar_10x10x340"}
        for s, obj in site.items():
            if obj in self.moves:
                self.moves[s] = self.moves[obj]
        self.allow += [(r"^W[RL][A-D]_", r"^F[1-4]_hollow_body", "wing root seats against the body side, as V18 (WRB/WRC x F2/F3)"),
                       (r"^CF_crossrail", r"(cassette_[AB]_support)", "crossrail touches the tray support strips from below, as V18 does under Tray A"),
                       (r"KEEP_OUT_FC_54x34x24__TRAY_A", r"KEEP_OUT_VTX_42x26x14__TRAY_A", "VTX stacked on the FC"),
                       (r"KEEP_OUT_.*__TRAY_A", r"TRAY_A_battery_power_cassette", "pocket floor"),
                       (r"^CF_gear_crossbar", r"^F[1-4]_hollow_body", "passes the body through a slot (V18 does this in F2)")]
        if c["battery"] == "nose_bay":
            self.moves["xyz:287,0,10"] = [TRAY_A_AFT, 0, 0]
        if c["avionics_forward"]:
            self.moves["xyz:520,25,12"] = [AVIONICS_DX, 0, 0]

    # ---------------- nose bay
    def nose_bay(self):
        if self.c["battery"] != "nose_bay":
            return
        x0 = BAY_X0
        L, W, H = PACK[0] + 4, PACK[1] + 4, PACK[2] + 2
        zf = KEEL_TOP + 0.1
        # floor plate follows the F1 inner skin (1 mm clear) where the nose narrows
        from shapely.geometry import Polygon
        f1 = self.parts["F1_hollow_body"].mesh()
        xs = np.arange(x0, x0 + L + 0.1, 2.0)
        half = []
        for x in xs:
            w = []
            for z in (zf, zf + FLOOR_T):
                loc, _, _ = f1.ray.intersects_location([[x, 0.0, z]], [[0, 1.0, 0]])
                w.append(loc[:, 1].min() if len(loc) else 99.0)
            half.append(min(W / 2, min(w) - 1.0))
        half = np.array(half)
        outline = [(x, h) for x, h in zip(xs, half)] + [(x, -h) for x, h in zip(xs[::-1], half[::-1])]
        poly = Polygon(outline).simplify(0.2)
        floor = trimesh.creation.extrude_polygon(poly, FLOOR_T)
        floor.apply_translation([0, 0, zf])
        self.floor_outline = [(round(x - x0, 2), round(y, 2)) for x, y in poly.exterior.coords]
        z0 = zf + FLOOR_T
        env = box(x0, x0 + L, -W / 2, W / 2, z0, z0 + H)
        pack_c = [x0 + L / 2, 0.0, z0 + PACK[2] / 2]
        self.moves[BATT] = [pack_c[0] - 362.0, 0.0, pack_c[2] - 15.0]   # the battery items follow the pack
        self.removed_viewer = getattr(self, "removed_viewer", []) + [BATT]
        self.add("KEEP_OUT_BATTERY_NOSE_BAY_140x48x33", env, "keepout", None, 0.0, layer="keepouts",
                 note=f"Nose-bay envelope for the BOM pack ({PACK[0]:.0f} x {PACK[1]:.0f} x {PACK[2]:.0f}) with 2 mm all round. "
                      "The V18 140 x 50 x 38 maximum does not fit the nose; buy a pack no larger than 136 x 44 x 31.")
        self.add("NEW_G10_nose_battery_floor", floor, "g10", "G10", floor.volume / 1000 * RHO["G10"],
                 note="1.5 mm G10 floor bolted to both keel tops (x150-227, 4x M3) and cantilevered 63 mm forward.",
                 dxf=("poly", self.floor_outline, [(x0 + 75, 18), (x0 + 75, -18), (x0 + 125, 18), (x0 + 125, -18)]))
        if self.c["avionics_forward"]:
            for n, (ctr, ext) in AVIONICS_TRAY_A.items():
                self.removed_viewer.append(n)
                self.add(n + "__TRAY_A", box(ctr[0] - ext[0] / 2, ctr[0] + ext[0] / 2, ctr[1] - ext[1] / 2, ctr[1] + ext[1] / 2,
                                             ctr[2] - ext[2] / 2, ctr[2] + ext[2] / 2), "keepout", None, 0.0, layer="keepouts",
                         note="Moved into the Tray A battery pocket (rotated to fit its 50 mm width); FC and VTX stacked.")
        rail = trimesh.util.concatenate([box(x0 + 6, x0 + L - 6, W / 2 + 0.1, W / 2 + 2.5, z0, z0 + 10),
                                         box(x0 + 6, x0 + L - 6, -W / 2 - 2.5, -W / 2 - 0.1, z0, z0 + 10)])
        self.add("NEW_nose_battery_rails", rail, "printed", "PETG", rail.volume / 1000 * RHO["PETG"],
                 note="Two PETG side rails with strap slots; bonded and bolted to the floor.")
        # camera cradle: base raised, camera stays where V18 has it
        self.modified["CAM_19mm_cradle"] = cam_trimmed(self.parts)
        self.mod_why.setdefault("CAM_19mm_cradle", []).append(f"base trimmed {CAM_RAISE:.0f} mm for the nose-bay pack; camera stays put")
        self.notes.append(f"CAM_19mm_cradle: bottom {CAM_RAISE:.0f} mm trimmed so the pack fits under it; the camera keeps its V18 position. "
                          "The cradle bolts to C1 so lifting C1 opens the nose bay.")
        self.allow += [(r"NEW_G10_nose_battery_floor", r"CF_keel_", "floor bolted on the keel tops"),
                       (r"NEW_nose_battery_rails", r"NEW_G10_nose_battery_floor", "rails bonded to the floor"),
                       (r"KEEP_OUT_BATTERY_NOSE_BAY", r"NEW_(G10_nose_battery_floor|nose_battery_rails)", "pack sits on the floor between the rails")]

    # ---------------- rotor booms (boom mode)
    def booms(self):
        if not self.boom:
            return
        dw, lay = self.dw, self.lay
        xf, xr = lay["front_x"], lay["rear_x"]
        x0, x1 = xf - 58.0, xr + 35.0
        top, bot = self.boom_top, self.boom_bot
        Lb = x1 - x0
        for s, side in ((1, "R"), (-1, "L")):
            y = s * E.MOTOR_Y
            tube = box(x0, x1, y - BOOM_SEC / 2, y + BOOM_SEC / 2, bot, top)
            self.add(f"NEW_CF_rotor_boom_{side}_10x10x{Lb:.0f}", tube, "carbon", "carbon", Lb / 1000 * G_PER_M[10],
                     layer="structure", note="10x10x1 carbon square tube; carries the front motor (pod) and the rear motor (riser), "
                                             "hangs under the wing from both crossrails.")
            # front motor pod
            pod = self.pod(xf, y, top, bot)
            area = pod.area
            self.add(f"NEW_front_motor_pod_{side}", pod, "printed", "PETG", area * 1.2 / 1000 * RHO["PETG"],
                     note="PETG nacelle (1.2 mm wall) around the boom nose; the V18 motor plate sits on top at the V18 motor height, "
                          "the V18 backing plate clamps under the boom.", mass_basis="surface x 1.2 mm wall")
            # hangers: crossrail bottom (-20) down to the boom top
            for nm, xc in (("front", self.front_rail_x), ("rear", self.rear_rail_x)):
                h = box(xc - 11, xc + 11, y - 8, y + 8, top + 0.05, -20.05)
                self.add(f"NEW_boom_hanger_{nm}_{side}", h, "printed", "PETG", h.volume / 1000 * RHO["PETG"],
                         note=f"PETG spacer between the {nm} crossrail and the boom, two M3 U-straps round each tube.")
            # rear motor riser (hollow PETG box)
            mx = xr
            outer = box(mx - 20, mx + 20, y - 20, y + 20, top + 0.05, -10.05)
            inner = box(mx - 18.4, mx + 18.4, y - 18.4, y + 18.4, top + 1.6, -11.65)
            riser = diff(outer, inner)
            self.add(f"NEW_rear_motor_riser_{side}", riser, "printed", "PETG", riser.volume / 1000 * RHO["PETG"],
                     note="Hollow PETG riser (1.6 mm walls) from the boom to the V18 rear motor plate.")
        self.allow += [(r"NEW_front_motor_pod", r"NEW_CF_rotor_boom", "pod is printed round the boom"),
                       (r"NEW_front_motor_pod", r"(PURCHASE_OR_CUT_motor_(plate|backing)|G10_motor_(plate|backing)_3)", "motor plate on the pod, backing under the boom inside the pod"),
                       (r"NEW_boom_hanger", r"(NEW_CF_rotor_boom|CF_crossrail)", "hanger clamps boom to crossrail"),
                       (r"NEW_rear_motor_riser", r"(NEW_CF_rotor_boom|G10_motor_plate_[24])", "riser sits on the boom under the motor plate"),
                       (r"G10_motor_backing_[24]|PURCHASE_OR_CUT_motor_backing|G10_motor_backing_3", r"NEW_CF_rotor_boom", "backing plate clamps under the boom")]
        self.notes.append(f"Rotor booms: 10x10 carbon at y +/-{E.MOTOR_Y:.0f}, z {bot:.1f} to {top:.1f} (0.5 mm under the lowest wing skin they pass).")

    def pod(self, xf, y, top, bot):
        z_plate = -10.2
        zc0 = (z_plate + (bot - 2.5)) / 2
        b0 = (z_plate - (bot - 2.5)) / 2
        a0 = 17.0
        zcb = (top + bot) / 2
        xs = np.linspace(xf - 70, xf + 75, 40)
        th = np.linspace(0, 2 * np.pi, 48, endpoint=False)
        rings = []
        for x in xs[1:]:
            t = (x - xs[0]) / (xs[-1] - xs[0])
            if t < 0.33:
                s = math.sqrt(max(0.0, 1 - (1 - t / 0.33) ** 2))
                zc, a, b = zc0, a0 * s, b0 * s
            elif t < 0.55:
                zc, a, b = zc0, a0, b0
            else:
                k = 0.5 - 0.5 * math.cos(math.pi * (t - 0.55) / 0.45)
                zc = zc0 + (zcb - zc0) * k
                a = a0 + (7.6 - a0) * k
                b = b0 + (7.6 - b0) * k
            rings.append(np.c_[np.full(th.size, x), y + a * np.cos(th), zc + b * np.sin(th)])
        return loft_rings(rings, cap_start=True, cap_end=True, start_point=[xs[0], y, zc0])

    # ---------------- well closures / fills, slots in the V18 panels
    def wells(self):
        dw, lay = self.dw, self.lay
        xs = np.arange(150.0, 512.0, 2.0)
        ys = np.arange(140.0, 302.0, 2.0)
        ft, fb, _ = self.wf.interp("wells", xs, ys)
        old = [(E.FRONT_X, E.MOTOR_Y), (E.REAR_X, E.MOTOR_Y)]           # V18 wing frame
        if self.boom:
            new_wells = [(E.REAR_X + (lay["rear_x"] - E.REAR_X - dw), E.MOTOR_Y)]
        else:
            new_wells = [(lay["front_x"] - dw, E.MOTOR_Y), (lay["rear_x"] - dw, E.MOTOR_Y)]
        moved = [w for w in new_wells if all(abs(w[0] - o[0]) > 0.5 for o in old)]
        # boom mode: thin caps over the old front wells
        if self.boom:
            cx, cy = old[0]
            r = E.WELL_R - 0.5
            v = np.linspace(-0.995, 0.995, 61)
            u = np.linspace(-1, 1, 61)
            V, U = np.meshgrid(v, u, indexing="ij")
            Y = cy + r * V
            X = cx + r * U * np.sqrt(1 - V ** 2)
            ZT = ft(np.c_[Y.ravel(), X.ravel()]).reshape(X.shape)
            ZB = fb(np.c_[Y.ravel(), X.ravel()]).reshape(X.shape)
            for which, zc in (("upper", ZT - CAP_T / 2), ("lower", ZB + CAP_T / 2)):
                P = np.stack([X + dw, Y, zc], -1)
                N = np.zeros_like(P)
                N[..., 2] = 1
                cap = surface_solid(P, N, np.full(X.shape, CAP_T / 2))
                if which == "lower":   # slots for the boom hangers that pass through the closed well
                    cap = diff(cap, *[box(xr - 12, xr + 12, cy - 9, cy + 9, -60, 0) for xr in (self.front_rail_x, self.rear_rail_x)])
                area = math.pi * r * r / 1e6
                for side, mm in (("R", cap), ("L", mirror_y(cap))):
                    self.add(f"NEW_front_well_cap_{which}_{side}", mm, "printed", "LW-PLA", area * SKIN_G_M2 / 2,
                             lwpla=True, mass_basis="V18 skin areal density",
                             note="Closes the V18 front well flush with the skin (0.9 mm, LW-PLA); glue to a 6 mm collar printed "
                                  "into the well wall." + (" Slot for the front boom hanger." if which == "lower" else ""))
            self.allow += [(r"NEW_front_well_cap", r"NEW_boom_hanger", "hanger passes the slot in the lower cap")]
        if moved:
            # wing-mode variants: fill the V18 wells, cut the new ones
            fills = []
            for (cx, cy) in old:
                r = E.WELL_R - 0.5
                v = np.linspace(-0.995, 0.995, 61)
                u = np.linspace(-1, 1, 61)
                V, U = np.meshgrid(v, u, indexing="ij")
                Y = cy + r * V
                X = cx + r * U * np.sqrt(1 - V ** 2)
                ZT = ft(np.c_[Y.ravel(), X.ravel()]).reshape(X.shape)
                ZB = fb(np.c_[Y.ravel(), X.ravel()]).reshape(X.shape)
                P = np.stack([X, Y, (ZT + ZB) / 2], -1)
                N = np.zeros_like(P)
                N[..., 2] = 1
                fills.append(surface_solid(P, N, (ZT - ZB) / 2 - 0.05))
            cyl = [self.cyl(x, y) for x, y in new_wells]
            fill = diff(trimesh.util.concatenate(fills), *cyl) if cyl else trimesh.util.concatenate(fills)
            if not fill.is_empty:
                from shapely.geometry import Point
                from shapely.ops import unary_union
                olds = unary_union([Point(x, y).buffer(E.WELL_R - 0.5, 64) for x, y in old])
                news = unary_union([Point(x, y).buffer(E.WELL_R, 64) for x, y in new_wells])
                planform = olds.difference(news).area / 1e6
                fill.apply_translation([dw, 0, 0])
                for side, mm in (("R", fill), ("L", mirror_y(fill))):
                    self.add(f"NEW_well_fill_{side}", mm, "printed", "LW-PLA", planform * SKIN_G_M2, lwpla=True,
                             mass_basis="V18 skin areal density x planform",
                             note="Fills the part of each V18 well the rotors left (printed as a hollow insert, outer surface from the "
                                  "V18 skin either side of the well).")
            self.cut_panels(cyl, "re-cut rotor wells", pattern=r"^W[RL][A-C]_")
            self.notes.append("Rotor wells re-cut at x " + ", ".join(f"{x + dw:.1f}" for x, _ in new_wells)
                              + " (V19 frame); old well areas filled.")

    def planform_area(self, m):
        from shapely.geometry import Polygon
        from shapely.ops import unary_union
        polys = []
        for f in m.vertices[m.faces][:, :, :2]:
            p = Polygon(f)
            if p.is_valid and p.area > 1e-6:
                polys.append(p)
        return unary_union(polys).area / 1e6

    def cyl(self, x, y, r=E.WELL_R):
        c = trimesh.creation.cylinder(radius=r, height=200, sections=120)
        c.apply_translation([x, y, 0])
        return c

    def cut_panels(self, cutters_v18_frame, why, pattern=r"^W[RL]"):
        """Subtract cutters (given for the starboard side in the V18 wing frame) from the panels they touch."""
        if not cutters_v18_frame:
            return
        both = list(cutters_v18_frame) + [mirror_y(c) for c in cutters_v18_frame]
        for n, p in self.parts.items():
            if not re.match(pattern, n):
                continue
            base = self.modified.get(n) or p.mesh()
            lo, hi = base.bounds
            hits = [c for c in both if np.all(c.bounds[0] <= hi) and np.all(c.bounds[1] >= lo)]
            if not hits:
                continue
            out = diff(base, *hits)
            if abs(out.volume - base.volume) > 1e-3:
                self.modified[n] = out
                self.mod_why.setdefault(n, []).append(why)

    def body_slots(self):
        """Slots in the body skins where a crossrail or the gear crossbar now passes (V18 F2 has them at the V18 stations)."""
        for n in (CR_F, CR_R, "CF_gear_crossbar_10x10x340"):
            mv = self.moves.get(n)
            if not mv or abs(mv[0]) < 0.5:
                continue
            m = self.final_mesh(n)
            (x0, y0, z0), (x1, y1, z1) = m.bounds
            cutter = box(x0 - 0.3, x1 + 0.3, y0, y1, z0 - 0.3, z1 + 0.3)
            for bn in ("F1_hollow_body", "F2_hollow_body", "F3_hollow_body", "F4_hollow_body"):
                base = self.modified.get(bn)
                base = base if base is not None else self.parts[bn].mesh()
                lo, hi = base.bounds
                if np.all(cutter.bounds[0] <= hi) and np.all(cutter.bounds[1] >= lo):
                    out = diff(base, cutter)
                    if abs(out.volume - base.volume) > 1e-3:
                        self.modified[bn] = out
                        self.mod_why.setdefault(bn, []).append(f"slot for {n} at x {(x0 + x1) / 2:.1f}")
        if any(abs(self.moves.get(n, [0])[0]) > 0.5 for n in (CR_F, CR_R)):
            self.notes.append("Plug the V18 crossrail slots in F2 that the moved crossrails leave empty (printed plugs, bond in).")

    def rail_slots(self):
        """Slot the panels where a crossrail now crosses the wing. Boom mode: the rear crossrail moves forward in the
        wing (ahead of D1) and the hangers pass the lower skin. Wing mode: both crossrails follow the rotors."""
        if not self.boom:
            cuts = []
            for n, x, x18 in ((CR_F, self.front_rail_x, E.FRONT_X), (CR_R, self.rear_rail_x, E.REAR_X)):
                xw = x - self.dw
                if abs(xw - x18) > 0.5:
                    cuts.append(box(xw - 5.3, xw + 5.3, 75, 420, -20.3, -9.7))
            self.cut_panels(cuts, "slot for the crossrail at its new station")
            self.rail_cuts = cuts
            return
        dw = self.dw
        xw = self.rear_rail_x - dw     # V18 wing frame
        cut = [box(xw - 5.3, xw + 5.3, 75, 420, -20.3, -9.7)]
        self.cut_panels(cut, "slot for the relocated rear crossrail")
        xh = self.rear_rail_x - dw
        self.cut_panels([box(xh - 11.6, xh + 11.6, E.MOTOR_Y - 8.6, E.MOTOR_Y + 8.6, -60, -19.5)], "slot for the rear boom hanger")
        self.notes.append(f"Rear crossrail moves to x {self.rear_rail_x:.1f} (wing frame x {xw:.1f}): the V18 station would put it "
                          "through the D1 intake. It now crosses the keels ahead of the outrigger connectors.")

    # ---------------- leading-edge glove (variant A)
    def glove(self):
        ext = self.lay["le_ext_mm"]
        if ext <= 0:
            return
        dw = self.dw
        xs = np.arange(80.0, 330.0, 1.5)
        ys = np.arange(78.0, 318.0, 3.0)
        ft, fb, (fx, fy, zt, zb) = self.wf.interp("glove", xs, ys)
        y0, y1 = 82.0, 314.0
        yv = np.linspace(y0, y1, 59)
        u = np.linspace(0, 1, 40) ** 1.6
        Lb = 60.0
        X = np.zeros((len(yv), len(u)))
        ZT = np.zeros_like(X)
        ZB = np.zeros_like(X)
        xles = []
        for y in yv:
            row = zt[np.argmin(abs(fy - y))]
            xles.append(fx[np.where(~np.isnan(row))[0][0]] if (~np.isnan(row)).any() else np.nan)
        xles = np.array(xles)
        ok = ~np.isnan(xles)
        xles = np.interp(yv, yv[ok], xles[ok])
        # the raw first-hit leading edge steps with the sampling; smooth it into a fair curve
        xs_fit = np.polyval(np.polyfit(yv, xles, 3), yv)
        for i, y in enumerate(yv):
            xle = float(max(xs_fit[i], xles[i]))
            xn = xle - ext
            X[i] = xn + u * (xle + Lb - xn)
            xm = xle + u * Lb
            ZT[i] = ft(np.c_[np.full(u.size, y), xm])
            ZB[i] = fb(np.c_[np.full(u.size, y), xm])
        Y = np.repeat(yv[:, None], len(u), 1)
        zc = (ZT + ZB) / 2
        P = np.stack([X, Y, zc], -1)
        N = np.zeros_like(P)
        N[..., 2] = 1
        gl = surface_solid(P, N, (ZT - ZB) / 2)
        new_front = (self.lay["front_x"] - dw, E.MOTOR_Y)
        gl = diff(gl, self.cyl(*new_front), *getattr(self, "rail_cuts", []))
        self.cut_panels([gl], "nose trimmed under the leading-edge glove", pattern=r"^W[RL][AB]_")
        planform = (ext + Lb) * (y1 - y0) / 1e6
        self.allow += [(r"NEW_leading_edge_glove", r"^F[12]_hollow_body", "glove root seats against the body side, like the wing root"),
                       (r"NEW_leading_edge_glove", r"^W[RL][AB]_", "glove bonds to the trimmed panel nose")]
        gl.apply_translation([dw, 0, 0])
        for side, mm in (("R", gl), ("L", mirror_y(gl))):
            self.add(f"NEW_leading_edge_glove_{side}", mm, "printed", "LW-PLA", planform * SKIN_G_M2, lwpla=True,
                     mass_basis="V18 skin areal density x planform",
                     note=f"Moves the inner-wing leading edge {ext:.0f} mm forward (y 82-314) so the forward-shifted front well keeps "
                          "35 mm of wing ahead of it; replaces the front 60 mm of the V18 panel nose.")

    # ---------------- root fairings where the wing root runs past the body end
    def root_fairings(self):
        dw = self.dw
        te = 675.0 + dw
        if te <= 812.0 or not self.boom:
            if te > 812.0:
                self.notes.append("Wing root runs past the body end; root fairings are only generated for the boom variants.")
            return
        xs_f = np.arange(300.0, 680.0, 2.0)
        ys_f = np.array([80.5, 82.0, 84.0])
        ft, fb, _ = self.wf.interp("root", xs_f, ys_f, full=True)
        xv = np.arange(604.0, te - 3.0, 4.0)
        yin, yout = [], []
        for x in xv:
            w = max(self.wf.body_half_width(x), self.wf.body_half_width(min(x + 4.0, 809.0))) if x < 810 else 0.0
            yin.append(max(w + 0.8, 61.0))
            yout.append(79.5)
        yin = np.array(yin)
        keep = yin < 79.0
        xv, yin = xv[keep], yin[keep]
        nu = 8
        U = np.linspace(0, 1, nu)
        X = np.repeat(xv[:, None], nu, 1)
        Y = yin[:, None] + U[None, :] * (79.5 - yin[:, None])
        q = np.c_[np.full(xv.size, 82.0), xv - dw]
        zt = ft(q)
        zb = fb(q)
        ZT = np.repeat(zt[:, None], nu, 1)
        ZB = np.repeat(zb[:, None], nu, 1)
        P = np.stack([X, Y, (ZT + ZB) / 2], -1)
        N = np.zeros_like(P)
        N[..., 2] = 1
        fr = surface_solid(P, N, np.maximum((ZT - ZB) / 2, 0.4))
        planform = float(np.trapezoid(79.5 - yin, xv)) / 1e6
        for side, mm in (("R", fr), ("L", mirror_y(fr))):
            self.add(f"NEW_F5_root_fairing_{side}", mm, "printed", "LW-PLA", planform * SKIN_G_M2, lwpla=True,
                     mass_basis="V18 skin areal density x planform",
                     note="Fills the gap between F4 and the wing root, and carries the root profile past the end of the body "
                          f"to the wing trailing edge (x {te:.0f}).")

    # ---------------- falcon tail
    def tail(self):
        if not self.c["tail"]:
            return
        t = dict(self.c["tail"])
        tg = E.tail_geometry(t)
        zt = tg["z_mm"]
        b2 = tg["y_tip"]

        def chord_at(y):
            f = y / b2
            return tg["x_le_root"] + f * (tg["x_le_tip"] - tg["x_le_root"]), tg["c_root"] + f * (tg["c_tip"] - tg["c_root"])
        yb = 54.0
        xle_b, c_b = chord_at(yb)
        # fins
        hinge_c = 1 - t.get("elevator_frac", 0.35)
        fin_le_root, fin_cr = xle_b - 45.0, (hinge_c - 0.03) * c_b + 55.0
        fin_le_tip, fin_ct = xle_b + 0.04 * c_b, (hinge_c - 0.07) * c_b
        z_root, z_tip = -8.0, zt
        boom_end = fin_le_root + fin_cr - 18.0
        x_start = 542.0
        Lt = boom_end - x_start
        for s, side in ((1, "R"), (-1, "L")):
            y = s * yb
            tube = box(x_start, boom_end, y - TAIL_SEC / 2, y + TAIL_SEC / 2, -4.0, 4.0)
            self.add(f"NEW_CF_tail_boom_{side}_8x8x{Lt:.0f}", tube, "carbon", "carbon", Lt / 1000 * G_PER_M[8], layer="structure",
                     note="Replaces the 174 mm V18 EDF outrigger with one 8x8x1 tube that runs on to the tail: same keel "
                          "connector, same EDF ear bracket, exits F4 through a slot.")
        self.removed += list(OUTRIGGERS)
        # F4 slots for the booms
        if not self.light:
            f4 = self.parts["F4_hollow_body"].mesh()
            slots = [box(x_start, boom_end + 5, s * yb - 4.6, s * yb + 4.6, -4.6, 4.6) for s in (1, -1)]
            self.modified["F4_hollow_body"] = diff(f4, *slots)
            self.mod_why.setdefault("F4_hollow_body", []).append("slots where the tail booms leave the body")
        nv, nu = 24, 36
        v = np.linspace(0, 1, nv)
        u = (1 - np.cos(np.linspace(0, np.pi, nu))) / 2
        fin_area = 0.5 * (fin_cr + fin_ct) * (z_tip - z_root) / 1e6
        for s, side in ((1, "R"), (-1, "L")):
            Z = z_root + v[:, None] * (z_tip - z_root) * np.ones((1, nu))
            le = fin_le_root + v * (fin_le_tip - fin_le_root)
            cc = fin_cr + v * (fin_ct - fin_cr)
            X = le[:, None] + u[None, :] * cc[:, None]
            Y = np.full(X.shape, s * yb)
            P = np.stack([X, Y, Z], -1)
            N = np.zeros_like(P)
            N[..., 1] = 1
            H = naca_t(u, 0.09)[None, :] * cc[:, None]
            fin = surface_solid(P, N, H)
            self.add(f"NEW_tail_fin_{side}", fin, "printed", "LW-PLA", fin_area * TAIL_G_M2, lwpla=True,
                     mass_basis="falcon-panel areal density x area",
                     note="Swept tail fin on the boom end (socket round the boom); carries the stabiliser on top.")
        # stabiliser halves + elevators
        hinge = 1 - t.get("elevator_frac", 0.35)
        for s, side in ((1, "R"), (-1, "L")):
            yv = np.linspace(3.0, b2, 30)
            le = tg["x_le_root"] + yv / b2 * (tg["x_le_tip"] - tg["x_le_root"])
            cc = tg["c_root"] + yv / b2 * (tg["c_tip"] - tg["c_root"])
            for part, (u0, u1) in (("stab", (0.0, hinge - 0.01)), ("elevator", (hinge + 0.005, 1.0))):
                uu = u0 + (u1 - u0) * (1 - np.cos(np.linspace(0, np.pi, 30))) / 2
                X = le[:, None] + uu[None, :] * cc[:, None]
                Y = np.repeat(s * yv[:, None], len(uu), 1)
                P = np.stack([X, Y, np.full(X.shape, zt)], -1)
                N = np.zeros_like(P)
                N[..., 2] = 1
                H = naca_t(uu, 0.09)[None, :] * cc[:, None]
                if part == "elevator":
                    H = np.maximum(H, 0.4)
                m = surface_solid(P, N, H)
                area = float(np.trapezoid(cc * (u1 - u0), yv)) / 1e6
                self.add(f"NEW_tail_{part}_{side}", m, "printed", "LW-PLA", area * TAIL_G_M2, lwpla=True,
                         layer="controls" if part == "elevator" else "skin", mass_basis="falcon-panel areal density x area",
                         note=("Stabiliser half, NACA 0009, 28 deg leading-edge sweep; halves join at the centre on a printed joiner."
                                if part == "stab" else f"Elevator, {100 * (1 - hinge):.0f} % chord, one piece per side, joined by a "
                                                        "wire torque rod; one servo."))
            # spar tube along each half's 30 % chord line
            p0 = np.array([tg["x_le_root"] + 0.3 * tg["c_root"], 0.0, zt])
            yt = 0.85 * b2
            xt, ct = chord_at(yt)
            p1 = np.array([xt + 0.3 * ct, s * yt, zt])
            L = float(np.linalg.norm(p1 - p0))
            sp = trimesh.creation.cylinder(radius=3.0, segment=[p0, p1], sections=16)
            self.add(f"NEW_CF_tail_spar_{side}_6x4x{L:.0f}", sp, "carbon", "carbon", L / 1000 * G_PER_M["rod6"], layer="structure",
                     note="6 x 4 mm carbon round tube spar in each stabiliser half.")
        # elevator servo in the starboard fin
        zs0 = 34.0
        xle_s = fin_le_root + (zs0 + 13 - z_root) / (z_tip - z_root) * (fin_le_tip - fin_le_root)
        cs = fin_cr + (zs0 + 13 - z_root) / (z_tip - z_root) * (fin_ct - fin_cr)
        xs0 = xle_s + 0.30 * cs
        servo = box(xs0, xs0 + 23, yb - 6.25, yb + 6.25, zs0, zs0 + 26)
        self.add("KEEP_OUT_elevator_servo_23x12x26", servo, "keepout", None, 17.0, layer="keepouts",
                 note="9 g digital servo + linkage (BOM add row T03) in a pocket in the starboard fin.")
        self.allow += [(r"NEW_tail_fin", r"NEW_CF_tail_boom", "fin socket round the boom"),
                       (r"NEW_tail_fin", r"NEW_tail_stab", "fin tip bonds into the stabiliser"),
                       (r"NEW_CF_tail_spar", r"NEW_tail_stab", "spar inside the stabiliser"),
                       (r"NEW_tail_stab_R", r"NEW_tail_stab_L", "halves meet at the joiner"),
                       (r"NEW_CF_tail_spar_R", r"NEW_CF_tail_spar_L", "spars meet at the root joiner"),
                       (r"KEEP_OUT_elevator_servo", r"NEW_tail_fin_R", "servo pocket in the fin"),
                       (r"NEW_CF_tail_boom", r"(FIT_G10_EDF_outrigger_connector|F4_hollow_body)", "same connector as the V18 outrigger; F4 slotted"),
                       (r"NEW_CF_tail_spar", r"NEW_tail_fin", "spar passes the fin top")]
        self.tail_info = {"x_le_root": tg["x_le_root"], "z": zt, "fin_inner_y": yb - naca_t(np.array([0.3]), 0.09)[0] * fin_cr,
                          "fin_x0": fin_le_root, "stab_bottom_z": zt - naca_t(np.array([0.3]), 0.09)[0] * tg["c_root"],
                          "boom_end": boom_end, "span": 2 * b2, "c_root": tg["c_root"]}

    # ---------------- registry
    def add(self, name, mesh, cls, material, mass_g, layer=None, note="", lwpla=False, mass_basis=None, dxf=None):
        if lwpla:
            mass_g = mass_g  # stored at 0.80 g/cm3, scaled by the engine for other densities
        self.new.append({"name": name, "mesh": mesh, "class": cls, "material": material, "mass_g": float(mass_g),
                         "lwpla": lwpla, "layer": layer or {"printed": "skin", "carbon": "structure", "g10": "structure",
                                                            "keepout": "keepouts", "purchase": "hardware"}[cls],
                         "note": note, "mass_basis": mass_basis or ("volume x density" if cls in ("g10", "printed") else
                                                                   "length x g/m" if cls == "carbon" else "item"),
                         "dxf": dxf})

    # ---------------- assembly + checks
    def final_mesh(self, name):
        m = self.modified.get(name)
        m = m.copy() if m is not None else self.parts[name].mesh()
        mv = self.moves.get(name)
        if mv:
            m.apply_translation(mv)
        return m

    def geometry_inputs(self):
        new = [{"name": n["name"], "mass_g": n["mass_g"], "lwpla": n["lwpla"],
                "xyz": [round(float(v), 2) for v in (n["mesh"].center_mass if n["mesh"].is_volume else n["mesh"].centroid)]}
               for n in self.new if n["mass_g"] != 0]
        vol = {}
        for nm, m in self.modified.items():
            p = self.parts[nm]
            if p.cls == "printed":
                vol[nm] = float(abs(m.volume)) / 1000
        return {"moves": self.moves, "removed": self.removed, "new": new, "volume_override_cm3": vol,
                "main_gear_x_mm": self.gear_x}

    def collisions(self):
        cm = CollisionManager()
        names = []
        for n, p in self.parts.items():
            if p.cls == "prop" or n in self.removed or n in getattr(self, "removed_viewer", []):
                continue
            cm.add_object(n, self.final_mesh(n))
            names.append(n)
        for nn in self.new:
            cm.add_object(nn["name"], nn["mesh"])
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for n in names:
            if self.parts[n].cls == "keepout":
                continue
            bb = self.final_mesh(n).bounds
            lo, hi = np.minimum(lo, bb[0]), np.maximum(hi, bb[1])
        for nn in self.new:
            if nn["class"] != "keepout":
                lo, hi = np.minimum(lo, nn["mesh"].bounds[0]), np.maximum(hi, nn["mesh"].bounds[1])
        self.extent = {"length_mm": round(float(hi[0] - min(lo[0], 0.0)), 1), "span_mm": round(float(hi[1] - lo[1]), 1),
                       "height_mm": round(float(hi[2] - lo[2]), 1)}
        _, pairs = cm.in_collision_internal(return_names=True)
        base = baseline_pairs()
        out = []
        for a, b in sorted(pairs):
            if (a, b) in base or (b, a) in base:
                continue
            why = next((r for ra, rb, r in self.allow if (re.search(ra, a) and re.search(rb, b)) or (re.search(ra, b) and re.search(rb, a))), None)
            out.append({"a": a, "b": b, "intended": why})
        return out, cm

    def build(self):
        t0 = time.time()
        self.mod_why = {}
        # boom height: under the lowest wing surface the boom passes (wells filled)
        if self.boom:
            xs = np.arange(60.0, 520.0, 2.0)
            ys = np.arange(212.0, 230.0, 2.0)
            _, fb, (fx, fy, zt, zb) = self.wf.interp("boomline", xs, ys)
            x0w = self.lay["front_x"] - 58.0 - self.dw
            x1w = self.lay["rear_x"] + 35.0 - self.dw
            sel = (fx >= x0w) & (fx <= x1w)
            zmin = np.nanmin(zb[:, sel])
            self.boom_top = round(float(zmin) - 0.5 - CAP_T * 0, 2)
            self.boom_bot = self.boom_top - BOOM_SEC
        # gear at CG + 45 (iterate with the geometry masses)
        self.gear_x = 385.0 + self.dw * 0.5
        passes = 3
        for it in range(passes):
            self.moves, self.removed, self.modified, self.new, self.allow, self.notes = {}, [], {}, [], [], []
            self.removed_viewer = []
            self.mod_why = {}
            self.place()
            self.nose_bay()
            if it == passes - 1 and not self.light:   # heavy geometry only on the last pass
                self.wells()
                self.rail_slots()
                self.body_slots()
                self.glove()
                self.root_fairings()
                self.booms()
                self.tail()
            else:
                self.booms()
                self.tail()
                self.root_fairings()
                self.wells_light()
            gi = self.geometry_inputs()
            c = dict(self.c)
            c["_geometry"] = gi
            M, cg, *_ = E.mass_and_cg(c)
            new_gear = round(float(cg[0]) + 45.0, 1)
            if it < passes - 1:
                self.gear_x = new_gear
        self.cg_geometry = cg
        if not self.light:
            print(f"  [{self.slug}] parts built in {time.time() - t0:.0f}s; gear x {self.gear_x}", flush=True)

    def wells_light(self):
        """Mass-only stand-in for the well parts on the iteration passes (same masses as the full build)."""
        if self.boom:
            r = E.WELL_R - 0.5
            area = math.pi * r * r / 1e6
            for side, s in (("R", 1), ("L", -1)):
                for which, z in (("upper", 25.0), ("lower", -26.0)):
                    m = box(E.FRONT_X + self.dw - 1, E.FRONT_X + self.dw + 1, s * E.MOTOR_Y - 1, s * E.MOTOR_Y + 1, z - 0.5, z + 0.5)
                    self.add(f"NEW_front_well_cap_{which}_{side}", m, "printed", "LW-PLA", area * SKIN_G_M2 / 2, lwpla=True)
        if not self.boom:
            from shapely.geometry import Point
            from shapely.ops import unary_union
            old = [(E.FRONT_X, E.MOTOR_Y), (E.REAR_X, E.MOTOR_Y)]
            new_w = [(self.lay["front_x"] - self.dw, E.MOTOR_Y), (self.lay["rear_x"] - self.dw, E.MOTOR_Y)]
            if any(abs(a[0] - b[0]) > 0.5 for a, b in zip(old, new_w)):
                olds = unary_union([Point(x, y).buffer(E.WELL_R - 0.5, 64) for x, y in old])
                news = unary_union([Point(x, y).buffer(E.WELL_R, 64) for x, y in new_w])
                rest = olds.difference(news)
                cx = rest.centroid.x + self.dw
                cut = news.difference(unary_union([Point(x, y).buffer(E.WELL_R, 64) for x, y in old]))
                for side, sgn in (("R", 1), ("L", -1)):
                    m = box(cx - 1, cx + 1, sgn * 220 - 1, sgn * 220 + 1, -1, 1)
                    self.add(f"NEW_well_fill_{side}", m, "printed", "LW-PLA", rest.area / 1e6 * SKIN_G_M2, lwpla=True)
                    # panel skin removed by the re-cut wells (the full build measures this from the cut meshes)
                    kx = cut.centroid.x + self.dw if not cut.is_empty else cx
                    m2 = box(kx - 1, kx + 1, sgn * 220 - 1, sgn * 220 + 1, -1, 1)
                    self.add(f"PANEL_well_recut_{side}", m2, "printed", "LW-PLA", -cut.area / 1e6 * SKIN_G_M2, lwpla=True)
        if self.lay["le_ext_mm"] > 0:
            ext = self.lay["le_ext_mm"]
            planform = (ext + 60.0) * 232.0 / 1e6
            for side, s in (("R", 1), ("L", -1)):
                m = box(80 + self.dw, 82 + self.dw, s * 198 - 1, s * 198 + 1, -1, 1)
                self.add(f"NEW_leading_edge_glove_{side}", m, "printed", "LW-PLA", planform * SKIN_G_M2, lwpla=True)
                # the front 60 mm of the panel nose is trimmed under the glove
                m2 = box(150 + self.dw, 152 + self.dw, s * 198 - 1, s * 198 + 1, -1, 1)
                self.add(f"PANEL_nose_trim_{side}", m2, "printed", "LW-PLA", -60.0 * 232.0 / 1e6 * SKIN_G_M2, lwpla=True)

    def changes(self) -> list[str]:
        c, lay, dw = self.c, self.lay, self.dw
        out = []
        if dw:
            out.append(f"Wing group {dw:.0f} mm further aft of the nose: inner and falcon panels, flaps, elevons, fins and servo "
                       "cassettes move together; nose, body, trays and EDF stay.")
        if c["battery"] == "nose_bay":
            out.append(f"Battery to a nose bay (pack centre x {BAY_X0 + (PACK[0] + 4) / 2:.0f}): 1.5 mm G10 floor on the keel tops, "
                       f"PETG rails; pack no larger than {PACK[0]:.0f} x {PACK[1]:.0f} x {PACK[2]:.0f} mm; camera-cradle base trimmed "
                       f"{CAM_RAISE:.0f} mm; lift C1 to reach the pack.")
        if c["avionics_forward"]:
            out.append(f"Tray A slides {TRAY_A_AFT:.0f} mm aft; FC with the VTX stacked on it, and the EDF ESC, move into its old battery "
                       "pocket. Tray B stays as the receiver / spare bay.")
        if self.boom:
            out.append(f"Front rotors on 10 x 10 carbon booms at y +/-{E.MOTOR_Y:.0f}, PETG nose pods at x {lay['front_x']:.1f} "
                       f"(prop {lay['boom_clear_mm']:.0f} mm ahead of the leading edge). Each boom runs under the wing to the rear "
                       "motor and hangs from both crossrails.")
            out.append("Rear motors stay in your V18 wells, on PETG risers on the boom. The front wells are closed with flush "
                       "LW-PLA caps.")
            if abs(self.rear_rail_x - (E.REAR_X + dw)) > 0.5:
                out.append(f"Rear crossrail moves to x {self.rear_rail_x:.1f}, ahead of the D1 intake: new slots in the panels and F3.")
        else:
            dx = lay["front_x"] - E.FRONT_X - dw
            if abs(dx) > 0.5:
                out.append(f"Both rotor pairs move {dx:+.0f} mm within the wing (crossrails with them): wells re-cut, the uncovered "
                           "parts of the V18 wells filled.")
            if lay["le_ext_mm"] > 0:
                out.append(f"Leading-edge glove takes the inner-wing leading edge {lay['le_ext_mm']:.0f} mm forward (y 82-314) so the "
                           "front wells keep 35 mm of wing ahead of them.")
        if c["tail"]:
            tg = E.tail_geometry(c["tail"])
            out.append(f"Falcon tail: {c['tail']['area_m2']:.3f} m2 stabiliser, {tg['span_mm']:.0f} mm span, 28 deg sweep, 80 mm above "
                       f"the wing plane on two swept fins; {100 * c['tail']['elevator_frac']:.0f} % elevator, one servo in the "
                       "starboard fin. The V18 EDF outriggers become one-piece 8 x 8 tail booms.")
        if self.boom and 675.0 + dw > 812:
            out.append(f"F5 root fairings carry the wing-root profile past the end of the body to x {675 + dw:.0f}.")
        out.append(f"Main gear to x {self.gear_x:.0f} (CG + 45 mm){' and 1.5 mm lower' if dw > 0 else ''}.")
        return out

    # ---------------- outputs
    def export(self, cm):
        from v18_extract import P1S
        parts_out = []
        printed = trimesh.Scene()
        for n in self.new:
            m = n["mesh"]
            n["P1S"] = None
            if n["class"] == "printed":
                bf = bed_fit(m)
                if bf is None:
                    n["P1S"] = {"fits": False, "footprint_max_mm": None, "note": "taller than the bed in every orientation"}
                else:
                    fits, foot, ang, hgt = bf
                    n["P1S"] = {"fits": bool(fits), "footprint_max_mm": foot, "rotation_deg": ang, "height_mm": hgt, "margin_mm": round(P1S - foot, 1)}
                printed.add_geometry(m, node_name=n["name"], geom_name=n["name"])
            if n["class"] in ("printed", "g10", "carbon"):
                m.export(self.out / "stl" / f"{n['name']}.stl")
            if n["dxf"]:
                self.write_dxf(n)
            ctr = m.center_mass if m.is_volume else m.centroid
            parts_out.append({k: v for k, v in n.items() if k not in ("mesh", "dxf")} |
                             {"centroid_mm": [round(float(v), 1) for v in ctr],
                              "bbox_mm": [round(float(v), 1) for v in m.extents], "mass_g": round(n["mass_g"], 1)})
        if self.slug not in BUILD_PACKS:   # concept variants: new parts only, no modified-panel files or print set
            return parts_out
        for nm, m in self.modified.items():
            mm = m.copy()
            mm.apply_translation(self.moves.get(nm, (0, 0, 0)))
            mm.export(self.out / "stl" / f"{nm}__V19.stl")
            if self.parts[nm].cls == "printed":
                printed.add_geometry(mm, node_name=f"{nm}__V19", geom_name=f"{nm}__V19")
        if printed.geometry:
            printed.export(self.out / f"{self.slug}_print_set.3mf")
        return parts_out

    def write_dxf(self, n):
        import ezdxf
        kind, outline, holes = n["dxf"]
        doc = ezdxf.new("R2010")
        msp = doc.modelspace()
        x0 = n["mesh"].bounds[0][0]
        msp.add_lwpolyline(outline, close=True)
        for hx, hy in holes:
            msp.add_circle((hx - x0, hy), 1.6)
        doc.saveas(self.out / "dxf" / f"{n['name']}.dxf")

    def glb(self):
        scene = trimesh.Scene()
        from trimesh.visual.material import PBRMaterial

        def col(h):
            h = h.lstrip("#")
            return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        for nm, m in self.modified.items():
            mm = m.copy()
            p = self.parts[nm]
            mm.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(name=nm, baseColorFactor=[*col(p.color), 1.0], roughnessFactor=0.75, metallicFactor=0.05))
            scene.add_geometry(mm, node_name=nm, geom_name=nm)   # V18 frame: the viewer applies the move
        for n in self.new:
            mm = n["mesh"].copy()
            key = {"printed": "petg" if n["material"] == "PETG" else "new_printed", "carbon": "carbon", "g10": "g10",
                   "keepout": "new_keepout", "purchase": "purchase"}[n["class"]]
            alpha = 0.28 if n["class"] == "keepout" else 1.0
            mm.visual = trimesh.visual.TextureVisuals(material=PBRMaterial(
                name=n["name"], baseColorFactor=[*col(COLORS[key]), alpha], roughnessFactor=0.55 if n["class"] != "carbon" else 0.35,
                metallicFactor=0.05 if n["class"] != "carbon" else 0.3, alphaMode="BLEND" if alpha < 1 else "OPAQUE",
                doubleSided=n["class"] == "keepout"))
            scene.add_geometry(mm, node_name=n["name"], geom_name=n["name"])
        raw = ROOT / "site" / "models" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        scene.export(raw / f"{self.slug}.glb")

    def checks(self, coll, cm):
        res = {"collisions_new_vs_V18": [c for c in coll if not c["intended"]],
               "intended_contacts": [c for c in coll if c["intended"]]}
        # prop discs vs the leading edge (boom variants) and vs pods / risers
        if self.boom:
            res["front_prop_to_leading_edge_mm"] = self.lay["boom_clear_mm"]
        # EDF jet versus the tail (jet radius grows ~0.1 mm per mm downstream from a 30 mm exit radius)
        if self.c["tail"]:
            ti = self.tail_info
            x_noz = 810.0
            r_at = lambda x: 30.0 + 0.10 * (x - x_noz)
            res["jet_vs_tail"] = {
                "assumed_exit_radius_mm": 30.0, "assumed_spread_mm_per_mm": 0.10,
                "jet_top_at_stab_le_mm": round(r_at(ti["x_le_root"]), 1), "stab_underside_z_mm": round(ti["stab_bottom_z"], 1),
                "stab_clear_mm": round(ti["stab_bottom_z"] - r_at(ti["x_le_root"] + 0.3 * ti["c_root"]), 1),
                "jet_radius_at_fin_le_mm": round(r_at(ti["fin_x0"]), 1), "fin_inner_face_y_mm": round(ti["fin_inner_y"], 1),
                "status": "PASS" if ti["stab_bottom_z"] - r_at(ti["x_le_root"] + 0.3 * ti["c_root"]) > 5 else "FLAG",
                "note": "Estimate only: confirm with a tuft/streamer test on the EDF bench rig before the tail is glued."}
        printed = [n for n in self.new if n["class"] == "printed"]
        res["P1S_fit"] = {n["name"]: n.get("P1S") for n in printed}
        res["status"] = "PASS" if not res["collisions_new_vs_V18"] and all((v or {}).get("fits", True) for v in res["P1S_fit"].values()) else "FAIL"
        return res


_CAM = None


def cam_trimmed(parts):
    global _CAM
    if _CAM is None:
        cam = parts["CAM_19mm_cradle"].mesh()
        zmin = cam.bounds[0][2]
        _CAM = diff(cam, box(cam.bounds[0][0] - 5, cam.bounds[1][0] + 5, -60, 60, zmin - 5, zmin + CAM_RAISE))
    return _CAM.copy()


def mass_inputs_for(cfg: dict) -> dict:
    """Where every mass sits for a configuration, using the V19 construction (no booleans, no export).
    Used by tools/v19/search.py so the search and the CAD agree."""
    b = Builder("search", cfg=cfg, light=True)
    b.build()
    return b.geometry_inputs()


_BASE = None


def baseline_pairs():
    global _BASE
    if _BASE is not None:
        return _BASE
    f = CACHE / "v18_collision_pairs.json"
    if f.exists():
        _BASE = {tuple(p) for p in json.loads(f.read_text())}
        return _BASE
    cm = CollisionManager()
    for p in g.load():
        if p.cls != "prop":
            cm.add_object(p.name, p.mesh())
    _, pairs = cm.in_collision_internal(return_names=True)
    _BASE = {tuple(sorted(p)) for p in pairs}
    f.write_text(json.dumps(sorted(_BASE)))
    return _BASE


WINGFIELD = None


def run(slug: str) -> dict:
    global WINGFIELD
    if WINGFIELD is None:
        WINGFIELD = WingField(g.by_name())
    b = Builder(slug)
    b.build()
    coll, cm = b.collisions()
    import shutil
    shutil.rmtree(b.out / "stl", ignore_errors=True)
    shutil.rmtree(b.out / "dxf", ignore_errors=True)
    for sub in ("stl", "dxf"):
        (b.out / sub).mkdir(parents=True, exist_ok=True)
    for old in b.out.glob("*_print_set.3mf"):
        old.unlink()
    parts_out = b.export(cm)          # sets each printed part's P1S fit, which checks() reports
    ck = b.checks(coll, cm)
    b.glb()
    gi = b.geometry_inputs()
    (b.out / "mass_inputs.json").write_text(json.dumps(gi, indent=1))
    c = dict(b.c)
    c["_geometry"] = gi
    ev = E.evaluate(c)
    ev["length_mm"] = b.extent["length_mm"]    # measured from the assembly (includes the swept tail tips)
    ev["planning_allowance_result"] = {k: E.evaluate(b.cfg_raw)[k] for k in ("all_up_g", "cg_mm", "sm_closed_pct", "worst_motor_pct", "passes")}
    modified = [{"name": n, "why": b.mod_why.get(n, ["modified"]), "move_mm": b.moves.get(n, [0, 0, 0])} for n in b.modified]
    (b.out / "parts.json").write_text(json.dumps({"variant": slug, "new": parts_out, "modified_v18": modified,
                                                  "removed_v18": b.removed, "notes": b.notes}, indent=1))
    (b.out / "checks.json").write_text(json.dumps(ck, indent=1))
    print(f"  [{slug}] {'PASS' if ev['passes'] else 'FAIL'} gates; checks {ck['status']}: "
          f"{len(ck['collisions_new_vs_V18'])} new collisions; M {ev['all_up_g']} CG {ev['cg_mm'][0]} SM {ev['sm_closed_pct']}/{ev['sm_open_pct']} "
          f"worst {ev['worst_motor_pct']}", flush=True)
    for cc in ck["collisions_new_vs_V18"]:
        print("     collision:", cc["a"], "x", cc["b"])
    return {"slug": slug, "evaluation": ev, "checks": ck, "extent": b.extent, "changes": b.changes(), "parts": parts_out, "modified": modified, "removed": b.removed,
            "moves": b.moves, "hidden_in_viewer": b.removed + getattr(b, "removed_viewer", []), "notes": b.notes,
            "label": b.cfg_raw.get("label", slug), "summary": b.cfg_raw.get("summary", "")}


def main(argv) -> int:
    E.MODE["res"] = "fine"
    slugs = argv[1:] or sorted(p.stem for p in (ROOT / "config" / "v19").glob("*.json"))
    out_f = ROOT / "analysis" / "v19_variants.json"
    allv = json.loads(out_f.read_text()) if out_f.exists() else {}
    for s in slugs:
        allv[s] = run(s)
        E.save_cache()
    out_f.write_text(json.dumps(allv, indent=1, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
