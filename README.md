# SKYFORGE Falcon: V18 workbench and V19 variants

An educational hybrid-VTOL RC aircraft with falcon / blended-wing styling: four 5-inch lift rotors, a rear 64 mm
electric ducted fan (EDF), flaps and elevons, a steerable tricycle gear, one 4S system, ArduPilot QuadPlane on a
SpeedyBee F405 WING, printed on a Bambu Lab P1S. This repo is the build workbench around **your V18 design**:
the V18 assembly is the source of truth, every number is computed from it, and the V19 variants are built
from its parts.

**Web version:** https://normansrule.github.io/skyforge-v18-falcon/ · **App version:** Windows / macOS / Linux
installers on the Releases page (same app, works offline). Steps: [docs/PUBLISHING.md](docs/PUBLISHING.md).

> **Status: mechanical fitting / development prototype - not flight-ready.** Nothing here has been flown,
> bench-tested or slicer-validated. Named parts are reference candidates until fitted and measured.

![V19-R, the recommended variant, in the web workbench](analysis/view_v19r_recommended.png)

## The headline

**V18 as designed does not balance; V19-R does (in the models).** V18's CG sits 88 mm tail-heavy of its rotors
and behind its neutral point, and no silhouette-preserving tweak fixes both. Your three V19 directions were each
built from the V18 parts, collision-checked and evaluated with the masses of the parts as modelled
([docs/V19_VARIANTS.md](docs/V19_VARIANTS.md)):

| | Mass | CG x | Static margin | Heaviest motor | Result |
|---|---:|---:|---:|---:|---|
| V18 as designed | 2,724 g | 418 | -24.6 % | 49.6 % | STOP |
| V19-A long-nose falcon (wing 200 mm aft, nose-bay battery) | 2,719 g | 446 | -5.6 % | 25.7 % | STOP |
| V19-B falcon tail (0.15 m², wing 120 mm aft) | 2,913 g | 481 | -2.9 % | 25.2 % | STOP |
| V19-C forward rotors on booms (wing 275 mm aft) | 2,883 g | 479 | 7.7 % | 25.0 % | PASS |
| **V19-R recommended**: long nose + forward rotors + 0.05 m² falcon tail (wing 250 mm aft) | 3,006 g | 498 | 7.4 % | 26.3 % | **PASS** |

Gates: static margin 5-25 % of the mean chord, heaviest motor no more than 30 % of the weight in hover, pitch trim
within 10° at 16 m/s, no new collisions. V19-R keeps your rear rotors in the V18 wells, puts the front pair on
carbon booms with nose pods, closes the front wells, moves the battery into a nose bay and adds a small swept
tail on two fins above the EDF jet. Its print set, STLs, cut list and buy list are in
[`cad/v19/v19r_recommended/`](cad/v19/v19r_recommended/) and the V19 document.

## Quick start (Ubuntu / WSL2)

```bash
mkdir -p ~/src && cd ~/src && git clone git@github-normansrule:Normansrule/skyforge-v18-falcon.git
cd skyforge-v18-falcon
./scripts/setup_ubuntu.sh        # once: apt packages, .venv, Node packages (add --desktop for the app)
make serve                       # web app at http://localhost:8080
make help                        # everything else: check, budget, v18, v19, web, desktop, publish
```

Workflow: measure something, enter it in the web app's **Budget** or **Bench** tab (or `config/measurements.json`),
`make budget`, and buy only the next stage's rows. The **V19** tab switches the 3D model between V18 and the
variants (with an X-ray ghost of V18 for comparison) and lists every part that changes.

## What is here

| Path | What | Label |
|---|---|---|
| [`site/`](site/) | Web app: 3D model with picking, layers, explode, cut-away, control sweep, balance ruler, V18/V19 switcher; balance explorer; live budget; bench log ingest; wiring map; stage tracker; all docs. Offline-capable | PROTOTYPE-READY |
| [`desktop/`](desktop/) | Tauri v2 desktop shell around `site/` | PROTOTYPE-READY |
| [`cad/v18/`](cad/v18/) | Your V18 assembly, extracted part data, G10 cutting DXFs, carbon cut list, your original V18 BOM | source |
| [`cad/v19/`](cad/v19/), [`config/v19/`](config/v19/) | V19 variants: configurations, new and modified parts (STL, 3MF print sets for C and R, DXF), collision and fit checks, mass inputs | EXPERIMENTAL |
| [`cad/interface/`](cad/interface/) | Parametric parts for the joints V18 left open: crossing clamps, belly straps, EDF ear brackets, FC isolation pad, nose-steering collar | EXPERIMENTAL |
| [`bom/bom.csv`](bom/bom.csv) -> [`docs/BOM.md`](docs/BOM.md) | V18 BOM rows plus added rows, with links, stages, purchase gates and V18 placements | PROTOTYPE-READY |
| [`docs/V19_VARIANTS.md`](docs/V19_VARIANTS.md) | The three directions and their combination: numbers, changes, parts, checks, V19-R build changes | results |
| [`docs/BALANCE_AND_STABILITY.md`](docs/BALANCE_AND_STABILITY.md) | Why V18 does not balance | results |
| [`docs/BUDGET.md`](docs/BUDGET.md) | Running cost, mass, CG, hover and stability gates | generated |
| [`docs/WIRING.md`](docs/WIRING.md), [`docs/HARNESS.md`](docs/HARNESS.md) | Pin-by-pin wiring per module; harness cut list | PROTOTYPE-READY (bench) |
| [`docs/V18_CHECKS.md`](docs/V18_CHECKS.md) | Prop/well clearance, seams, control sweeps, gear, P1S fit | results |
| [`docs/TEST_GATES.md`](docs/TEST_GATES.md) | Stage 0-10 with PASS/FIX/STOP numbers | PROTOTYPE-READY |
| [`firmware/thrust_stand/`](firmware/thrust_stand/) | Arduino Nano + HX711 thrust-stand logger | PROTOTYPE-READY (compiles) |
| [`config/ardupilot/`](config/ardupilot/) | Bench-only ArduPilot port map | PROTOTYPE-READY (bench) |
| [`tools/`](tools/), [`tools/v19/`](tools/v19/) | Extraction, mass/CG, vortex lattice, geometry checks, balance study, V19 search/geometry/report, budget, harness, bench ingest, web export, repo checks | - |
| [`scripts/`](scripts/), [`Makefile`](Makefile) | One-command setup and publishing | - |

## Engineering rules this repo keeps

- V18 is the baseline and one 4S system throughout. Your V18 parts win over any candidate; V19 changes them only
  where a variant has to, and every change is listed.
- A printed nozzle is not propulsion, a decorative duct is not blade containment and printed skin is not the
  load path (V19 loads go through carbon booms and crossrails). Never print flight propellers.
- Failed and flagged checks are reported, not hidden (`make check` lists them).
- First flights happen with an experienced RC / QuadPlane pilot at a proper site, line-of-sight.

## Licence

No licence has been chosen yet; until one is added, all rights are reserved by the author. The vendored
libraries in `site/vendor/` keep their own licences (three.js MIT, marked MIT, fonts SIL OFL).
