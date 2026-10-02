// SKYFORGE V18 - Stage-2 guarded thrust stand logger (ESP-free: Arduino Nano Classic, ATmega328P)
//
// Measures one lift motor + prop + ESC + flight battery on a GUARDED stand and prints CSV:
//   t_ms,phase,throttle_pct,pwm_us,thrust_g,current_a,voltage_v,temp_c
// Feed the log to:  python3 tools/ingest_bench.py log.csv --write
//
// Hardware (see firmware/thrust_stand/README.md for the full wiring table)
//   HX711 DT -> D2, SCK -> D3, VCC -> 5V, GND -> GND   (5 kg load cell under the motor mount)
//   ESC signal -> D9, ESC signal ground -> GND            (ESC BEC red wire NOT connected)
//   ARM switch -> D4 to GND (closed = armed), LED on D13 shows armed
//   Current: Mauch HS-200-LV / ACS758 output -> A0 (0-5 V; set CURR_* below from the sensor sheet)
//   Battery voltage: divider 47k (top) / 10k (bottom) from battery + -> A1
//   Motor temperature: 10k NTC (B3950) to 5V, 10k fixed resistor to GND, junction -> A2 (optional)
//
// Safety model: throttle is 1000 us (stop) unless BOTH the arm switch is closed AND the operator
// typed RUN. Any byte received, opening the switch, over-current or low voltage stops the motor
// immediately and ends the run. Props on only with the guard in place and nobody in the prop plane.
//
// Serial commands (115200 baud, newline-terminated):
//   TARE            zero the load cell (props off, motor still)
//   CAL <grams>     calibrate with a known weight on the cell, e.g. CAL 500
//   RUN             run the step profile below (needs the arm switch closed)
//   PROFILE a,b,c   set step throttles in percent, e.g. PROFILE 25,40,50,60,70,80,90,100
//   HOLD <s>        seconds per step (default 12; the ingest tool averages the last 5 s)
//   LIMIT <A>       over-current abort (default 45 A per motor)
//   STATUS          print calibration and live readings

#include <EEPROM.h>
#include <HX711.h>   // "HX711 Arduino Library" by Bogdan Necula (Library Manager)
#include <Servo.h>

const uint8_t PIN_DT = 2, PIN_SCK = 3, PIN_ARM = 4, PIN_ESC = 9, PIN_LED = 13;
const uint8_t PIN_CURR = A0, PIN_VBAT = A1, PIN_NTC = A2;

// --- sensor scaling: EDIT to match your parts ---
float CURR_V_PER_A = 0.0165f;    // volts per amp of the current sensor (Mauch sheet / ACS758-200U: 0.020)
float CURR_V_OFFSET = 0.0f;      // sensor output at 0 A (Mauch ~0 V, ACS758 unidirectional ~0.6 V)
const float VDIV_RATIO = (47.0f + 10.0f) / 10.0f;
const float ADC_REF = 5.0f;      // measure the Nano's 5V pin and put the real value here
const float LOW_V_PER_CELL = 3.3f;
const uint8_t CELLS = 4;

HX711 scale;
Servo esc;

struct Cal { uint32_t magic; float scale; long offset; };
Cal cal = {0x5F18B001UL, 420.0f, 0};

uint8_t profile[16] = {25, 40, 50, 60, 70, 80, 90, 100};
uint8_t nsteps = 8;
uint16_t hold_s = 12;
float limit_a = 45.0f;

float readVolts(uint8_t pin, uint8_t n = 8) {
  long acc = 0;
  for (uint8_t i = 0; i < n; i++) acc += analogRead(pin);
  return (acc / (float)n) * ADC_REF / 1023.0f;
}
float currentA() { return (readVolts(PIN_CURR) - CURR_V_OFFSET) / CURR_V_PER_A; }
float batteryV() { return readVolts(PIN_VBAT) * VDIV_RATIO; }
float tempC() {
  float v = readVolts(PIN_NTC, 4);
  if (v < 0.05f || v > ADC_REF - 0.05f) return NAN;          // not fitted
  float r = 10000.0f * (ADC_REF - v) / v;                    // NTC on the 5V side, 10k fixed to GND (as wired above)
  float t = 1.0f / (1.0f / 298.15f + log(r / 10000.0f) / 3950.0f);
  return t - 273.15f;
}
bool armed() { return digitalRead(PIN_ARM) == LOW; }
void stopMotor() { esc.writeMicroseconds(1000); }

void saveCal() { EEPROM.put(0, cal); }
void loadCal() {
  Cal c; EEPROM.get(0, c);
  if (c.magic == cal.magic) cal = c;
  scale.set_scale(cal.scale); scale.set_offset(cal.offset);
}

