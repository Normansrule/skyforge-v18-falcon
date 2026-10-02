"""Parameters for the repo interface parts that fill V18 gaps (brief section 4).

Geometry anchors come from the V18 assembly (cad/v18/parts.json): tube sections and crossings,
outrigger positions, FC keep-out, nose leg wire. Values tagged MEASURE are placeholders that must
be replaced by a caliper measurement of the real part before cutting or printing anything but a
fit test.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# --- Fasteners ---
M3_CLEAR = 3.2
M3_NUT_AF = 5.5 + 0.25          # nut pocket across-flats incl. print clearance
M3_NUT_H = 2.4 + 0.2
M2_CLEAR = 2.3                  # MEASURE: replace with the Stage-0 coupon hole that slides

# --- Carbon (V18: CF_crossrail 10x10, CF_keel 8x8, CF_gear_crossbar 10x10, CF_EDF_outrigger 8x8) ---
CR = 10.0                       # crossrail / gear crossbar section (MEASURE actual)
KEEL = 8.0                      # keel / outrigger section (MEASURE actual)

# --- Crossing clamp plates (G10 2.0 mm), one above and one below each tube crossing ---
XC_T = 2.0
XC_EDGE = 1.5                   # material outside each hole (V18 tray strips sit 0.3 mm away)
XC_HOLE_GAP = 1.0               # hole edge to tube face
# V18 crossings: crossrails x240/x420 over keels y+/-24; gear crossbar x385 under keels
XC_SITES = [(240.0, 24.0, "rail_over_keel"), (240.0, -24.0, "rail_over_keel"),
            (420.0, 24.0, "rail_over_keel"), (420.0, -24.0, "rail_over_keel"),
            (385.0, 24.0, "keel_over_bar"), (385.0, -24.0, "keel_over_bar")]

# --- EDF ear clamp (PETG/PA-CF split clamp on the 8x8 outrigger, slotted tab toward the housing) ---
EDF_AXIS_X = 695.0              # bracket station: forward part of the V18 EDF housing span (671-749); the F4 skin closes in aft of ~x705
OUTRIGGER_Y = 54.0              # V18 CF_EDF_outrigger centre |y|
HOUSING_R = 36.0                # V18 keep-out radius (72 mm housing) - MEASURE the real E7206
SKIN_GAP_Y = 59.4               # V18 F4 inner skin |y| over x684-706 is >= 59.7 (outrigger outer face 58)
EAR_SLOT_LEN = 24.0             # slot along x so the bracket fits an unknown ear position
EAR_TAB_T = 4.0
CLAMP_LEN = 22.0                # along the tube
FLANGE_T = 3.0
WEB_T = 4.4
BELLY_STRAP_Z = -42.6           # external strap under the gear-crossbar crossings (belly skin ~ -40.5)

# --- FC isolation pad (TPU 95A) sized to the V18 FC keep-out 54 x 34 ---
FC_PAD_L = 52.0
FC_PAD_W = 32.0
FC_PAD_T = 3.0
FC_SLOT_X = (18.0, 24.0)        # FC hole half-spacing range (unconfirmed - slotted); MEASURE then narrow
FC_SLOT_Y = (9.0, 13.0)

# --- Nose steering collar (V18: 4 mm-class spring-steel nose leg at x~150) ---
NOSE_WIRE_D = 4.0               # MEASURE the leg wire
COLLAR_OD = 12.0
COLLAR_H = 10.0
ARM_LEN = 20.0
ARM_HOLES_R = (10.0, 13.0, 16.0)
PUSHROD_HOLE = 1.6
