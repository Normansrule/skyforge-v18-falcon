# Staged build and test gates

Each stage lists: files + quantities, buy-now list, steps, measurements, PASS / FIX / STOP, and
what NOT to buy yet. Stages 0-2 are detailed because they gate every bulk purchase and bulk print.
Stages 3-10 follow the master brief; their numeric gates are set when Stage 2 data exists.

Record every measurement in `config/measurements.json`, then run `python3 tools/budget.py`.

---

## Stage 0 - fit coupons and templates

**Print (P1S, PLA or PETG, 0.2 mm, no supports)**

| File | Qty | Source |
|---|---|---|
| `TEST_M2_hole_coupon` | 1 | V18 archive (`cad/v18_baseline/`) |
| `TEST_145mm_rotor_gauge` | 1 | V18 archive |
| `SF_G10_drill_templates_PLA` | 1 | this repo, `cad/out/3mf/` |

**Buy now:** F01 (M2 kit), C05 (filament), X01 calipers, X02 scales, X10 soldering station if not owned.
**Do not buy yet:** motors, ESCs, EDF, FC, servos beyond A07, carbon, G10.

| Measurement | PASS | FIX | STOP |
|---|---|---|---|
| Smallest coupon hole an M2 x 0.4 screw slides through without threading | 2.2-2.4 mm hole; enter it as `M2_CLEAR` in `cad/src/params.py` | Slides only at >= 2.5 mm: calibrate flow / hole compensation and reprint | - |
| M2 nut pocket | Nut presses in by thumb, stays put upside-down, no cracking | Loose or cracking: adjust pocket AF by +/-0.1 mm and reprint | - |
| Owned "2.0 mm" screws | Thread cleanly into a plain M2 x 0.4 nut for >= 3 turns | - | Self-tapping or wrong pitch: do not use in nut pockets; buy F01 |
| Rotor gauge diameter | 145.0 +/- 0.3 mm on two perpendicular axes | 0.3-0.6 mm off: scale compensation, reprint | > 0.6 mm: printer calibration first |
| Drill template holes vs 16 x 16 pattern | 16.0 +/- 0.15 mm centre-to-centre | Reprint after XY compensation | - |

---

## Stage 1 - first functional prints and real LW-PLA mass

**Print (production LW-PLA profile where the V18 manifest calls for it)**

| File | Qty |
|---|---|
| `CAM_19mm_cradle` | 1 |
| `SP1_side_servo_cassette` | 1 |
| `SC1_servo_access_cover` | 1 |
| `WRE2_falcon_wing` (sample) | 1 - counts as the installed right E2 only if it passes; do not print a second one "for the build" |

**Buy now:** A07 (one servo), V01 (camera), C02 (CA).
**Do not buy yet:** A08 servos #2-5, anything propulsion.

| Measurement | How | PASS | FIX | STOP |
|---|---|---|---|---|
| LW-PLA effective density | E2 mass (0.1 g scale) / slicer-reported extruded volume (cm3) -> `stage1.lwpla_effective_density_g_cm3` | <= 0.80 g/cm3 | 0.80-1.00: tune foaming temperature/flow, reprint | > 1.00: the all-up mass plan is invalid - re-run the budget and redesign before Stage 2 buys |
| E2 surface/strength | Visual + thumb press at mid-panel | No delamination, no soft spots | Raise temperature 5 C / add a wall | Layers split by hand |
| Servo in SP1 | Insert A07, close SC1 | No force fit; horn clears through the full V18 range -25..+25 deg **plus 5 deg** each side | Adjust pocket, reprint | Servo body or tabs do not fit - servo substitute needs dimensional AND torque check |
| Camera FOV | Phoenix 2 in the cradle, live image | Horizon visible at level; cockpit frame <= 10% of the image | Shim / re-angle cradle | - |
| Cable path | Camera + servo leads routed with real connectors | Bend radius >= 3 x cable diameter, no pinch at cover | Enlarge channel | - |

---

## Stage 2 - guarded single-motor and EDF bench (the gate for all propulsion spending)