void printRow(const char *phase, uint8_t pct, uint16_t us) {
  float t = tempC();
  Serial.print(millis()); Serial.print(',');
  Serial.print(phase); Serial.print(',');
  Serial.print(pct); Serial.print(',');
  Serial.print(us); Serial.print(',');
  Serial.print(scale.is_ready() ? scale.get_units(1) : NAN, 1); Serial.print(',');
  Serial.print(currentA(), 2); Serial.print(',');
  Serial.print(batteryV(), 3); Serial.print(',');
  if (isnan(t)) Serial.println(""); else Serial.println(t, 1);
}

bool abortCheck(const char **why) {
  if (Serial.available()) { *why = "operator"; return true; }
  if (!armed()) { *why = "arm switch opened"; return true; }
  if (currentA() > limit_a) { *why = "over-current"; return true; }
  if (batteryV() < LOW_V_PER_CELL * CELLS) { *why = "low battery voltage"; return true; }
  return false;
}

void runProfile() {
  if (!armed()) { Serial.println(F("# REFUSED: close the arm switch first")); return; }
  Serial.println(F("# RUN starts in 5 s - send any key to abort"));
  for (uint8_t i = 0; i < 50; i++) { delay(100); if (Serial.available()) { while (Serial.available()) Serial.read(); Serial.println(F("# aborted")); return; } }
  Serial.println(F("t_ms,phase,throttle_pct,pwm_us,thrust_g,current_a,voltage_v,temp_c"));
  digitalWrite(PIN_LED, HIGH);
  const char *why = nullptr;
  for (uint8_t s = 0; s < nsteps && !why; s++) {
    uint8_t pct = profile[s];
    uint16_t us = 1000 + 10 * pct;
    // 1.5 s ramp to the step so the stand does not jerk
    uint16_t from = (s == 0) ? 1000 : 1000 + 10 * profile[s - 1];
    for (uint8_t k = 1; k <= 15 && !why; k++) {
      esc.writeMicroseconds(from + (long)(us - from) * k / 15);
      delay(100);
      abortCheck(&why);
    }
    unsigned long t0 = millis();
    while (!why && millis() - t0 < hold_s * 1000UL) {
      esc.writeMicroseconds(us);
      printRow("step", pct, us);
      abortCheck(&why);
      delay(100);
    }
  }
  stopMotor();
  digitalWrite(PIN_LED, LOW);
  unsigned long t0 = millis();
  while (millis() - t0 < 3000) { printRow("cooldown", 0, 1000); delay(250); }
  Serial.print(F("# END ")); Serial.println(why ? why : "complete");
  while (Serial.available()) Serial.read();
}

void handle(String line) {
  line.trim();
  if (line == "TARE") { scale.tare(20); cal.offset = scale.get_offset(); saveCal(); Serial.println(F("# tared")); }
  else if (line.startsWith("CAL ")) {
    float grams = line.substring(4).toFloat();
    if (grams <= 0) { Serial.println(F("# CAL needs grams > 0")); return; }
    scale.set_scale(1.0f);
    float raw = scale.get_units(20);
    cal.scale = raw / grams; scale.set_scale(cal.scale); saveCal();
    Serial.print(F("# scale=")); Serial.println(cal.scale, 4);
  } else if (line == "RUN") runProfile();
  else if (line.startsWith("PROFILE ")) {
    String p = line.substring(8); nsteps = 0;
    while (p.length() && nsteps < 16) {
      int c = p.indexOf(',');
      int v = (c < 0 ? p : p.substring(0, c)).toInt();
      if (v >= 0 && v <= 100) profile[nsteps++] = v;
      p = c < 0 ? "" : p.substring(c + 1);
    }
    Serial.print(F("# steps=")); Serial.println(nsteps);
  } else if (line.startsWith("HOLD ")) { hold_s = max(6, line.substring(5).toInt()); Serial.print(F("# hold_s=")); Serial.println(hold_s); }
  else if (line.startsWith("LIMIT ")) { limit_a = line.substring(6).toFloat(); Serial.print(F("# limit_a=")); Serial.println(limit_a); }
  else if (line == "STATUS") {
    Serial.print(F("# scale=")); Serial.print(cal.scale, 4);
    Serial.print(F(" armed=")); Serial.print(armed());
    Serial.print(F(" thrust_g=")); Serial.print(scale.get_units(5), 1);
    Serial.print(F(" current_a=")); Serial.print(currentA(), 2);
    Serial.print(F(" voltage_v=")); Serial.println(batteryV(), 3);
  } else if (line.length()) Serial.println(F("# commands: TARE | CAL g | RUN | PROFILE a,b,.. | HOLD s | LIMIT A | STATUS"));
}

void setup() {
  pinMode(PIN_ARM, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  esc.attach(PIN_ESC, 1000, 2000);
  stopMotor();                       // ESC sees "stop" from power-up
  Serial.begin(115200);
  scale.begin(PIN_DT, PIN_SCK);
  loadCal();
  Serial.println(F("# SKYFORGE V18 thrust stand ready. Props OFF until the guard is on. Type STATUS."));
}

void loop() {
  stopMotor();
  if (Serial.available()) handle(Serial.readStringUntil('\n'));
}
