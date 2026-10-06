#!/usr/bin/env python3
"""Aerodynamic model of the V18 planform: sections from the V18 meshes + a vortex-lattice method (VLM).

    python3 tools/aero_vlm.py            # analysis/aero.json + analysis/aero_*.png
    python3 tools/aero_vlm.py --selftest # validate the VLM against textbook cases

Method (linear, inviscid - an estimate, not a flight clearance):
  1. Slice every lifting part (F1-F4 body, wing panels A-F, flaps, elevons) with planes y = const.
     At each station: covered x-intervals (rotor wells and gaps are holes), upper/lower surface,
     camber line z_c(x) (includes incidence and twist), and which x-range belongs to a control surface.
  2. Horseshoe-vortex lattice on the planform (stair-stepped strips): bound vortex at 1/4 panel,
     control point at 3/4 panel, flow tangency with the camber slope. Rotor wells carry no panels.
  3. Neutral point = centroid of the lift increment per unit alpha; Cm0, CL0 from camber; elevon/flap
     derivatives by deflecting the camber line aft of the hinge.
Fins are not modelled (no lateral-directional results). Thickness, viscous effects, prop/EDF flow,
landing gear and the stopped lift rotors are not modelled.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

RHO = 1.225
G0 = 9.80665


# ------------------------------------------------------------------------------------------------
# Vortex lattice core (SI units)
# ------------------------------------------------------------------------------------------------
def _seg_induced(P, A, B):
    """Velocity at points P (N,3) from unit-strength segments A->B (M,3) - returns (N,M,3).
    Biot-Savart with a small core to avoid the singularity."""
    r1 = P[:, None, :] - A[None, :, :]
    r2 = P[:, None, :] - B[None, :, :]
    r0 = B - A
    c = np.cross(r1, r2)
    c2 = np.einsum("nmk,nmk->nm", c, c)
    n1 = np.linalg.norm(r1, axis=2)
    n2 = np.linalg.norm(r2, axis=2)
    eps = 1e-10
    k = (np.einsum("mk,nmk->nm", r0, r1) / np.maximum(n1, eps) - np.einsum("mk,nmk->nm", r0, r2) / np.maximum(n2, eps))
    f = np.where(c2 > 1e-12, k / (4 * np.pi * np.maximum(c2, 1e-12)), 0.0)
    return c * f[:, :, None]


def _semi_inf(P, A, direction):
    """Velocity at P from unit semi-infinite vortices starting at A going along +direction (to infinity)."""
    far = A + direction * 1e4
    return _seg_induced(P, A, far)


def solve_lattice(panels: dict, rhs_extra=None):
    """panels: arrays xa, ya, xb, yb (bound vortex endpoints, z=0), xc, yc (control points), dy, slope (dzc/dx).
    Returns influence matrix-based solution for alpha=1 rad (gamma_alpha) and for camber (gamma_0)."""
    z = panels["z"] if "z" in panels else np.zeros_like(panels["xa"])
    A_pts = np.c_[panels["xa"], panels["ya"], z]
    B_pts = np.c_[panels["xb"], panels["yb"], z]
    C = np.c_[panels["xc"], panels["yc"], z]
    ex = np.array([1.0, 0.0, 0.0])
    # horseshoe: from +inf to A, A->B, B to +inf  (velocity of inf->A = -(A->inf))
    w = (-_semi_inf(C, A_pts, ex) + _seg_induced(C, A_pts, B_pts) + _semi_inf(C, B_pts, ex))[:, :, 2]
    return w


def vlm_solve(panels: dict, aic=None):
    """Return dict of per-panel circulation for unit alpha, camber, and any deflection groups."""
    if aic is None:
        aic = solve_lattice(panels)
    lu = np.linalg.inv(aic)
    out = {"aic_inv": lu}
    # BC: w = -V (alpha - dzc/dx + delta)  with V = 1
    out["g_alpha"] = lu @ (-np.ones(len(panels["xc"])))
    out["g_camber"] = lu @ (panels["slope"])
    return out


def forces(gamma, panels, S, cref, xref):
    """Lift coefficient and pitching moment about xref (nose-up positive) for V=1, rho=1."""
    dy = panels["yb"] - panels["ya"]
    xm = (panels["xa"] + panels["xb"]) / 2
    L = gamma * dy  # per unit rho*V
    CL = 2 * L.sum() / S
    Cm = 2 * (L * (xref - xm)).sum() / (S * cref)
    return CL, Cm, L


# ------------------------------------------------------------------------------------------------
# Self-test against textbook values
# ------------------------------------------------------------------------------------------------
def build_simple_wing(span, root_c, tip_c, sweep_le_deg, ns=40, nc=8):
    """Straight-tapered, swept wing lattice (stair-stepped, like the V18 model) for validation."""
    ys = np.linspace(-span / 2, span / 2, ns + 1)
    pan = {k: [] for k in ("xa", "ya", "xb", "yb", "xc", "yc", "slope")}
    for j in range(ns):
        yc = (ys[j] + ys[j + 1]) / 2
        c = root_c + (tip_c - root_c) * abs(yc) / (span / 2)
        xle = abs(yc) * np.tan(np.radians(sweep_le_deg))
        for i in range(nc):
            x0 = xle + c * i / nc
            dx = c / nc
            pan["xa"].append(x0 + dx / 4); pan["xb"].append(x0 + dx / 4)
            pan["ya"].append(ys[j]); pan["yb"].append(ys[j + 1])
            pan["xc"].append(x0 + 3 * dx / 4); pan["yc"].append(yc)
            pan["slope"].append(0.0)
    return {k: np.array(v) for k, v in pan.items()}


def selftest() -> dict:
    """References: AeroSandbox 4.2.10 VortexLatticeMethod (independent implementation, swept panels,
    24 spanwise x 10 chordwise per semispan) and the Helmbold formula as a loose sanity check."""
    res = {}
    p = build_simple_wing(6.0, 1.0, 1.0, 0.0, ns=48, nc=10)
    s = vlm_solve(p)
    CL, Cm, _ = forces(s["g_alpha"], p, 6.0, 1.0, 0.0)
    helm = 2 * np.pi * 6 / (2 + np.sqrt(36 + 4))
    res["rect_AR6"] = {"CLa": round(CL, 3), "aerosandbox": 4.274, "err_pct": round(100 * (CL / 4.274 - 1), 2),
                       "helmbold": round(helm, 3), "xac_over_c": round(-Cm / CL, 3), "xac_aerosandbox": 0.239}
    p = build_simple_wing(5.0, 1.0, 1.0, 45.0, ns=48, nc=10)
    s = vlm_solve(p)
    CL, Cm, _ = forces(s["g_alpha"], p, 5.0, 1.0, 0.0)
    res["swept45_AR5"] = {"CLa": round(CL, 3), "aerosandbox": 3.239, "err_pct": round(100 * (CL / 3.239 - 1), 2),
                          "xac_over_c": round(-Cm / CL, 3), "xac_aerosandbox": 1.433}
    r, w = res["rect_AR6"], res["swept45_AR5"]
    res["pass"] = bool(abs(r["err_pct"]) < 3 and abs(w["err_pct"]) < 3 and abs(r["xac_over_c"] - 0.239) < 0.02
                       and abs(w["xac_over_c"] - 1.433) < 0.05 and abs(r["CLa"] / helm - 1) < 0.07)
    return res


# ------------------------------------------------------------------------------------------------
# V18 sections
# ------------------------------------------------------------------------------------------------
LIFT_PARTS = re.compile(r"^(F[1-4]_hollow_body|W[RL][A-F]\d?_(hollow|falcon)_wing|FLAP_[RL]|ELEVON_[RL]_falcon)$")
CTRL = {"FLAP_R": "flap", "FLAP_L": "flap", "ELEVON_R_falcon": "elevon", "ELEVON_L_falcon": "elevon"}


def section_points(mesh, y):
    import trimesh

    segs = trimesh.intersections.mesh_plane(mesh, plane_normal=[0, 1, 0], plane_origin=[0, y, 0])
    return segs.reshape(-1, 3)[:, [0, 2]] if len(segs) else np.zeros((0, 2))


_STATION_CACHE: dict = {}


def station(meshes, y, bin_mm=2.0, gap_fill_mm=6.0):
    key = round(y, 3)
    if key in _STATION_CACHE:
        return tuple(a.copy() for a in _STATION_CACHE[key])
    out = _station(meshes, y, bin_mm, gap_fill_mm)
    _STATION_CACHE[key] = tuple(a.copy() for a in out)
    return out


def _station(meshes, y, bin_mm=2.0, gap_fill_mm=6.0):
    """Covered x-bins, z_upper, z_lower, and control tags at span station y (mm)."""
    x0, x1 = 0.0, 820.0
    nb = int((x1 - x0) / bin_mm)
    zu = np.full(nb, -np.inf)
    zl = np.full(nb, np.inf)
    tag = np.array([""] * nb, dtype=object)
    for name, m, (bmin, bmax) in meshes:
        # sample just either side of y too, so 0.3 mm seams between V18 parts do not drop a strip
        pts = [section_points(m, yy) for yy in (y - 2.5, y, y + 2.5) if bmin[1] <= yy <= bmax[1]]
        pts = [q for q in pts if len(q)]
        if not pts:
            continue
        segs = np.vstack(pts).reshape(-1, 2, 2)
        for (xa, za), (xb, zb) in segs:
            lo, hi = sorted((xa, xb))
            i0 = int(np.clip((lo - x0) // bin_mm, 0, nb - 1))
            i1 = int(np.clip((hi - x0) // bin_mm, 0, nb - 1))
            for i in range(i0, i1 + 1):
                zu[i] = max(zu[i], za, zb)
                zl[i] = min(zl[i], za, zb)
                if name in CTRL:
                    tag[i] = CTRL[name]
    cov = np.isfinite(zu)
    # fill seams/hinge gaps
    idx = np.where(cov)[0]
    if len(idx):
        gaps = np.diff(idx)
        for k, gsize in enumerate(gaps):
            if 1 < gsize <= gap_fill_mm / bin_mm + 1:
                a, b = idx[k], idx[k + 1]
                cov[a:b] = True
                zu[a:b] = np.linspace(zu[a], zu[b], b - a)
                zl[a:b] = np.linspace(zl[a], zl[b], b - a)
                tag[a:b] = tag[b] if tag[b] == tag[a] else ""
    xs = x0 + (np.arange(nb) + 0.5) * bin_mm
    return xs, cov, zu, zl, tag


def intervals(cov):
    out, start = [], None
    for i, c in enumerate(cov):
        if c and start is None:
            start = i
        if not c and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(cov)))
    return out


_MESHES: list = []


def lifting_meshes():
    import v18geom as g

    if not _MESHES:
        for p in g.load():
            if LIFT_PARTS.match(p.name):
                m = p.mesh()
                _MESHES.append((p.name, m, m.bounds))
    return _MESHES


def np_of(P, stations):
    d = derivatives(P, stations)
    return d["x_np_mm"], d["CLa"], d["geo"]


def derivatives(P, stations) -> dict:
    """All linear derivatives about the nose (x=0) for one lattice."""
    geo = planform_metrics(stations)
    S, c = geo["S_m2"], geo["mac_m"]
    aic = solve_lattice(P)
    n = len(P["xc"])
    out = {"geo": geo}
    for key, rhs in (("a", -np.ones(n)), ("0", P["slope"]), ("de", -(P["tag"] == "elevon").astype(float)),
                     ("df", -(P["tag"] == "flap").astype(float)),
                     ("dall", -np.isin(P["tag"], ["elevon", "flap"]).astype(float)),
                     ("dt", -(P["tag"] == "elev").astype(float)),
                     ("dpitch", -np.isin(P["tag"], ["elevon", "flap", "elev"]).astype(float))):
        CL, Cm, _ = forces(np.linalg.solve(aic, rhs), P, S, c, 0.0)
        out["CL" + key], out["Cm" + key] = CL, Cm
    out["x_np_mm"] = -out["Cma"] / out["CLa"] * c * 1000
    return out


def trim(d: dict, x_cg_mm: float, mass_g: float, V: float, eta: float = 0.8, surf: str = "de"):
    """alpha, elevon (rad) for steady level flight at V with the CG at x_cg (linear model)."""
    c = d["geo"]["mac_m"]
    S = d["geo"]["S_m2"]
    xc = x_cg_mm / 1000

    def cm(key):
        return d["Cm" + key] + d["CL" + key] * xc / c

    CLreq = mass_g / 1000 * G0 / (0.5 * RHO * V * V * S)
    M = np.array([[d["CLa"], eta * d["CL" + surf]], [cm("a"), eta * cm(surf)]])
    a, de = np.linalg.solve(M, np.array([CLreq - d["CL0"], -cm("0")]))
    return a, de, CLreq


def build_v18_lattice(strip_mm=10.0, panel_mm=12.0, fill_wells=False, wing_shift_mm=0.0, wells=None, body_half_mm=81.0,
                      le_ext_mm=0.0, le_ext_span=(81.0, 315.0), extra_surfaces=None, outer_shift_mm=0.0, outer_y_mm=315.0):
    """wing_shift_mm moves every strip outboard of |y| > body_half_mm aft (wing group relative to the body).
    wells: list of (x, y, r) circles (mm, after the shift) whose panels are removed; implies fill_wells.
    outer_shift_mm moves the outer (falcon) panels outboard of outer_y_mm a further distance aft: a cranked "stoop" wing."""
    fill_wells = fill_wells or wells is not None
    meshes = lifting_meshes()
    half = max(b[1][1] for _, _, b in meshes)
    edges = np.arange(0.0, half + strip_mm, strip_mm)
    edges[-1] = min(edges[-1], half)
    pan = {k: [] for k in ("xa", "ya", "xb", "yb", "xc", "yc", "slope", "tag", "x_le", "x_te", "z")}
    stations = []
    for j in range(len(edges) - 1):
        ya, yb = edges[j], edges[j + 1]
        yc = (ya + yb) / 2
        xs, cov, zu, zl, tag = station(meshes, yc)
        with np.errstate(invalid="ignore"):
            zc = np.where(cov, (zu + zl) / 2, np.nan)
        ivs = intervals(cov)
        if fill_wells and len(ivs) > 1:
            a0, b0 = ivs[0][0], ivs[-1][1]
            gap = ~cov[a0:b0]
            zu[a0:b0][gap] = np.interp(np.where(gap)[0], np.where(~gap)[0], zu[a0:b0][~gap])
            zl[a0:b0][gap] = np.interp(np.where(gap)[0], np.where(~gap)[0], zl[a0:b0][~gap])
            cov[a0:b0] = True
            with np.errstate(invalid="ignore"):
                zc = np.where(cov, (zu + zl) / 2, np.nan)
            ivs = [(a0, b0)]
        ivs = [(a, b) for a, b in ivs if (b - a) * (xs[1] - xs[0]) >= 4.0]  # drop slivers
        ext = le_ext_mm if le_ext_span[0] < yc <= le_ext_span[1] else 0.0
        if ext > 0 and ivs:
            a0 = ivs[0][0]
            k = int(round(ext / (xs[1] - xs[0])))
            k = min(k, a0)
            if k > 0:  # flat extension ahead of the existing leading edge (camber continues level)
                zu[a0 - k:a0] = zu[a0]
                zl[a0 - k:a0] = zl[a0]
                cov[a0 - k:a0] = True
                tag[a0 - k:a0] = ""
                with np.errstate(invalid="ignore"):
                    zc = np.where(cov, (zu + zl) / 2, np.nan)
                ivs[0] = (a0 - k, ivs[0][1])
        if not ivs:
            continue
        sh = (wing_shift_mm if yc > body_half_mm else 0.0) + (outer_shift_mm if yc > outer_y_mm else 0.0)
        stations.append({"y": yc, "le": float(xs[ivs[0][0]] - 1 + sh), "te": float(xs[ivs[-1][1] - 1] + 1 + sh),
                         "intervals": [[float(xs[a] - 1 + sh), float(xs[b - 1] + 1 + sh)] for a, b in ivs],
                         "tmax": float(np.nanmax(zu[cov] - zl[cov]))})
        for a, b in ivs:
            xl, xr = xs[a] - 1.0, xs[b - 1] + 1.0
            n = max(1, int(round((xr - xl) / panel_mm)))
            dx = (xr - xl) / n
            seg_x = xs[a:b]
            seg_z = zc[a:b]
            shift = (wing_shift_mm if yc > body_half_mm else 0.0) + (outer_shift_mm if yc > outer_y_mm else 0.0)
            for i in range(n):
                x0 = xl + i * dx
                if wells is not None and shift is not None:
                    xcp_s = x0 + 0.75 * dx + shift
                    if yc > body_half_mm and any((xcp_s - wx) ** 2 + (yc - abs(wy)) ** 2 < wr * wr for wx, wy, wr in wells):
                        continue
                xcp = x0 + 0.75 * dx
                # camber slope by central difference over +/- dx/2 around the control point
                xa_s, xb_s = max(xcp - dx / 2, seg_x[0]), min(xcp + dx / 2, seg_x[-1])
                za_s, zb_s = np.interp([xa_s, xb_s], seg_x, seg_z)
                slope = (zb_s - za_s) / (xb_s - xa_s) if xb_s > xa_s else 0.0
                k = int(np.clip(np.searchsorted(seg_x, xcp), 0, len(seg_x) - 1))
                for sgn in (1, -1):  # starboard strip and its mirror
                    y0, y1 = (ya, yb) if sgn == 1 else (-yb, -ya)
                    pan["xa"].append(x0 + dx / 4 + shift); pan["xb"].append(x0 + dx / 4 + shift)
                    pan["ya"].append(y0); pan["yb"].append(y1)
                    pan["xc"].append(xcp + shift); pan["yc"].append(sgn * yc)
                    pan["slope"].append(slope)
                    pan["tag"].append(tag[a:b][k])
                    pan["x_le"].append(xl + shift); pan["x_te"].append(xr + shift)
                    pan["z"].append(0.0)
    for surf in extra_surfaces or []:
        add_surface(pan, surf, strip_mm, panel_mm)
    P = {k: np.array(v) for k, v in pan.items()}
    for k in ("xa", "ya", "xb", "yb", "xc", "yc", "x_le", "x_te", "z"):
        P[k] = P[k] / 1000.0  # -> metres
    return P, stations


def add_surface(pan, s, strip_mm=10.0, panel_mm=12.0):
    """Append a mirrored, flat, straight-tapered surface (e.g. a horizontal tail).
    s: y_root, y_tip, x_le_root, x_le_tip, c_root, c_tip (mm), incidence_deg (leading edge up +),
    tag, flap_frac (aft fraction tagged `flap_tag`, e.g. an elevator)."""
    n_span = max(2, int(round((s["y_tip"] - s["y_root"]) / strip_mm)))
    ys = np.linspace(s["y_root"], s["y_tip"], n_span + 1)
    slope0 = -np.tan(np.radians(s.get("incidence_deg", 0.0)))
    for j in range(n_span):
        ya, yb = ys[j], ys[j + 1]
        yc = (ya + yb) / 2
        f = (yc - s["y_root"]) / (s["y_tip"] - s["y_root"])
        xl = s["x_le_root"] + f * (s["x_le_tip"] - s["x_le_root"])
        c = s["c_root"] + f * (s["c_tip"] - s["c_root"])
        n = max(2, int(round(c / panel_mm)))
        dx = c / n
        for i in range(n):
            x0 = xl + i * dx
            frac = (i + 0.5) / n
            tag = s.get("flap_tag", "elev") if frac > 1 - s.get("flap_frac", 0.0) else s.get("tag", "tail")
            for sgn in (1, -1):
                y0, y1 = (ya, yb) if sgn == 1 else (-yb, -ya)
                pan["xa"].append(x0 + dx / 4); pan["xb"].append(x0 + dx / 4)
                pan["ya"].append(y0); pan["yb"].append(y1)
                pan["xc"].append(x0 + 0.75 * dx); pan["yc"].append(sgn * yc)
                pan["slope"].append(slope0)
                pan["tag"].append(tag)
                pan["x_le"].append(xl); pan["x_te"].append(xl + c)
                pan["z"].append(s.get("z_mm", 0.0))


def planform_metrics(stations):
    y = np.array([s["y"] for s in stations]) / 1000
    chord = np.array([sum(b - a for a, b in s["intervals"]) for s in stations]) / 1000  # wetted (holes removed)
    full = np.array([s["te"] - s["le"] for s in stations]) / 1000                     # LE-TE, wells included
    le = np.array([s["le"] for s in stations]) / 1000
    dy = np.gradient(y) if len(y) > 1 else np.array([0.01])
    S = 2 * float((chord * dy).sum())
    S_full = 2 * float((full * dy).sum())
    b = 2 * float(y.max() + dy[-1] / 2)
    mac = 2 * float((full ** 2 * dy).sum()) / S_full
    x_le_mac = 2 * float((le * full * dy).sum()) / S_full
    return {"S_m2": S, "S_gross_m2": S_full, "span_m": b, "AR": b * b / S, "mac_m": mac, "x_le_mac_m": x_le_mac}


def analyse(mass_cases: dict) -> dict:
    P, stations = build_v18_lattice()
    geo = planform_metrics(stations)
    S, c = geo["S_m2"], geo["mac_m"]
    aic = solve_lattice(P)
    inv = np.linalg.inv(aic)
    n = len(P["xc"])
    sol = {"alpha": inv @ (-np.ones(n)), "camber": inv @ P["slope"]}
    for grp in ("elevon", "flap"):
        mask = (P["tag"] == grp).astype(float)
        sol[grp] = inv @ (-mask)  # +1 rad trailing-edge-down deflection acts like +alpha on those panels
    xref = 0.0
    co = {k: forces(v, P, S, c, xref)[:2] for k, v in sol.items()}
    CLa, Cma0 = co["alpha"]
    CL0, Cm0 = co["camber"]
    x_np = xref - Cma0 / CLa * c
    res = {
        "planform": {k: round(v, 4) for k, v in geo.items()},
        "panels": int(n),
        "CL_alpha_per_rad": round(CLa, 3),
        "CL0": round(CL0, 4),
        "Cm0_about_nose": round(Cm0, 4),
        "neutral_point_x_mm": round(x_np * 1000, 1),
        "neutral_point_pct_mac": round(100 * (x_np - geo["x_le_mac_m"]) / c, 1),
        "elevon": {"CL_d_per_rad": round(co["elevon"][0], 4), "Cm_d_about_nose_per_rad": round(co["elevon"][1], 4)},
        "flap": {"CL_d_per_rad": round(co["flap"][0], 4), "Cm_d_about_nose_per_rad": round(co["flap"][1], 4)},
        "stations": stations,
    }

    def cm_about(x_mm, key):
        CL, Cm = co[key]
        return Cm + CL * (x_mm / 1000 - xref) / c  # moment transfer: Cm_p = Cm_ref + CL (x_p - x_ref)/c

    res["Cm0_about"] = lambda x: cm_about(x, "camber")
    eta = 0.8  # empirical plain-control effectiveness applied to the linear result
    cases = {}
    for name, mc in mass_cases.items():
        x_cg = mc["cg_mm"][0]
        W = mc["all_up_g"] / 1000 * G0
        sm = (x_np * 1000 - x_cg) / (c * 1000)
        trims = []
        for V in (12.0, 15.0, 18.0):
            q = 0.5 * RHO * V * V
            CLreq = W / (q * S)
            M = np.array([[co["alpha"][0], eta * co["elevon"][0]],
                          [cm_about(x_cg, "alpha"), eta * cm_about(x_cg, "elevon")]])
            rhs = np.array([CLreq - CL0, -cm_about(x_cg, "camber")])
            a, d = np.linalg.solve(M, rhs)
            trims.append({"V_ms": V, "CL": round(CLreq, 3), "alpha_deg": round(np.degrees(a), 1),
                          "elevon_deg_TE_down_pos": round(np.degrees(d), 1)})
        stall = {f"CLmax_{cl}": round(float(np.sqrt(2 * W / (RHO * S * cl))), 1) for cl in (0.6, 0.8, 1.0)}
        cases[name] = {"all_up_g": mc["all_up_g"], "cg_x_mm": x_cg, "static_margin_pct_mac": round(100 * sm, 1),
                       "trim": trims, "stall_speed_ms": stall,
                       "wing_loading_g_dm2": round(mc["all_up_g"] / (S * 100), 1)}
    res["cases"] = cases
    # neutral-point band: the real aircraft lies between these modelling bounds
    band = {"open_wells_body_lifting": round(x_np * 1000, 1)}
    Pc, sc = build_v18_lattice(fill_wells=True)
    band["closed_wells_body_lifting"] = round(derivatives(Pc, sc)["x_np_mm"], 1)
    for lab, (PP, ss) in (("open_wells_body_nonlifting", (P, stations)), ("closed_wells_body_nonlifting", (Pc, sc))):
        keep = np.abs(PP["yc"]) > 0.081
        band[lab] = round(derivatives({k: v[keep] for k, v in PP.items()}, ss)["x_np_mm"], 1)
    res["neutral_point_band_x_mm"] = band
    fwd_np = min(band.values())
    res["cg_window_conservative_x_mm"] = {"aft_limit_5pct": round(fwd_np - 0.05 * c * 1000, 1),
                                          "forward_target_12pct": round(fwd_np - 0.12 * c * 1000, 1),
                                          "basis": "most forward neutral point in the band"}
    # is the planform trimmable if the CG were where it should be? (planning mass, CG at fwd NP - 8 % MAC)
    d_open = derivatives(P, stations)
    m_plan = mass_cases.get("planning", next(iter(mass_cases.values())))["all_up_g"]
    tt = {}
    for lab, d in (("open", d_open), ("closed", derivatives(Pc, sc))):
        xcg = d["x_np_mm"] - 0.08 * c * 1000
        a, de, CL = trim(d, xcg, m_plan, 15.0)
        a4, de4, _ = trim(d, xcg, m_plan, 15.0, surf="dall")
        tt[lab] = {"cg_x_mm": round(xcg, 1), "alpha_deg": round(float(np.degrees(a)), 1),
                   "elevon_only_deg": round(float(np.degrees(de)), 1), "all_four_surfaces_deg": round(float(np.degrees(de4)), 1)}
    res["trim_if_cg_at_8pct_margin_15ms"] = tt
    # the CG window that gives 5-12 % static margin
    res["cg_window_if_wells_open_x_mm"] = {"aft_limit_5pct": round(x_np * 1000 - 0.05 * c * 1000, 1),
                             "forward_target_12pct": round(x_np * 1000 - 0.12 * c * 1000, 1)}
    res["eta_control"] = eta
    res["_lattice"] = P
    res["_sol"] = sol
    return res


def plots(res, mass_cases, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    P = res["_lattice"]
    fig, ax = plt.subplots(figsize=(10, 8.6))
    tagcol = {"": "#b9c0c8", "flap": "#4a5866", "elevon": "#2b3540"}
    for i in range(len(P["xc"])):
        x0 = P["xa"][i] - (P["xc"][i] - P["xa"][i]) / 2  # panel start
        dx = 2 * (P["xc"][i] - P["xa"][i])
        ax.add_patch(plt.Rectangle((P["ya"][i] * 1000, x0 * 1000), (P["yb"][i] - P["ya"][i]) * 1000, dx * 1000,
                                   fc=tagcol[P["tag"][i]], ec="white", lw=0.1))
    for (mx, my) in [(240, 220), (240, -220), (420, 220), (420, -220)]:
        ax.add_patch(Circle((my, mx), 63.5, fill=False, ec="#2a64b0", lw=1, ls="--"))
    xnp = res["neutral_point_x_mm"]
    ax.axhline(xnp, color="#c0392b", lw=2, label=f"neutral point x{xnp:.0f}")
    w = res["cg_window_conservative_x_mm"]
    ax.axhspan(w["forward_target_12pct"], w["aft_limit_5pct"], color="#27ae60", alpha=0.18,
               label=f"flight CG window (12-5 % MAC on the forward NP) x{w['forward_target_12pct']:.0f}-{w['aft_limit_5pct']:.0f}")
    ax.axhline(330, color="#2a64b0", lw=1.5, ls=":", label="rotor thrust centroid x330")
    for name, mc in mass_cases.items():
        ax.plot(0, mc["cg_mm"][0], "o", ms=8, label=f"CG {name}: x{mc['cg_mm'][0]:.0f}")
    x_le_mac = res["planform"]["x_le_mac_m"] * 1000
    ax.plot([-480, -480], [x_le_mac, x_le_mac + res["planform"]["mac_m"] * 1000], "k-", lw=3)
    ax.text(-470, x_le_mac + res["planform"]["mac_m"] * 500, "MAC", va="center")
    ax.set_xlim(-520, 520); ax.set_ylim(830, -20); ax.set_aspect("equal")
    ax.set_xlabel("y (mm)"); ax.set_ylabel("x (mm, aft from nose)")
    ax.set_title("V18 vortex-lattice planform (from the V18 meshes) - wells carry no panels")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout(); fig.savefig(out / "aero_planform.png", dpi=110); plt.close(fig)

    # spanwise lift distribution at the planning-case trim, 15 m/s
    sol = res["_sol"]
    y = P["yc"]
    order = np.argsort(y)
    fig, ax = plt.subplots(figsize=(9, 4))
    for key, lab in (("alpha", "per rad alpha"), ("camber", "camber (alpha=0)")):
        dy = P["yb"] - P["ya"]
        lift = sol[key] * dy
        ys = np.unique(np.round(y, 4))
        dist = [lift[np.isclose(np.round(y, 4), yy)].sum() / dy[np.isclose(np.round(y, 4), yy)][0] for yy in ys]
        ax.plot(ys * 1000, dist, label=lab)
    ax.set_xlabel("y (mm)"); ax.set_ylabel("circulation per unit V (m)"); ax.grid(alpha=0.3); ax.legend()
    ax.set_title("Spanwise loading (rotor wells show as dips)")
    fig.tight_layout(); fig.savefig(out / "aero_span_loading.png", dpi=110); plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    st = selftest()
    print("VLM self-test:", json.dumps(st))
    if args.selftest:
        return 0 if st["pass"] else 1
    import mass_cg

    mc = mass_cg.compute()
    res = analyse(mc["cases"])
    out = mass_cg.ROOT / "analysis"
    out.mkdir(exist_ok=True)
    plots(res, mc["cases"], out)
    clean = {k: v for k, v in res.items() if not k.startswith("_") and not callable(v)}
    clean["selftest"] = st
    clean["method_note"] = __doc__.split("Method")[1].strip()
    (out / "aero.json").write_text(json.dumps(clean, indent=1))
    show = {k: v for k, v in clean.items() if k not in ("stations", "method_note")}
    print(json.dumps(show, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
