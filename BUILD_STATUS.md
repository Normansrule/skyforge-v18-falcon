# Build status

Labels: **FINISHED** (verified on real parts) / **PROTOTYPE-READY** (ready for the stage's fit or bench
test) / **EXPERIMENTAL** (design proposal, unverified). Nothing is FINISHED yet.

## Decision

**V18 as designed does not balance** (model gates G1-G3 STOP, see
[docs/BALANCE_AND_STABILITY.md](docs/BALANCE_AND_STABILITY.md)): CG x418, 88 mm aft of the rotor centroid and
aft of the whole neutral-point band.

**Recommended: V19-F** ([docs/V19_VARIANTS.md](docs/V19_VARIANTS.md)), a VTOL that hovers balanced and flies stable
without a big boom tail:
- hover: all four lift motors in your V18 wing wells; the CG sits 0.2 mm from the centre of the four motors (each lifts
  24.9-25.1 % of the weight), set by sliding the battery 5 mm forward in your V18 tray;
- deep stoop: outer falcon panels and elevons swept 340 mm back at the wrist, one swept 10 x 10 carbon spar per wrist;
- slim falcon crest: 0.055 m2, 45 deg sweep, aspect ratio 8, on the tips of your V18 fins (6 deg leading edge down,
  30 % elevator, one slim servo);
- wing group 235 mm aft; rear motors and main gear on short under-wing booms; battery in the V18 tray (no nose bay);
- pilot's-eye FPV camera under a clear canopy; the single V18 EDF as the cruise engine.

It passes every model gate with the masses of the parts as modelled (static margin 7.5 %, heaviest motor 25.1 %,
pitch trim 0.1 / -7.5 deg at 16 m/s) and has no new collisions in the full assembly. It weighs 2,829 g and is
1,228 mm long. V19-S (300 mm stoop, 0.07 m2 crest) and V19-G (300 mm stoop, slim crest) are the same layout with a
different look and also pass; V19-W (0.18 m2 boom tail), V19-R and V19-C pass too. The long nose alone (V19-A) and the
tail alone (V19-B) do not pass.

Stages 0-2 (fit coupons, LW-PLA density, single-motor and EDF bench) are unchanged and come first: their
measurements replace the model assumptions V19 rests on.

## Deliverables

| Item | Label | Basis |
|---|---|---|
| V18 extraction (parts, P1S fit, G10 DXFs, carbon cut list) | PROTOTYPE-READY | Your V18 assembly; matches the brief's 35 templates / 42 pieces / ~1,297 cm3 |
| Mass + CG model | PROTOTYPE-READY | V18 positions + BOM masses; estimates flagged |
| Vortex-lattice aero model | PROTOTYPE-READY | Within 0.3 % of AeroSandbox on two reference wings; NP agrees within 1 mm on V18 |
| Balance study | PROTOTYPE-READY | 576 combinations; screening tool, not a flight clearance |
| Geometry checks (wells, seams, control sweeps, gear) | PROTOTYPE-READY | Both sides; hinge axes estimated |
| BOM (V18 rows + added rows) | PROTOTYPE-READY | V18 BOM carried forward; vendor pages checked 2026-09-30/10-01 for rows marked (v) |
| Budget with gates | PROTOTYPE-READY | Python and the web calculator agree (parity test) |
| Pin-by-pin wiring + harness cut list | PROTOTYPE-READY (props-off bench) | ArduPilot SpeedyBeeF405WING hwdef; V18 positions; verify silk |
| ArduPilot bench .param | PROTOTYPE-READY (bench) | Port map only |
| Interface parts | EXPERIMENTAL | All fit-checked inside V18; strength unproven |
| Thrust-stand firmware + ingest | PROTOTYPE-READY | Compiles for ATmega328P (44 % flash); synthetic-log tested |
| V19 search + variant geometry (A, B, C, R, W, S, G, F) | EXPERIMENTAL | 92 configurations with as-built masses; full-assembly collision check against V18 |
| V19-F / V19-S / V19-W / V19-R / V19-C part files (STL, 3MF print set, DXF) | EXPERIMENTAL | Outer mould lines; unsliced; strength unproven |
| Web app (Pages, offline) | PROTOTYPE-READY | V18/V19 switcher, pilot view; tested in Chromium desktop + phone widths |
| Desktop app (Tauri) | PROTOTYPE-READY | Linux release build verified running; Windows/macOS built by CI on tag |

## Flagged (open)

| Finding | Action |
|---|---|
| CG / NP / rotor-centroid conflict | Resolved in the model by V19-F (and S, G, W); confirm by weighing at Stage 9 |
| V19-F wrist: the swept outer panels hang on one 254 mm carbon spar per side (60 deg) plus the bonded overlap; strength unproven | Wrist load test (TEST_GATES.md V19-S additions) before any flight |
| V19-F trims at 13-16 deg angle of attack at 16 m/s (9-10.5 deg at 20 m/s); wells-open trim uses 7.5 of the 10 deg gate | Transition and cruise at 18-20 m/s; confirm stall in glide tests |
| V19-F hover balance rests on a 5 mm battery position (0.7 mm of CG per 5 mm of pack) | Weigh and mark the pack position at Stage 9; motor shares from the hover log |
| V19-F crest elevator on a slim 5 g servo; torque not checked against hinge moment | Bench: +/-20 deg throw under a 50 g tip load before gluing |
| FPV through a vacuum-formed canopy | Check glare and distortion on the bench; matt-black seat and frame |
| V19 tail / crest sits 75-80 mm above the wing plane to clear the EDF jet (estimate) | Tuft test on the EDF bench before gluing the tail or crest |
| V19-B: rear crossrail runs into the D1 intake | V19-B is not recommended |
| Flaps touch the D-panel trailing lip at neutral (both sides, y 229-247); 0.07 mm at +1 deg | Relieve ~0.8 mm |
| Seams cross all four well walls | Gauge the full opening; seam backer before motors |
| Main wheels inside the rear-well footprints | Gear in the thrust test, or legs inboard of y 147.5 |
| WRE1/WLE1 are 269.6-269.9 mm long | Print rotated ~29 deg (52.7 mm spare) |
| Elevons alone lack pitch authority (-13 to -18 deg trim even with a correct CG) | Use all four trailing-edge surfaces for pitch |
| Lift ESC sits front-left; motor leads run 292-524 mm | Extensions on all four motors (HARNESS.md) |
| EDF outriggers 1.4 mm from the F4 skin aft of x705 | Ear brackets at x695 only |

## Unknowns that block purchases

- LW-PLA effective density (Stage 1) and real lift-motor thrust/current/temperature (Stage 2).
- E7206 ear position; SpeedyBee F405 WING hole pattern; Mauch sensor scaling.
- Whether stopped props make the wells behave as open holes or closed surface (moves the NP by ~40 mm).
- Positions not in the V18 model: star point, current sensor, servo bus, airspeed sensor, buzzer,
  nose-steering servo.
- Whether the no-ESP32 preference covers the aircraft's commercial ELRS link (the RP1 V2 uses an ESP8285).
- Whether the owned 2.0 mm screws are M2 x 0.4 machine screws.
