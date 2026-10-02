#!/usr/bin/env python3
"""Make the app mark from the V18 planform (top view, wells cut out) and every icon size the web app
and the Tauri desktop app need.

    python3 tools/web/make_icons.py      # site/icons/*, desktop/src-tauri/icons/source.png
Then `npx tauri icon desktop/src-tauri/icons/source.png -o desktop/src-tauri/icons` (done in CI too).
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
st = json.loads((ROOT / "analysis" / "aero.json").read_text())["stations"]
CHARCOAL, SKIN, AMBER = "#26313D", "#C9CED4", "#E5A34E"


def outline():
    half = [(s["y"], s["le"]) for s in st] + [(s["y"], s["te"]) for s in reversed(st)]
    full = half + [(-y, x) for y, x in reversed(half)]
    return full


def svg_mark(size=64):
    pts = outline()
    # map: y in [-500, 500] -> [6, 58]; x in [0, 810] -> [6, 58] scaled uniformly
    s = 52 / 1000
    oy = 32
    ox = 32 - 405 * s
    d = "M" + " L".join(f"{oy + y * s:.2f},{ox + x * s:.2f}" for y, x in pts) + " Z"
    wells = "".join(f'<circle cx="{oy + wy * s:.2f}" cy="{ox + wx * s:.2f}" r="{72.5 * s:.2f}" fill="{CHARCOAL}"/>'
                    for wx in (240, 420) for wy in (220, -220))
    cg = f'<circle cx="32" cy="{ox + 418 * s:.2f}" r="2.6" fill="{AMBER}"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}">'
            f'<rect width="64" height="64" rx="12" fill="{CHARCOAL}"/><path d="{d}" fill="{SKIN}"/>{wells}{cg}</svg>')


def png(path: Path, px: int, pad=0.0):
    fig = plt.figure(figsize=(1, 1), dpi=px)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 64); ax.set_ylim(64, 0); ax.axis("off")
    ax.add_patch(FancyBboxPatch((pad, pad), 64 - 2 * pad, 64 - 2 * pad, boxstyle="round,pad=0,rounding_size=12", fc=CHARCOAL, ec="none"))
    s = (52 - 2 * pad) / 1000
    oy, ox = 32, 32 - 405 * s
    pts = [(oy + y * s, ox + x * s) for y, x in outline()]
    ax.add_patch(PathPatch(MPath(pts + [pts[0]], closed=True), fc=SKIN, ec="none"))
    for wx in (240, 420):
        for wy in (220, -220):
            ax.add_patch(Circle((oy + wy * s, ox + wx * s), 72.5 * s, fc=CHARCOAL, ec="none"))
    ax.add_patch(Circle((32, ox + 418 * s), 2.6 * (1 - pad / 32), fc=AMBER, ec="none"))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=px, transparent=True)
    plt.close(fig)


def main():
    icons = ROOT / "site" / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    (icons / "mark.svg").write_text(svg_mark())
    for px in (192, 512):
        png(icons / f"icon-{px}.png", px)
    png(icons / "icon-maskable-512.png", 512, pad=0.0)
    png(ROOT / "desktop" / "src-tauri" / "icons" / "source.png", 1024)
    print("icons written")


if __name__ == "__main__":
    main()
