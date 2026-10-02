# Changelog

## 0.3.0 - 2026-10-02

V19: the three requested directions, built and checked, and a recommendation that passes.

- `tools/v19/`: configuration engine, search over 44 configurations (long nose, falcon tail, forward rotors,
  combined) with masses from the V19 construction itself, variant geometry from the V18 meshes (moved parts,
  cut panels, new booms, pods, risers, hangers, well caps, glove, root fairings, tail booms, fins, stabiliser,
  elevator, nose-bay floor), full-assembly collision checks against the V18 baseline, and a generated report.
- **Result:** V19-R (wing 250 mm aft + forward rotors on booms + 0.05 m2 tail) and V19-C (wing 275 mm aft +
  forward rotors) pass every model gate; the long nose alone and the tail alone do not.
- Web app redesign: environment lighting, soft shadows, grid floor, intro, animated V18/V19 switching with an
  X-ray ghost of V18, a V19 tab with variant cards, change lists, part cards and a comparison table; refreshed
  visual style throughout (light and dark).
- Easy setup: `scripts/setup_ubuntu.sh`, `scripts/publish_github.sh`, `Makefile` (`make help`).
- Repo checks and tests cover the V19 data; CI's manual analysis job re-runs the V19 search and geometry.


## 0.2.0 - 2026-10-02

Rebuilt around the actual V18 assembly instead of a proxy layout.

- V18 geometry: extraction of all 90 objects, P1S placement search, G10 cutting DXFs, carbon cut list.
- Mass and CG model from V18 positions; vortex-lattice aero model (validated against AeroSandbox);
  geometry checks on both sides; balance study over 576 design combinations.
- **Finding:** the V18 CG (x418) is aft of the rotor centroid (x330) and of the neutral-point band
  (x285-332); no silhouette-preserving change passes both hover and wing-borne gates.
- BOM reconciled with the V18 BOM (APC B5x3E, Freewing E7206, Skywalker 60A V2, RP1 V2, generic M10 GNSS);
  added rows kept; every item placed on the V18 model.
- Interface parts redesigned for the V18 structure and fit-checked in place (the 0.1 beam/pad/cradle
  parts and the proxy layout are removed - they conflicted with the V18 crossrails).
- Harness cut list from V18 positions; wiring updated to V18 parts and trays.
- Thrust-stand firmware (Arduino Nano + HX711) and log ingest.
- Web app (GitHub Pages, offline) and Tauri desktop app; CI for checks, firmware, Pages and releases.

## 0.1.0 - 2026-09-30

First repo: improved BOM, budget tool, pin-by-pin wiring, interface CAD on a proxy layout, test gates.
