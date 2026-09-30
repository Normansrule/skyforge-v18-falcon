# Build status

Labels: **FINISHED** (verified on real parts) / **PROTOTYPE-READY** (ready for the stage's fit or bench
test) / **EXPERIMENTAL** (design proposal, unverified). Nothing is FINISHED yet.

## Deliverables

| Item | Label | Basis |
|---|---|---|
| BOM with links, dims, gates, stages | PROTOTYPE-READY | Vendor pages checked 2026-09-30 for the rows marked (v); prices are allowances |
| Mass / cost / hover budget tool | PROTOTYPE-READY | Gate logic exercised on synthetic data in `tests/`; real inputs all `null` |
| Pin-by-pin wiring | PROTOTYPE-READY (props-off bench) | ArduPilot SpeedyBeeF405WING hwdef; module pinouts from vendor docs - verify silk |
| ArduPilot bench .param | PROTOTYPE-READY (bench) | Port map only |
| Motor pad + cross-clamps + cradles | EXPERIMENTAL | Hand stiffness estimate; Stage-3 proof test pending |
| EDF thrust plate | EXPERIMENTAL | EDF model and ear pattern unconfirmed |
| FC isolation carrier | EXPERIMENTAL | FC hole pattern unconfirmed (slotted) |
| Nose-steering collar | EXPERIMENTAL | Leg wire diameter unconfirmed |
| Layout reference assembly | reference | Planform is a proxy, not the V18 outline |
| V18 airframe templates | not in repo | Archives not yet added (`cad/v18_baseline/`) |

## Flagged checks (open)

| ID | Finding | Action |
|---|---|---|
| L5 | Main wheels at (385, +/-180) fall inside the rear-rotor well footprints in plan view | Attach legs inboard of \|y\| = 147.5; keep legs/wheels below the rotor wash; include them in thrust tests |
| L6 | Tip-back margin only 25 mm if the flight CG ends up near x360 | Check the 15 deg rule with the Stage-9 CG height; move the axle aft if needed |
| L7 | Beam + pad block ~10 % of each prop disc outside the motor footprint | Stage-2 bench runs with the beam and pad in place |
| MASS | Planning all-up 2.65 kg; hover PASS needs >= 1,543 g per motor at CG x345 | Stage-2 bench; reduce mass if FIX/STOP |
| POWER | Simultaneous lift + EDF current may approach the XT90 class | Stage-2 data -> budget gate |

## Unknowns that block purchases

- LW-PLA effective density (Stage 1).
- Lift motor thrust / current / temperature at loaded voltage with the real prop and mount (Stage 2).
- Which EDF the V18 saddle was drawn for; its OD and ear pattern.
- SpeedyBee F405 WING mounting-hole pattern (not confirmed from a reliable source).
- Mauch HS-200-LV output scaling (from its test sheet) and whether it stays <= 3.3 V at max current.
- Whether the owned 2.0 mm screws are M2 x 0.4 machine screws.
- Flight CG, neutral point and static margin (Stage 9 aero work - nothing carries over from old versions).
- Whether the no-ESP32 learning-link preference is meant to cover the aircraft's commercial ELRS link
  (the RP2 receiver uses an ESP8285).

## Supplier notes found while checking links (2026-09-30)

- Matek lists the M10Q-5883 GNSS/compass as end-of-life; buy remaining stock or an equivalent M10 + compass.
- The Hobbywing UBEC 10A (2-6S) page lists 5.0 / 6.0 / 7.4 / 8.4 V outputs; the 3-14S 10A variant starts at 6.0 V.
- The CNHL 3300 mAh 4S 40C pack is listed at 136 x 44 x 31 mm, 369 g, XT60, 12 AWG.
- The Freewing 64 mm 12-blade 4S unit lists 35 A max draw and a 35 A minimum ESC.
- The F405 WING PDB current sensor is 90 A continuous / 215 A peak; its ADC inputs are unscaled 3.3 V.
