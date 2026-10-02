#!/usr/bin/env python3
"""Harness cut list from V18 component positions.

    python3 tools/harness.py      # docs/HARNESS.md + analysis/harness.json

Each run is routed orthogonally (along x down the body keels, then along y out the crossrails or
wing, plus any z change), then 15 % slack and 25 mm per termination are added. Positions are the
centroids of the V18 keep-out boxes / purchased-part envelopes; `xyz:` positions are assumptions
for parts the V18 model does not place. Gauges are starting points; currents are planning values
until the Stage-2 bench measures them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import v18geom as g  # noqa: E402

SLACK = 1.15
TERM = 25.0
# copper resistance, ohm per metre (annealed copper, 20 C)
OHM_PER_M = {10: 0.00328, 12: 0.00521, 14: 0.00829, 16: 0.0132, 18: 0.0209, 20: 0.0333, 22: 0.0530, 26: 0.134}

NODES = {
    "battery": "KEEP_OUT_BATTERY_MAX_140x50x38",
    "lift_esc": "KEEP_OUT_LIFT_ESC_54x46x14",
    "ubec": "KEEP_OUT_SERVO_BEC_48x38x16",
    "fc": "KEEP_OUT_FC_54x34x24",
    "edf_esc": "KEEP_OUT_EDF_ESC_73x30x12_plus_margin",
    "edf": "KEEP_OUT_EDF_72mm_HOUSING_KEEP_OUT",
    "vtx": "KEEP_OUT_VTX_42x26x14",
    "camera": "KEEP_OUT_CAMERA_19mm",
    "rx": "KEEP_OUT_RX_antenna_free_zone",
    "gps": "KEEP_OUT_GPS_mount_EXTERNAL_TBD",
    "M1": "PURCHASE_M1_2207_envelope", "M2": "PURCHASE_M2_2207_envelope",
    "M3": "PURCHASE_M3_2207_envelope", "M4": "PURCHASE_M4_2207_envelope",
    "servo_flap_R": "SP1_side_servo_cassette_PRINT4_180", "servo_flap_L": "SP1_side_servo_cassette_PRINT4_-180",
    "servo_elevon_R": "SP1_side_servo_cassette_PRINT4_360.222222222",
    "servo_elevon_L": "SP1_side_servo_cassette_PRINT4_-360.222222222",
}
ASSUMED = {"star": (288.0, 0.0, 8.0), "sensor": (287.0, 0.0, 10.0), "servo_bus": (255.0, 27.0, 16.0),
           "airspeed": (130.0, 0.0, 20.0), "buzzer": (520.0, 25.0, 12.0), "servo_steer": (200.0, 0.0, -15.0)}

# (run, from, to, conductors, AWG, planning current A, note)
RUNS = [
    ("Battery lead to sensor", "battery", "sensor", 2, 10, 120, "battery XT90 pigtail; + through the hall sensor"),
    ("Sensor to star", "sensor", "star", 1, 10, 120, "+ only; - goes straight to the star"),
    ("Star to 4-in-1 (branch A)", "star", "lift_esc", 2, 10, 100, "cap E07 #1 at the ESC pads"),
    ("Star to EDF ESC (branch B)", "star", "edf_esc", 2, 12, 60, "XT60; cap E07 #2 at the ESC"),
    ("Star to FC PDB (branch C, fused)", "star", "fc", 2, 18, 5, "fuse E08 near the star"),
    ("Star to UBEC (branch D)", "star", "ubec", 2, 18, 5, ""),
    ("4-in-1 to M1 (FR)", "lift_esc", "M1", 3, 18, 30, "motor stock leads are short: extension + 3.5 mm bullets"),
    ("4-in-1 to M2 (RL)", "lift_esc", "M2", 3, 18, 30, ""),
    ("4-in-1 to M3 (FL)", "lift_esc", "M3", 3, 18, 30, ""),
    ("4-in-1 to M4 (RR)", "lift_esc", "M4", 3, 18, 30, ""),
    ("EDF ESC to EDF motor", "edf_esc", "edf", 3, 14, 40, "3.5 mm bullets; route clear of the fan inlet"),
    ("FC S1-S4 + GND to 4-in-1", "fc", "lift_esc", 5, 26, 0.1, "signal ribbon"),
    ("FC S11 + GND to EDF ESC", "fc", "edf_esc", 2, 26, 0.1, "BEC red lead isolated"),
    ("FC S5-S9 + GND to servo bus", "fc", "servo_bus", 6, 26, 0.1, ""),
    ("UBEC to servo bus", "ubec", "servo_bus", 2, 20, 4, ""),
    ("Servo bus to right flap servo", "servo_bus", "servo_flap_R", 3, 22, 1, "servo extension"),
    ("Servo bus to left flap servo", "servo_bus", "servo_flap_L", 3, 22, 1, ""),
    ("Servo bus to right elevon servo", "servo_bus", "servo_elevon_R", 3, 22, 1, ""),
    ("Servo bus to left elevon servo", "servo_bus", "servo_elevon_L", 3, 22, 1, ""),
    ("Servo bus to nose-steering servo", "servo_bus", "servo_steer", 3, 22, 1, "servo position assumed"),
    ("FC to receiver", "fc", "rx", 4, 26, 0.2, "5V GND TX RX"),
    ("FC to GNSS/compass", "fc", "gps", 6, 26, 0.2, "5V GND TX RX SDA SCL"),
    ("FC to airspeed", "fc", "airspeed", 4, 26, 0.1, "I2C; position assumed"),
    ("FC to current sensor", "fc", "sensor", 3, 26, 0.1, "VCC, CURR, GND"),
    ("FC to buzzer", "fc", "buzzer", 2, 26, 0.1, "position assumed"),
    ("Video rail to VTX", "fc", "vtx", 2, 22, 0.5, "5.0 V measured"),
    ("Video rail + signal to camera", "fc", "camera", 3, 26, 0.3, "5 V, GND, VIDEO"),
    ("Camera video to VTX", "camera", "vtx", 2, 26, 0.0, "shielded or twisted with GND"),
]


def pos(node: str, pbn) -> np.ndarray:
    if node in ASSUMED:
        return np.array(ASSUMED[node])
    v = pbn[NODES[node]].vertices
    return (v.min(0) + v.max(0)) / 2


def route_len(a, b):
    """Down the body in x at |y| <= 30, then out in y, plus z."""
    ya, yb = a[1], b[1]
    inner = min(abs(ya), 30.0) * np.sign(ya), min(abs(yb), 30.0) * np.sign(yb)
    return abs(a[0] - b[0]) + abs(ya - inner[0]) + abs(inner[0] - inner[1]) + abs(yb - inner[1]) + abs(a[2] - b[2])


def main() -> int:
    pbn = g.by_name()
    rows, per_gauge = [], {}
    for name, a, b, n, awg, amps, note in RUNS:
        L = route_len(pos(a, pbn), pos(b, pbn)) * SLACK + 2 * TERM
        drop = amps * OHM_PER_M[awg] * L / 1000 * (2 if n >= 2 and amps > 1 else 1)
        rows.append({"run": name, "from": a, "to": b, "conductors": n, "awg": awg, "length_each_mm": round(L),
                     "planning_current_a": amps, "voltage_drop_v": round(drop, 3), "loss_w": round(drop * amps, 2), "note": note})
        per_gauge[awg] = per_gauge.get(awg, 0) + n * L
    nodes = {n: [round(float(v), 1) for v in pos(n, pbn)] for n in set(list(NODES) + list(ASSUMED))}
    out = {"_note": __doc__.strip(), "assumed_positions": ASSUMED, "nodes": nodes, "runs": rows,
           "wire_per_gauge_m": {str(k): round(v / 1000, 2) for k, v in sorted(per_gauge.items())},
           "buy_per_gauge_m_with_25pct_spare": {str(k): round(v / 1000 * 1.25, 1) for k, v in sorted(per_gauge.items())}}
    (g.ROOT / "analysis" / "harness.json").write_text(json.dumps(out, indent=1))
    L = ["# Harness cut list (generated from V18 positions)", "",
         "> `python3 tools/harness.py`. Lengths include 15 % slack and 25 mm per end. Positions come from the V18 keep-out boxes and",
         "> motor envelopes; the star point, servo bus, current sensor, airspeed sensor, buzzer and steering servo are assumed",
         "> (they are not in the V18 model) - see `analysis/harness.json`. Currents are planning values; re-size after Stage 2.", "",
         "| Run | From -> To | Cond. | AWG | Length each (mm) | Plan A | Drop V | Loss W | Note |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['run']} | {r['from']} -> {r['to']} | {r['conductors']} | {r['awg']} | {r['length_each_mm']} | "
                 f"{r['planning_current_a']:g} | {r['voltage_drop_v']:.3f} | {r['loss_w']:.2f} | {r['note']} |")
    L += ["", "## Wire to buy (with 25 % spare)", "", "| AWG | Metres |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in out["buy_per_gauge_m_with_25pct_spare"].items()]
    L += ["", "Buy red and black separately for 10/12 AWG power runs; motor phase extensions in three colours help keep order.",
          "Every lift-motor run is longer than typical 2207 stock leads, so all four need extensions (or a motor variant with long leads).", ""]
    (g.ROOT / "docs" / "HARNESS.md").write_text("\n".join(L))
    print(json.dumps(out["buy_per_gauge_m_with_25pct_spare"]))
    for r in rows[:11]:
        print(r["run"], r["length_each_mm"], "mm", r["voltage_drop_v"], "V")
    return 0


if __name__ == "__main__":
    sys.exit(main())
