"""Parameters for the SKYFORGE V18 interface parts and layout reference.

Every value tagged MEASURE is a placeholder that must be replaced by a caliper measurement of the
part you actually hold before the corresponding part is cut or printed for anything but a fit test.
Geometry values come from config/geometry.json (the V18 brief) so the two never drift apart.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEO = json.loads((ROOT / "config" / "geometry.json").read_text())

# --- V18 layout (from the brief) ---
MOTORS = {k: (v["x"], v["y"]) for k, v in GEO["lift_motors"].items()}
PROP_D = GEO["prop_diameter_mm"]            # 127
WELL_D = GEO["rotor_opening_mm"]            # 145
EDGE_GAP = GEO["rotor_edge_gap_mm"]         # 35
LENGTH = GEO["length_mm"]                   # 810
SPAN = GEO["span_mm"]                       # 1000
SERVO_X = GEO["outer_servo_centers"]["x"]
SERVO_Y = GEO["outer_servo_centers"]["y_abs"]
MAIN_TRACK = GEO["main_wheel_track_mm"]
GEAR_X = GEO["gear_crossbar_x_mm"]
NOSE_X = GEO["nose_axle_x_mm"]
CENTROID_X = GEO["equal_thrust_centroid_x_mm"]

# --- Candidate spar stations bracketing the wells (EXPERIMENTAL - set to the real V18 rail positions) ---
SPAR_X = (150.0, 330.0, 510.0)   # front spar in the LE gap, mid spar in the 35 mm web, rear spar in the TE gap
SPAR_W = 10.0                    # 10 x 10 carbon (S01); MEASURE actual outside size
SPAR_H = 10.0
SPAR_HALF_SPAN = 300.0           # layout only

# --- Fasteners ---
M3_CLEAR = 3.2
M3_NUT_AF = 5.5 + 0.25           # nut pocket across-flats incl. print clearance; tune from Stage-0 coupon
M3_NUT_H = 2.4 + 0.2
M2_CLEAR = 2.3                   # MEASURE: replace with the Stage-0 coupon hole that slides

# --- Motor mount (G10 2.5 mm pad on an 8 x 8 carbon motor beam) ---
# Load path: motor -> G10 pad -> 8x8 carbon beam across the well (fore/aft) -> G10 cross-clamps -> 10x10 spars.
# A flat 2.5 mm G10 bridge over the same 180 mm span was rejected: flatwise it deflects ~3.8 mm at a
# 1.2 kg static thrust (E~18 GPa, I=21 mm^4) versus ~0.1 mm for an 8x8x1 pultruded tube.
G10_THICK_MB = 2.5               # imperial substitute 2.38 mm (3/32 in) -> change here
MOTOR_PATTERN = 16.0             # EMAX ECO II 2207: 16 x 16 M3 (vendor) - MEASURE
MOTOR_RELIEF_D = 9.0             # shaft/clip relief - MEASURE on P01 (clearance to beam top = pad thickness)
MOTOR_FOOT_D = 28.0              # motor base footprint for blockage accounting - MEASURE
HUB_D = 34.0
PAD_TAB_L = 50.0                 # along the beam (X)
PAD_TAB_W = 22.0
PAD_CLAMP_X = 20.0               # clamp bolts at x = +/-20, straddling the beam in Y
BEAM_W = 8.0                     # 8 x 8 carbon (S02); MEASURE
BEAM_H = 8.0
BEAM_SPAN = 180.0                # spar centre to spar centre across one well (150->330, 330->510)
BEAM_OVERHANG = 13.0             # past each spar centre
XCLAMP_T = 2.5                   # G10 cross-clamp plates, two per crossing

# --- Rail clamp cradle (printed PETG/PA prototype under the carbon; the G10 above carries the load) ---
CRADLE_LEN = 20.0
CRADLE_WALL = 3.2
CRADLE_FLOOR = 3.0
CRADLE_PRELOAD = 0.5             # channel is this much shallower than the tube -> clamp squeeze
PAD_POCKET = 0.8                 # recess for a rubber/cork compression pad

# --- FC isolation carrier (TPU 95A) ---
FC_CARRIER_L = 62.0
FC_CARRIER_W = 42.0
FC_CARRIER_T = 3.0
# FC hole pattern is NOT confirmed from a reliable source -> slots cover a range; MEASURE and narrow later
FC_SLOT_X = (18.0, 24.0)         # half-spacing range along the board length
FC_SLOT_Y = (9.0, 13.0)          # half-spacing range across the board

# --- EDF thrust plate (G10 2.0 mm), ears drilled to the measured unit ---
G10_THICK_EDF = 2.0
EDF_FAN_ID = 64.0
EDF_HOUSING_OD = 70.0            # MEASURE - placeholder
EDF_PLATE_W = 120.0
EDF_PLATE_H = 84.0
EDF_RAIL_HALF = 50.0             # rail-clamp holes either side; MEASURE vs V18 EDF_saddle rails

# --- Nose steering collar (printed PETG test piece) ---
NOSE_WIRE_D = 4.0                # MEASURE the leg wire
COLLAR_OD = 12.0
COLLAR_H = 10.0
ARM_LEN = 20.0
ARM_HOLES_R = (10.0, 13.0, 16.0)
PUSHROD_HOLE = 1.6
