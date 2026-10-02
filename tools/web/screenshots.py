#!/usr/bin/env python3
"""Render the 3D views used in the docs (analysis/view_*.png) from the web app in headless Chromium.

    python3 -m http.server 8765 --directory site &      # or: make serve PORT=8765
    python3 tools/web/screenshots.py [--url http://localhost:8765/]

Needs Python Playwright with Chromium (pip install playwright && playwright install chromium); the
software renderer is fine. Optional: the docs keep working with the images already committed.
"""
import argparse
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
SHOTS = [("view_v18", "#aircraft", None), ("view_v19a_long_nose", "#v19/v19a_long_nose", None),
         ("view_v19b_falcon_tail", "#v19/v19b_falcon_tail", None), ("view_v19c_forward_rotors", "#v19/v19c_forward_rotors", None),
         ("view_v19r_recommended", "#v19/v19r_recommended", None), ("view_v19r_side", "#v19/v19r_recommended", "side"),
         ("view_v19r_top", "#v19/v19r_recommended", "top")]
HIDE = ".variant-pills, .viewport-hint { display: none !important; }"


async def main(url: str) -> None:
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = await b.new_page(viewport={"width": 1500, "height": 860}, device_scale_factor=1)
        await pg.goto(url + "#aircraft", wait_until="domcontentloaded")
        await pg.add_style_tag(content=HIDE)
        await pg.wait_for_timeout(6000)
        for name, h, view in SHOTS:
            await pg.evaluate(f"location.hash = '{h}'")
            await pg.wait_for_timeout(4500)
            if view:
                await pg.evaluate(f"window.__viewer && window.__viewer.frame('{view}', 0)")
                await pg.wait_for_timeout(1500)
            box = await pg.locator("#viewport").bounding_box()
            await pg.screenshot(path=str(ROOT / "analysis" / f"{name}.png"), clip=box, timeout=120000)
            print("wrote", name)
        await b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8765/")
    asyncio.run(main(ap.parse_args().url))
