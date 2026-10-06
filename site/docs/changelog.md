# Changelog

## 0.5.0 - 2026-10-06

V19-S: the four-rotor layout without the big tail.

- New variant V19-S, now the recommendation. It keeps V19-W's four lift motors in your V18 wing wells, the pilot's-eye
  camera and the single EDF, and drops the 0.18 m2 boom tail. Two features take over its job. The outer falcon panels
  and elevons sweep 300 mm back at the wrist (the "stoop"), carried by a swept 10 x 10 carbon spar per side. A 0.07 m2
  falcon crest sits on the tips of your V18 fins, 4 deg leading edge down, with a 30 % elevator on one slim servo.
  The wing group moves 235 mm aft and the battery stays in the V18 tray. Result: 2,832 g (183 g lighter than V19-W),
  1,188 mm long (168 mm shorter), static margin 8.0 / 13.9 %, heaviest motor 25.5 %, no new collisions.
- For the record: a fixed crest (no elevator) gets the margin but needs 16-38 deg of elevon at 16 m/s with the wells
  open, outside the 10 deg gate; the search keeps those rows in the V19 document.
- Fixes: tail incidence and position are now part of the aero cache key; the web viewer maps GLB node names with dots
  back to part names, so the outer servo cassettes follow their panels; F4 is no longer slotted for a removed gear
  crossbar (V19-W).
- Web app and docs: V19-S in the switcher, V19-S gates in TEST_GATES.md (wrist load, crest tufts, crest elevator).


## 0.4.0 - 2026-10-04

V19-W: four rotors in the wings, pilot's-eye camera, one EDF.

- New variant V19-W, now the recommendation. All four lift motors sit in your V18 wing wells, the front pair in the holes
  V19-R closes. The wing group moves 200 mm aft with a 0.18 m2 falcon tail on the EDF outrigger booms. Two short
  under-wing booms carry the rear motors, so the rear crossrail can sit ahead of the D1 intake; the main gear legs bolt to
  the rear motor backing plates, and the gear crossbar goes. Static margin 8.2 %, heaviest motor
  26.2 %, no new collisions.
- Cockpit: the FPV camera moves back to a pilot's eye point (x 120-140, z 44) on a printed pilot-seat mount, under a
  vacuum-formed clear PETG canopy on a printed frame cut from your C1 cover. The GPS moves off the nose (it sat in the
  camera's view) to the H2 hatch. All V19 variants get the cockpit.
- Cruise engine: one Freewing E7206 64 mm EDF stays in the jet bay (1,200 g, 44 A, 142 g). Twin 50 mm fans would draw
  about 80 A and add a second ESC, with no lift redundancy gained; the comparison is in the V19 document.
- The V19-R slug becomes `v19r_boom_rotors`. Large tails are split spanwise so every piece fits the P1S.
- Web app: Pilot view (look around from the FPV camera with a HUD); V19-W in the switcher.


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