**Buy now:** P01 (one motor), P03 (spare), P04 + P05 props, P06 (4-in-1, use one channel), E01 battery,
E02 current sensor, E05-E07 connectors/wire/caps, X03-X07 (meter, watt meter, stand, servo tester,
charger) as needed. P07/P08 EDF + ESC may be bought here **only** if their fit to the V18 saddle was
confirmed from dimensions; otherwise wait for Stage 5.
**Do not buy yet:** P02 (motors #2-4), FC, servos, carbon, G10, bulk filament for wings/body.

**Rig**

- Motor on a mock of the real mount: a 180 mm length of 8 x 8 carbon (or aluminium of the same width)
  with the G10 motor pad, so the thrust figure includes the beam + pad blockage (layout check L7).
- Load cell (X05) under the mount, prop guard around the full disc, stand clamped to a heavy bench.
  Nobody in the prop plane. Battery in a LiPo bag, EDF unplugged.
- Inline watt meter (X04) **and** E02 in series so E02 is calibrated at the same time.
- Servo tester (X06) drives the ESC. Props only after a props-off spin-up and direction check.

**Procedure:** 25, 40, 50, 60, 70, 80, 90, 100 % throttle; hold each >= 10 s after settling; log thrust (g),
current (A), loaded battery voltage (V), and motor + ESC temperature after 60 s at the step closest to
the hover thrust from `docs/BUDGET.md`. Enter the rows into `stage2.thrust_table`,
`max_static_thrust_g_loaded`, `max_current_a`. Repeat the top step once to check repeatability.

Then the EDF, separately, outside the airframe, inlet screened, same logging: `edf_max_current_a`,
`edf_max_thrust_g`.

| Gate | PASS | FIX | STOP |
|---|---|---|---|
| Worst-motor hover fraction (computed by `tools/budget.py` from the thrust table, mass and CG) | <= 0.50 | 0.50-0.60: reduce mass (target shown in BUDGET.md), change prop, or move the CG forward, then re-bench | > 0.60: do not buy P02 or bulk-print; redesign (mass, prop size, or motor) |
| Hover endurance (computed) | >= 2.0 min at 80 % usable | 1.0-2.0 min | < 1.0 min |
| Loaded voltage at 100 % | >= 3.5 V/cell (14.0 V) | 3.3-3.5 V/cell: higher-C pack or shorter leads | < 3.3 V/cell |
| Motor temperature after 60 s at hover throttle | <= 70 C | 70-85 C | > 85 C or any smell/discolouration |
| ESC temperature, same step | <= 80 C | 80-95 C | > 95 C or thermal cut |
| E02 vs watt meter at ~5 A, ~20 A and max | within 5 % | 5-10 %: recalibrate BATT_AMP_PERVLT/OFFSET | > 10 % or output > 3.3 V at max: change sensor or add a divider |
| Transition peak current (computed: lift at 1.3 x hover + EDF max) | <= main connector class and <= 70 % of the pack's label C | Re-terminate XT90/10 AWG, higher-C pack | Exceeds XT90 class: cap currents (Q_M_BAT_CURR_MAX) and re-plan the power system |
| Vibration | No audible buzz, stand not walking, prop balanced | Re-balance prop / tighten mount | Mount loosens during a run |

---

## Stages 3-10 (summary; numeric gates set after Stage 2)

| Stage | Build / check | Key PASS criteria | Do not do yet |
|---|---|---|---|
| 3 Structure | 10x10 spars at the V18 rail stations, 8x8 motor beams, G10 pads + cross-clamps (`SF_MP`, `SF_XC`), cradles (`SF_RC8`), real gear, **no printed skin** | Each crossing and motor clamp holds 3x the Stage-2 max thrust without slip (hang weights); gear drop from 10 cm with ballast at planned mass, no permanent set; nose steering moves freely | Wing shells |
| 4 Trays and covers | TRAY_A/B, H1/H2 with real battery, FC, harness | Battery pull test 3 g equivalent (hang 3x pack mass from the strap) with no movement; cover removal without unplugging; connector bend radius | - |
| 5 EDF dry-fit | EDF_saddle x2, D1, D2, `SF_EDF_thrust_plate` drilled to the measured ears; EDF power disconnected | Blade tip clearance uniform to +/-0.3 mm by feeler; thrust path is plate -> 8x8 rails, not printed saddle | Powered EDF runs inside the body before this passes |
| 6 Wings | One wing, then its mirror; 145 mm gauge through every well including seams that cross wells | Gauge passes all four wells; left/right mass within 3 %; seams flush; rail fit without force | - |
| 7 Controls | Hinges, flaps, elevons, fins, all 5 servos | Free motion over full range + 5 deg margin, both sides; correcting directions; no horn/pushrod/wire contact at any deflection | - |
| 8 Electrical | `docs/WIRING.md` section 12 order, props OFF | Every rail measured; no brownout with all servos + motors; motor test A-D order and direction correct; video clean | Props on |
| 9 Weigh + CG | Whole aircraft; flight CG from aero work (neutral point, static margin) - **not** x330 | Hover gate re-run with measured mass and CG still PASS; simultaneous current measured; failsafes configured | Flight |
| 10 Flight qualification | With an experienced RC / QuadPlane pilot at a proper site: taxi -> hover -> wing-borne -> transitions, as separate sessions | Each session's own plan; first flight line-of-sight, not immersive FPV | Decoration before final reweigh/rebalance |
