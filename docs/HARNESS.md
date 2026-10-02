# Harness cut list (generated from V18 positions)

> `python3 tools/harness.py`. Lengths include 15 % slack and 25 mm per end. Positions come from the V18 keep-out boxes and
> motor envelopes; the star point, servo bus, current sensor, airspeed sensor, buzzer and steering servo are assumed
> (they are not in the V18 model) - see `analysis/harness.json`. Currents are planning values; re-size after Stage 2.

| Run | From -> To | Cond. | AWG | Length each (mm) | Plan A | Drop V | Loss W | Note |
|---|---|---|---|---|---|---|---|---|
| Battery lead to sensor | battery -> sensor | 2 | 10 | 142 | 120 | 0.112 | 13.41 | battery XT90 pigtail; + through the hall sensor |
| Sensor to star | sensor -> star | 1 | 10 | 53 | 120 | 0.021 | 2.52 | + only; - goes straight to the star |
| Star to 4-in-1 (branch A) | star -> lift_esc | 2 | 10 | 120 | 100 | 0.079 | 7.88 | cap E07 #1 at the ESC pads |
| Star to EDF ESC (branch B) | star -> edf_esc | 2 | 12 | 341 | 60 | 0.213 | 12.79 | XT60; cap E07 #2 at the ESC |
| Star to FC PDB (branch C, fused) | star -> fc | 2 | 18 | 297 | 5 | 0.062 | 0.31 | fuse E08 near the star |
| Star to UBEC (branch D) | star -> ubec | 2 | 18 | 122 | 5 | 0.026 | 0.13 |  |
| 4-in-1 to M1 (FR) | lift_esc -> M1 | 3 | 18 | 349 | 30 | 0.438 | 13.13 | motor stock leads are short: extension + 3.5 mm bullets |
| 4-in-1 to M2 (RL) | lift_esc -> M2 | 3 | 18 | 466 | 30 | 0.585 | 17.54 |  |
| 4-in-1 to M3 (FL) | lift_esc -> M3 | 3 | 18 | 292 | 30 | 0.366 | 10.97 |  |
| 4-in-1 to M4 (RR) | lift_esc -> M4 | 3 | 18 | 524 | 30 | 0.657 | 19.71 |  |
| EDF ESC to EDF motor | edf_esc -> edf | 3 | 14 | 254 | 40 | 0.168 | 6.73 | 3.5 mm bullets; route clear of the fan inlet |
| FC S1-S4 + GND to 4-in-1 | fc -> lift_esc | 5 | 26 | 328 | 0.1 | 0.004 | 0.00 | signal ribbon |
| FC S11 + GND to EDF ESC | fc -> edf_esc | 2 | 26 | 133 | 0.1 | 0.002 | 0.00 | BEC red lead isolated |
| FC S5-S9 + GND to servo bus | fc -> servo_bus | 6 | 26 | 375 | 0.1 | 0.005 | 0.00 |  |
| UBEC to servo bus | ubec -> servo_bus | 2 | 20 | 63 | 4 | 0.017 | 0.07 |  |
| Servo bus to right flap servo | servo_bus -> servo_flap_R | 3 | 22 | 623 | 1 | 0.033 | 0.03 | servo extension |
| Servo bus to left flap servo | servo_bus -> servo_flap_L | 3 | 22 | 685 | 1 | 0.036 | 0.04 |  |
| Servo bus to right elevon servo | servo_bus -> servo_elevon_R | 3 | 22 | 785 | 1 | 0.042 | 0.04 |  |
| Servo bus to left elevon servo | servo_bus -> servo_elevon_L | 3 | 22 | 847 | 1 | 0.045 | 0.04 |  |
| Servo bus to nose-steering servo | servo_bus -> servo_steer | 3 | 22 | 180 | 1 | 0.010 | 0.01 | servo position assumed |
| FC to receiver | fc -> rx | 4 | 26 | 447 | 0.2 | 0.012 | 0.00 | 5V GND TX RX |
| FC to GNSS/compass | fc -> gps | 6 | 26 | 600 | 0.2 | 0.016 | 0.00 | 5V GND TX RX SDA SCL |
| FC to airspeed | fc -> airspeed | 4 | 26 | 493 | 0.1 | 0.007 | 0.00 | I2C; position assumed |
| FC to current sensor | fc -> sensor | 3 | 26 | 301 | 0.1 | 0.004 | 0.00 | VCC, CURR, GND |
| FC to buzzer | fc -> buzzer | 2 | 26 | 142 | 0.1 | 0.002 | 0.00 | position assumed |
| Video rail to VTX | fc -> vtx | 2 | 22 | 110 | 0.5 | 0.003 | 0.00 | 5.0 V measured |
| Video rail + signal to camera | fc -> camera | 3 | 26 | 547 | 0.3 | 0.022 | 0.01 | 5 V, GND, VIDEO |
| Camera video to VTX | camera -> vtx | 2 | 26 | 568 | 0 | 0.000 | 0.00 | shielded or twisted with GND |

## Wire to buy (with 25 % spare)

| AWG | Metres |
|---|---|
| 10 | 0.7 |
| 12 | 0.9 |
| 14 | 1.0 |
| 18 | 7.2 |
| 20 | 0.2 |
| 22 | 12.0 |
| 26 | 19.3 |

Buy red and black separately for 10/12 AWG power runs; motor phase extensions in three colours help keep order.
Every lift-motor run is longer than typical 2207 stock leads, so all four need extensions (or a motor variant with long leads).
