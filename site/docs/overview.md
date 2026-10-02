# SKYFORGE V18 Falcon

An educational hybrid-VTOL RC aircraft with falcon / blended-wing styling. It has four 5-inch lift rotors
in wing wells and a rear 64 mm electric ducted fan (EDF), with elevons, flaps and a steerable tricycle
gear. It runs on one 4S system with ArduPilot QuadPlane on a SpeedyBee F405 WING, and is printed on a
Bambu Lab P1S. This repo is the build workbench around **the V18 design**: your V18 assembly is the
source of truth, and every number here is computed from it.

**Web version:** https://normansrule.github.io/skyforge-v18-falcon/ (after the steps in
[docs/PUBLISHING.md](docs/PUBLISHING.md)).
**App version:** Windows / macOS / Linux installers on the Releases page; the same app, offline.

> **Status: mechanical fitting / development prototype - not flight-ready.** Nothing here has been
> flown, bench-tested or slicer-validated. Named parts are reference candidates until fitted and
> measured.

![V18 planform with the neutral-point band, CG and rotors](analysis/aero_planform.png)

## The headline: V18 does not balance yet

From your V18 geometry and the BOM ([docs/BALANCE_AND_STABILITY.md](docs/BALANCE_AND_STABILITY.md)):

| | Value | Needed |
|---|---|---|
| All-up mass (LW-PLA 0.80 planning) | 2,724 g (2,515-3,183 g across densities) | - |
| Centre of gravity (CG) | x418 mm | on the rotor centroid for hover |
| Rotor thrust centroid | x330 mm | - |
| Neutral point (NP), vortex-lattice model | x285-332 mm | CG 5-12 % of the mean chord ahead |
| Static margin | -24.6 % to -15.8 % | +5 % or more |
| Heaviest motor in hover | 49.6 % of the weight (rear pair) | <= 30 % |

A search of 576 silhouette-preserving changes (wing shift, rotor shift, battery position, lighter tail,
avionics moved) found **no combination that passes both hover balance and wing-borne stability**. V19
needs a configuration change; the document above sets out four directions with numbers. Stages 0-2 (fit
coupons, LW-PLA density, single-motor bench) remain worth doing because any V19 needs those measurements.

## What is here

| Path | What | Label |
|---|---|---|
| [`site/`](site/) | Web app: 3D V18 with picking, layers, explode, cut-away, control sweep, balance ruler; balance explorer; live budget; bench log ingest; wiring map; stage tracker; all docs. Offline-capable | PROTOTYPE-READY |
| [`desktop/`](desktop/) | Tauri v2 desktop shell around `site/` (verified building and running on Linux) | PROTOTYPE-READY |
| [`cad/v18/`](cad/v18/) | Your V18 assembly, extracted part data, G10 cutting DXFs, carbon cut list, your original V18 BOM | source |
| [`cad/interface/`](cad/interface/) | Parametric parts for the joints V18 left open: crossing clamps, belly straps, EDF ear brackets, FC isolation pad, nose-steering collar, all fit-checked inside V18 | EXPERIMENTAL |
| [`bom/bom.csv`](bom/bom.csv) -> [`docs/BOM.md`](docs/BOM.md) | V18 BOM rows plus the added rows, with links, stages, purchase gates and V18 placements | PROTOTYPE-READY |
| [`docs/BUDGET.md`](docs/BUDGET.md) | Running cost, mass, CG, hover and stability gates | generated |
| [`docs/WIRING.md`](docs/WIRING.md), [`docs/HARNESS.md`](docs/HARNESS.md) | Pin-by-pin wiring per module; harness cut list from V18 positions | PROTOTYPE-READY (bench) |
| [`docs/V18_CHECKS.md`](docs/V18_CHECKS.md) | Prop/well clearance, seams, control sweeps on both sides, gear, P1S fit | results |
| [`docs/TEST_GATES.md`](docs/TEST_GATES.md) | Stage 0-10 with PASS/FIX/STOP numbers | PROTOTYPE-READY |
| [`firmware/thrust_stand/`](firmware/thrust_stand/) | Arduino Nano + HX711 thrust-stand logger (ESP-free) | PROTOTYPE-READY (compiles) |
| [`config/ardupilot/`](config/ardupilot/) | Bench-only ArduPilot port map | PROTOTYPE-READY (bench) |
| [`tools/`](tools/) | Extraction, mass/CG, vortex lattice, geometry checks, balance study, budget, harness, bench ingest, web export, repo checks | - |

## Quick start

```bash
python3 -m http.server 8080 --directory site    # web app at http://localhost:8080
python3 tools/budget.py                           # regenerate docs/BOM.md and docs/BUDGET.md
python3 tools/check_repo.py                       # consistency checks (stdlib only)
npm test                                          # web calculator == Python budget
```

Workflow: measure something, then enter it in the web app's Budget or Bench tab (or in
`config/measurements.json`), re-run the budget, and buy only the next stage's rows.

## Engineering rules this repo keeps

- V18 only, one 4S system. Your V18 parts win over any candidate; the original BOM is kept in `cad/v18/`.
- A printed nozzle is not propulsion, a decorative duct is not blade containment and printed skin is
  not the load path. Never print flight propellers.
- Failed and flagged checks are reported, not hidden (`python3 tools/check_repo.py` lists them).
- First flights happen with an experienced RC / QuadPlane pilot at a proper site, line-of-sight.

## Licence

No licence has been chosen yet; until one is added, all rights are reserved by the author. The vendored
libraries in `site/vendor/` keep their own licences (three.js MIT, marked MIT, fonts SIL OFL).
