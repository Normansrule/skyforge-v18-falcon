# Build status

Labels: **FINISHED** (verified on real parts) / **PROTOTYPE-READY** (ready for the stage's fit or bench
test) / **EXPERIMENTAL** (design proposal, unverified). Nothing is FINISHED yet.

## Decision

**V18 as designed does not balance** (model gates G1-G3 STOP, see
[docs/BALANCE_AND_STABILITY.md](docs/BALANCE_AND_STABILITY.md)): CG x418, 88 mm aft of the rotor centroid and
aft of the whole neutral-point band.

**Recommended: V19-W** ([docs/V19_VARIANTS.md](docs/V19_VARIANTS.md)):
- all four lift motors in your V18 wing wells, wing group 200 mm aft;
- 0.18 m2 falcon tail on the EDF outrigger booms;
- rear motors and main gear on short under-wing booms;
- nose-bay battery, pilot's-eye FPV camera under a clear canopy;
- the single V18 EDF as the cruise engine.

It passes every model gate with the masses of the parts as modelled (static margin 8.2 %, heaviest
motor 26.2 %) and has no new collisions in the full assembly. It is long: 1355 mm nose to tail
tip. V19-R and V19-C (front rotors on booms ahead of the wing) also pass and are the alternatives. The long nose alone
(V19-A) and the tail alone (V19-B) do not pass.

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
| V19 search + variant geometry (A, B, C, R, W) | EXPERIMENTAL | 64 configurations with as-built masses; full-assembly collision check against V18 |
| V19-W / V19-R / V19-C part files (STL, 3MF print set, DXF) | EXPERIMENTAL | Outer mould lines; unsliced; strength unproven |
| Web app (Pages, offline) | PROTOTYPE-READY | V18/V19 switcher, pilot view; tested in Chromium desktop + phone widths |
| Desktop app (Tauri) | PROTOTYPE-READY | Linux release build verified running; Windows/macOS built by CI on tag |

## Flagged (open)

| Finding | Action |
|---|---|
| CG / NP / rotor-centroid conflict | Resolved in the model by V19-W; confirm by weighing at Stage 9 |
| V19-W tail is large (0.18 m2, 759 mm span) and far aft; aircraft length 1355 mm | Accept, or use V19-R (0.05 m2 tail, front rotors on booms) |
| V19-W trims at 10 deg angle of attack at 16 m/s (7 deg at 20 m/s) | Transition and cruise at 18-20 m/s; confirm stall in glide tests |
| FPV through a vacuum-formed canopy | Check glare and distortion on the bench; matt-black seat and frame |
| V19 tail sits 80 mm above the wing plane to clear the EDF jet (estimate) | Tuft test on the EDF bench before gluing the tail |
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
