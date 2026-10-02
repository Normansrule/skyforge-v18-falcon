// SKYFORGE V18 budget arithmetic for the browser - a line-for-line port of tools/budget.py `compute`.
// tests/test_budget_parity.mjs runs both on the same inputs and fails CI if they disagree.
// Pure module: no DOM access, so it runs in Node too.

export function interp(table, xKey, yKey, x) {
  const pts = table.map((p) => [Number(p[xKey]), Number(p[yKey])]).sort((a, b) => a[0] - b[0]);
  if (!pts.length) return null;
  if (x <= pts[0][0]) return pts[0][0] ? (pts[0][1] * x) / pts[0][0] : pts[0][1];
  for (let i = 0; i + 1 < pts.length; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    if (x0 <= x && x <= x1) return y0 + ((y1 - y0) * (x - x0)) / (x1 - x0);
  }
  return null; // never extrapolate beyond the measured range
}

export function gate(v, { passMax, fixMax, passMin, fixMin }) {
  if (v === null || v === undefined || Number.isNaN(v)) return 'UNKNOWN';
  if (passMax !== undefined) return v <= passMax ? 'PASS' : v <= fixMax ? 'FIX' : 'STOP';
  return v >= passMin ? 'PASS' : v >= fixMin ? 'FIX' : 'STOP';
}

function solve3(M, b) {
  const m = M.map((r) => r.slice());
  const v = b.slice();
  for (let c = 0; c < 3; c++) {
    let p = c;
    for (let r = c + 1; r < 3; r++) if (Math.abs(m[r][c]) > Math.abs(m[p][c])) p = r;
    [m[c], m[p]] = [m[p], m[c]];
    [v[c], v[p]] = [v[p], v[c]];
    for (let r = 0; r < 3; r++) {
      if (r === c) continue;
      const f = m[r][c] / m[c][c];
      for (let k = 0; k < 3; k++) m[r][k] -= f * m[c][k];
      v[r] -= f * v[c];
    }
  }
  return v.map((x, i) => x / m[i][i]);
}

/** Minimum-norm thrusts that balance weight and both moments about the CG. */
export function hoverSplit(total, cg, motors) {
  const names = Object.keys(motors);
  const xs = names.map((n) => motors[n][0] - cg[0]);
  const ys = names.map((n) => motors[n][1] - cg[1]);
  const A = [[1, 1, 1, 1], xs, ys];
  const AAt = [0, 1, 2].map((i) => [0, 1, 2].map((j) => A[i].reduce((s, _, k) => s + A[i][k] * A[j][k], 0)));
  const lam = solve3(AAt, [total, 0, 0]);
  return Object.fromEntries(names.map((n, k) => [n, lam[0] * A[0][k] + lam[1] * A[1][k] + lam[2] * A[2][k]]));
}

/** All-up mass (g) and CG (mm) for an LW-PLA density and measured component masses. */
export function massState(model, lwDensity, measuredG = {}) {
  let M = 0;
  const mom = [0, 0, 0];
  const units = model.bom_unit_g;
  for (const it of model.items) {
    let m = it.g;
    if (measuredG[it.id] !== null && measuredG[it.id] !== undefined && units[it.id]) m *= Number(measuredG[it.id]) / units[it.id];
    M += m;
    for (let k = 0; k < 3; k++) mom[k] += m * it.xyz[k];
  }
  for (const [mat, e] of Object.entries(model.polymer)) {
    const d = mat === 'LW-PLA' ? lwDensity : model.densities_g_cm3[mat];
    M += e.volume_cm3 * d;
    for (let k = 0; k < 3; k++) mom[k] += e.moment_cm3_mm[k] * d;
  }
  return { M, cg: mom.map((x) => x / M) };
}

