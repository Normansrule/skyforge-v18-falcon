# Thrust stand (Stage 2) - Arduino Nano Classic + HX711

ESP-free on purpose. This keeps to the project's learning-hardware preference: Arduino Nano Classic, no ESP32.
It measures **one** lift motor + prop + ESC + flight battery and prints CSV that
`tools/ingest_bench.py` turns into the numbers the budget gates need. It compiles for the
ATmega328P at about 14.4 KB of flash (44 %) and 455 B of RAM. CI compiles it on every push.

## Wiring

| Nano pin | Connects to | Notes |
|---|---|---|
| 5V / GND | HX711 VCC / GND | power the Nano from USB |
| D2 | HX711 DT | |
| D3 | HX711 SCK | |
| D4 | Arm switch to GND | closed = armed; a latching toggle you can reach without leaning over the stand |
| D9 | ESC signal | |
| GND | ESC signal ground | the ESC BEC red wire is **not** connected |
| A0 | Current sensor output | Mauch HS-200-LV or ACS758 in the battery + lead. Set `CURR_V_PER_A`/`CURR_V_OFFSET` from its sheet |
| A1 | Divider mid-point | 47 k from battery +, 10 k to GND. 16.8 V reads as 2.95 V |
| A2 | NTC junction (optional) | 10 k B3950 NTC from 5V to A2, 10 k fixed resistor from A2 to GND; tape the NTC to the stator bell |
| D13 | LED | on while running |

Load cell: a 5 kg bar cell under a lever-free mount, so the motor pushes straight down or pulls straight up.
For Stage 2 the motor must sit on the real V18 G10 motor plate on a 10 x 10 carbon rail stub, because
that is what the prop sees in the aircraft.

## Guard and stand

- The prop guard must cover the full disc plus 20 mm, made of 6 mm plywood or polycarbonate. **Never** printed PLA alone.
- Clamp the stand to a heavy bench. Keep everyone out of the prop plane. Put the battery in a LiPo bag.
- Only fit the prop after a props-off spin-up and direction check.

## Procedure

1. Upload `thrust_stand.ino` (Arduino IDE: board "Arduino Nano", processor "ATmega328P"; Library Manager
   "HX711 Arduino Library" by Bogdan Necula).
2. Serial monitor at 115200, newline. `TARE`, then hang a known weight and send `CAL 500` (grams).
3. Check `STATUS` reads ~0 A, the battery voltage, and ~0 g.
4. Props off: close the arm switch, `PROFILE 10,20` and `RUN` to check direction and the abort keys.
5. Fit the prop and guard. `PROFILE 25,40,50,60,70,80,90,100`, `HOLD 12`, `LIMIT 45`, then `RUN`.
   Save the serial output as `logs/lift_<prop>_<date>.csv`.
6. `python3 tools/ingest_bench.py logs/lift_....csv --prop "APC B5x3E" --write`, then `python3 tools/budget.py`.
7. Repeat the 100 % step once to check repeatability. Repeat the whole run for the EDF (outside the
   airframe, inlet screened) and ingest it with `--edf`.

Any key, opening the arm switch, over-current or low voltage (3.3 V/cell) stops the motor immediately.
