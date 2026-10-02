"""Shared loader for the user's V18 assembly (cad/v18/V18_EQUIPMENT_ASSEMBLY_VIEW_ONLY.3mf).

The 3MF is the source of truth for geometry. This module parses it once, caches the meshes to
.cache/v18.npz (git-ignored) and classifies every object by its V18 name prefix:

    printed   F*, C1, H1, H2, W*, FLAP_*, ELEVON_*, FIN_*, TRAY_*, CAM_*, D1/D2, SP1/SC1, EDF_saddle_*
    carbon    CF_*                       (dimensions are encoded in the name, e.g. CF_keel_24_8x8x420)
    g10       G10_*, FIT_G10_*, PURCHASE_OR_CUT_*
    purchase  PURCHASE_*                 (motor envelopes, gear legs, wheels)
    keepout   KEEP_OUT_*                 (equipment envelopes)
    prop      NO_PRINT_PURCHASED_PROP_*  (reference only - never printed)

Axes (V18): +X aft from the nose, +Y starboard, +Z up, millimetres.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "cad" / "v18" / "V18_EQUIPMENT_ASSEMBLY_VIEW_ONLY.3mf"
CACHE = ROOT / ".cache"
NS = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"

AERO_PARTS = re.compile(r"^(F[1-4]_hollow_body|W[RL][A-F]\d?_|FLAP_|ELEVON_)")


def classify(name: str) -> str:
    if name.startswith("KEEP_OUT"):
        return "keepout"
    if name.startswith("NO_PRINT"):
        return "prop"
    if name.startswith("CF_"):
        return "carbon"
    if name.startswith(("G10_", "FIT_G10", "PURCHASE_OR_CUT")):
        return "g10"
    if name.startswith("PURCHASE_"):
        return "purchase"
    return "printed"


def template_name(name: str) -> str:
    """Instance name -> print template name (SP1_..._PRINT4_-180 -> SP1_side_servo_cassette)."""
    return re.sub(r"_PRINT\d.*$|_(0|40)$", "", name)


def side(name: str, centroid_y: float) -> str:
    if re.match(r"^W[RL]", name):
        return "R" if name[1] == "R" else "L"
    if name.endswith(("_R", "_R_falcon")):
        return "R"
    if name.endswith(("_L", "_L_falcon")):
        return "L"
    if abs(centroid_y) < 1.0:
        return "C"
    return "R" if centroid_y > 0 else "L"


@dataclass
class Part:
    name: str
    cls: str
    color: str
    vertices: np.ndarray
    faces: np.ndarray

    def mesh(self):
        import trimesh
        return trimesh.Trimesh(self.vertices, self.faces, process=False)


def _parse() -> list[Part]:
    from lxml import etree

    data = zipfile.ZipFile(SRC).read("3D/3dmodel.model")
    root = etree.fromstring(data, parser=etree.XMLParser(huge_tree=True))
    mats = {bm.get("id"): [b.get("displaycolor") for b in bm.findall(NS + "base")]
            for bm in root.iter(NS + "basematerials")}
    objs = {}
    for o in root.iter(NS + "object"):
        m = o.find(NS + "mesh")
        if m is None:
            continue
        v = np.array([[float(x.get("x")), float(x.get("y")), float(x.get("z"))] for x in m.find(NS + "vertices")])
        f = np.array([[int(t.get("v1")), int(t.get("v2")), int(t.get("v3"))] for t in m.find(NS + "triangles")],
                     dtype=np.int32)
        col = "#888888"
        if o.get("pid") in mats and o.get("pindex") is not None:
            col = mats[o.get("pid")][int(o.get("pindex"))][:7]
        objs[o.get("id")] = (o.get("name"), col, v, f)
    parts = []
    for it in root.iter(NS + "item"):
        name, col, v, f = objs[it.get("objectid")]
        if it.get("transform"):
            t = [float(x) for x in it.get("transform").split()]
            R = np.array(t[:9]).reshape(3, 3)
            v = v @ R + np.array(t[9:])
        parts.append(Part(name, classify(name), col, v, f))
    return parts


@lru_cache(maxsize=1)
def load() -> list[Part]:
    CACHE.mkdir(exist_ok=True)
    digest = hashlib.sha1(SRC.read_bytes()).hexdigest()[:12]
    cache = CACHE / f"v18_{digest}.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        names = list(z["names"])
        return [Part(str(n), classify(str(n)), str(z["colors"][i]), z[f"v{i}"], z[f"f{i}"])
                for i, n in enumerate(names)]
    parts = _parse()
    arrays = {f"v{i}": p.vertices for i, p in enumerate(parts)}
    arrays.update({f"f{i}": p.faces for i, p in enumerate(parts)})
    np.savez_compressed(cache, names=np.array([p.name for p in parts]),
                        colors=np.array([p.color for p in parts]), **arrays)
    return parts


def by_name() -> dict[str, Part]:
    return {p.name: p for p in load()}


def carbon_dims(name: str):
    """CF_crossrail_270_10x10x620 -> (10, 10, 620)."""
    m = re.search(r"(\d+)x(\d+)x(\d+)$", name)
    return tuple(int(g) for g in m.groups()) if m else None