export function compute(meas, { bom, model, aero, power }) {
  const g = power.gates;
  const owned = new Set(meas?.owned_items?.ids ?? []);
  const measuredG = meas?.component_masses_g?.values ?? {};
  const aircraft = bom.filter((r) => r.group !== 'Extras' && r.stage !== 'ALT');
  const extras = bom.filter((r) => r.group === 'Extras');
  const sum = (rows, k) => rows.reduce((s, r) => s + r[k], 0);
  const cost = { aircraft: [sum(aircraft, 'row_usd_low'), sum(aircraft, 'row_usd_high')], extras: [sum(extras, 'row_usd_low'), sum(extras, 'row_usd_high')] };
  cost.contingency = [0.15 * cost.aircraft[0], 0.2 * cost.aircraft[1]];
  cost.from_scratch = [0, 1].map((i) => cost.aircraft[i] + cost.contingency[i] + cost.extras[i]);
  const notOwned = [...aircraft, ...extras].filter((r) => !owned.has(r.id));
  cost.remaining = [sum(notOwned, 'row_usd_low') + cost.contingency[0], sum(notOwned, 'row_usd_high') + cost.contingency[1]];

  const rhoMeas = meas?.stage1?.lwpla_effective_density_g_cm3;
  let lwCases = { ...model.lwpla_cases };
  if (rhoMeas) lwCases = { measured: rhoMeas, ...lwCases };
  const cases = {};
  for (const [name, d] of Object.entries(lwCases)) {
    const s = massState(model, d, measuredG);
    cases[name] = { lwpla: d, all_up_g: s.M, cg_mm: s.cg };
  }
  const design = rhoMeas ? 'measured' : 'planning';
  let M = cases[design].all_up_g;
  let cg = cases[design].cg_mm.slice();
  const s9 = meas?.stage9 ?? {};
  let basis = `MODEL (${design} LW-PLA ${lwCases[design].toFixed(2)})`;
  if (s9.all_up_mass_g) { M = Number(s9.all_up_mass_g); basis = 'MEASURED mass'; }
  if (s9.flight_cg_x_mm !== null && s9.flight_cg_x_mm !== undefined) {
    cg = [Number(s9.flight_cg_x_mm), Number(s9.flight_cg_y_mm || 0), cg[2]];
    basis += ' + MEASURED CG';
  }
  const motors = model.motor_xy_mm;
  const loads = hoverSplit(M, cg, motors);
  const worstName = Object.keys(loads).reduce((a, b) => (loads[b] > loads[a] ? b : a));
  const worst = loads[worstName];
  const rotorCx = Object.values(motors).reduce((s, v) => s + v[0], 0) / 4;

  const s2 = meas?.stage2 ?? {};
  const tmax = s2.max_static_thrust_g_loaded;
  const table = s2.thrust_table ?? [];
  const hoverFrac = tmax ? worst / tmax : null;
  let hoverCurrent = null;
  if (table.length) {
    const cur = Object.values(loads).map((t) => interp(table, 'thrust_g', 'current_a', Math.max(t, 0)));
    if (cur.every((c) => c !== null)) hoverCurrent = cur.reduce((a, b) => a + b, 0) + power.avionics_video_servo_avg_current_a;
  }
  const capAh = (power.battery_capacity_mah / 1000) * power.usable_capacity_fraction;
  const hoverMin = hoverCurrent ? (capAh / hoverCurrent) * 60 : null;
  const massForPass = tmax ? (M * (g.hover_fraction_pass_max * tmax)) / worst : null;

  let peak = s9.simultaneous_lift_plus_edf_peak_a ?? null;
  let worstAll = null;
  if (s2.max_current_a && s2.edf_max_current_a) worstAll = 4 * s2.max_current_a + s2.edf_max_current_a + power.avionics_video_servo_avg_current_a;
  let peakBasis;
  if (peak !== null) peakBasis = 'MEASURED';
  else if (table.length && s2.edf_max_current_a && tmax) {
    const per = Object.values(loads).map((t) => interp(table, 'thrust_g', 'current_a', Math.min(1.3 * Math.max(t, 0), tmax)));
    peak = per.every((p) => p !== null) ? per.reduce((a, b) => a + b, 0) + s2.edf_max_current_a + power.avionics_video_servo_avg_current_a : null;
    peakBasis = 'estimated transition: lift at 1.3 x hover + EDF max + avionics';
  } else peakBasis = 'UNKNOWN until Stage 2';
  const connA = power.connector_class_continuous_a[power.main_connector];
  const battLabelA = (power.battery_capacity_mah / 1000) * power.battery_c_rating_continuous_label;

  const band = aero.neutral_point_band_x_mm;
  const mac = aero.planform.mac_m * 1000;
  const npFwd = Math.min(...Object.values(band));
  const npAft = Math.max(...Object.values(band));
  const smFwd = (npFwd - cg[0]) / mac;
  const smAft = (npAft - cg[0]) / mac;
  const off = Math.abs(cg[0] - rotorCx);
  const gates = [
    { id: 'G1', gate: 'Hover balance: |CG x - rotor centroid x|', value: off, unit: 'mm', status: gate(off, { passMax: g.cg_offset_pass_mm, fixMax: g.cg_offset_fix_mm }), basis },
    { id: 'G2', gate: `Worst motor share of weight (${worstName})`, value: (100 * worst) / M, unit: '%', status: gate((100 * worst) / M, { passMax: g.worst_share_pass_pct, fixMax: g.worst_share_fix_pct }), basis },
    { id: 'G3', gate: 'Static margin, most forward neutral point', value: 100 * smFwd, unit: '% MAC', status: gate(100 * smFwd, { passMin: g.static_margin_pass_pct, fixMin: g.static_margin_fix_pct }), basis: `${basis}; NP band x${npFwd.toFixed(0)}-${npAft.toFixed(0)}` },
    { id: 'G4', gate: 'Worst-motor hover fraction of measured max thrust', value: hoverFrac, unit: '', status: gate(hoverFrac, { passMax: g.hover_fraction_pass_max, fixMax: g.hover_fraction_fix_max }), basis: 'Stage-2 bench' },
    { id: 'G5', gate: `Hover endurance at ${Math.round(power.usable_capacity_fraction * 100)}% of ${power.battery_capacity_mah} mAh`, value: hoverMin, unit: 'min', status: gate(hoverMin, { passMin: g.hover_minutes_pass_min, fixMin: g.hover_minutes_fix_min }), basis: 'Stage-2 thrust table' },
    { id: 'G6', gate: `Transition peak current vs ${power.main_connector} class ${connA} A`, value: peak, unit: 'A', status: peak ? (peak <= connA ? 'PASS' : 'STOP') : 'UNKNOWN', basis: peakBasis },
    { id: 'G7', gate: `Transition peak vs 70 % of battery label (${battLabelA.toFixed(0)} A)`, value: peak, unit: 'A', status: peak ? (peak <= 0.7 * battLabelA ? 'PASS' : 'FIX') : 'UNKNOWN', basis: peakBasis },
  ];
  return {
    cost_usd: cost, mass_cases: cases, design_case: design, all_up_g: M, cg_mm: cg, basis,
    rotor_centroid_x_mm: rotorCx, motor_hover_g: loads, worst_motor: worstName,
    bench_max_thrust_needed_g: { PASS: worst / g.hover_fraction_pass_max, FIX: worst / g.hover_fraction_fix_max },
    mass_for_hover_pass_g: massForPass, hover_current_a: hoverCurrent, worst_case_current_a: worstAll,
    neutral_point_band_x_mm: band, mac_mm: mac, static_margin_pct: [100 * smFwd, 100 * smAft],
    cg_window_x_mm: [npFwd - (g.static_margin_target_pct / 100) * mac, npFwd - (g.static_margin_pass_pct / 100) * mac],
    gates,
  };
}

