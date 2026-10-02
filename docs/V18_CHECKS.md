# V18 geometry checks

Run on your V18 assembly by `tools/v18_extract.py` and `tools/geom_checks.py`, on **both sides**.
Results: `cad/v18/parts.json` and `analysis/geom_checks.json`.

## Inventory (matches the brief)

| Item | V18 file | Brief |
|---|---|---|
| Objects in the assembly | 90 | - |
| Printed templates / installed pieces | 35 / 42 | 35 aircraft templates, 42 installed |
| Printed polymer volume | 1,292.4 cm³ | 1,297.2 cm³ (difference is tessellation) |
| G10 volume | 87.9 cm³ (15 flat plates + 2 outrigger fittings) | - |
| Carbon cut list | 10×10: 620 + 820 + 340 mm on 2 bars; 8×8: 2×420 + 2×174 mm on 2 bars | 2 + 2 one-metre tubes |

## P1S bed fit

Every printed part fits a 256 mm bed. `WRE1` and `WLE1` falcon wings are 269.6–269.9 mm long, longer than
the bed edge (the brief's "largest part 234.7 mm" does not include them). Placed rotated about 29°,
their footprint is 203 mm, with 52.7 mm to spare. Every part's best placement is in `cad/v18/parts.json`.

## C1 prop tip to well wall

| Motor | Wall radius | Tip clearance | Status |
|---|---|---|---|
| M1 front-right | 72.5 mm | 9.0 mm | PASS |
| M2 rear-left | 72.5 mm | 9.0 mm | PASS |
| M3 front-left | 72.5 mm | 9.0 mm | PASS |
| M4 rear-right | 72.5 mm | 9.0 mm | PASS |

Measured by sectioning every wing panel at the prop plane (z 24, 26 and 28 mm) for the 127 mm prop.

## C2 seams crossing wells (FLAG)

Every well wall is formed by two printed panels, so a seam crosses each opening. M1 is split between
WRA and WRB, M4 between WRB and WRC, and the left side mirrors this. Assemble with the 145 mm gauge
through the full opening and bond the seam with a backer before the motor goes in.

## C3 control-surface sweep, −25° to +25° in 1° steps (FLAG)

The hinge line is estimated from each surface's leading-edge nose radius, so confirm it against the
V18 hinge design.

| Surface | Result |
|---|---|
| ELEVON_R / ELEVON_L | Free over the whole range; tightest 1.89 mm at −25°. Symmetric. |
| FLAP_R / FLAP_L | **Interference at 0° and −1°** with WRD / WLD: the flap trailing-edge region (x ≈ 657, z ≈ 2.4) touches the D-panel trailing lip over y ≈ 229–247 mm, at 8 contact points each side. At +1° it clears by only 0.07 mm; by ±5° the clearance is 1.18 mm. Relieve the D-panel lip by about 0.8 mm (or trim the flap) so the flap does not bind at neutral. |

## C4 main wheels under the rear wells (FLAG)

The main wheels at (x385, y ±180) sit inside the rear-rotor well footprints (M2, M4) in plan view, about 40 mm
below the wing. They will be in the rotor wash in hover. Include the gear in the Stage-2 thrust
measurement, or move the legs inboard of |y| = 147.5 mm.

## Interface parts in place (repo parts)

Each repo interface part was placed at its V18 site and collision-tested against all 90 V18 objects:

| Part | Sites | Result |
|---|---|---|
| Crossing clamp plates (crossrails over keels) | 8 | PASS, 0.3 mm from the Tray A support strips |
| Crossing clamp plate (keels over gear crossbar) | 2 | PASS; no room under the crossbar, which runs through the belly skin |
| Belly strap (outside, under the gear crossings) | 2 | PASS, 2.2 mm |
| EDF ear bracket, upper and lower | 2 + 2 | PASS at x695, 0.6 mm from the F4 skin. The F4 skin closes in to the outrigger aft of x705, so nothing can clamp there |
| FC isolation pad | 1 | PASS, 1.25 mm |

## Naming note

The crossrails are named `CF_crossrail_270_…` and `CF_crossrail_450_…`, but in the V18 model they sit at x240 and
x420, directly under the motor rows. The repo uses the modelled positions; rename them in V19 if the names are meant to be stations.

## Not yet checked

- Pushrod, horn and wire clearance (no linkages in the V18 model).
- Cover removal paths and cable bend radii with real connectors (Stage 4).
- Swept volumes of the props and the EDF inlet flow path.