/** Parse a thrust-stand CSV log - port of tools/ingest_bench.py. */
export function ingestBench(text, settle = 5) {
  const rows = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim() || line.startsWith('#') || line.startsWith('t_ms')) continue;
    const r = line.split(',');
    if (r.length < 7 || r[1] !== 'step') continue;
    const v = { t: Number(r[0]) / 1000, pct: parseInt(r[2], 10), thrust: Number(r[4]), current: Number(r[5]), voltage: Number(r[6]), temp: r[7] ? Number(r[7]) : null };
    if ([v.t, v.pct, v.thrust, v.current, v.voltage].some(Number.isNaN)) continue;
    rows.push(v);
  }
  const by = new Map();
  for (const r of rows) { if (!by.has(r.pct)) by.set(r.pct, []); by.get(r.pct).push(r); }
  const out = [];
  for (const pct of [...by.keys()].sort((a, b) => a - b)) {
    const rs = by.get(pct);
    const tEnd = Math.max(...rs.map((r) => r.t));
    const tail = rs.filter((r) => r.t >= tEnd - settle);
    if (tail.length < 3) continue;
    const avg = (k) => tail.reduce((s, r) => s + r[k], 0) / tail.length;
    const temps = rs.map((r) => r.temp).filter((t) => t !== null && !Number.isNaN(t));
    out.push({ throttle_pct: pct, thrust_g: Math.round(avg('thrust') * 10) / 10, current_a: Math.round(avg('current') * 100) / 100,
      voltage_v: Math.round(avg('voltage') * 1000) / 1000, motor_temp_c_max: temps.length ? Math.round(Math.max(...temps) * 10) / 10 : null });
  }
  return out;
}
