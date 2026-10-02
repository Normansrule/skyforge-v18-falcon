// Parity test: site/js/budget.js (web calculator) must match tools/budget.py on the same inputs.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { compute, ingestBench } from '../site/js/budget.js';

const root = new URL('..', import.meta.url).pathname;
const j = (p) => JSON.parse(readFileSync(join(root, p), 'utf8'));
const inputs = { bom: j('site/data/bom.json'), model: j('site/data/mass_model.json'), aero: j('site/data/aero.json'), power: j('site/data/power.json') };

function python(measPath) {
  const out = mkdtempSync(join(tmpdir(), 'budget-'));
  execFileSync('python3', [join(root, 'tools/budget.py'), '--measurements', measPath, '--out', out], { stdio: 'ignore' });
  return JSON.parse(readFileSync(join(out, 'budget_summary.json'), 'utf8'));
}

const close = (a, b, label) => {
  if (a === null || b === null || a === undefined || b === undefined) return assert.equal(a ?? null, b ?? null, label);
  assert.ok(Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(b)), `${label}: js ${a} vs py ${b}`);
};

for (const meas of ['config/measurements.json', 'tests/synthetic_measurements.json']) {
  test(`budget parity on ${meas}`, () => {
    const py = python(join(root, meas));
    const js = compute(j(meas), inputs);
    close(js.all_up_g, py.all_up_g, 'all_up_g');
    for (let k = 0; k < 3; k++) close(js.cg_mm[k], py.cg_mm[k], `cg[${k}]`);
    for (const m of Object.keys(py.motor_hover_g)) close(js.motor_hover_g[m], py.motor_hover_g[m], `hover ${m}`);
    for (const b of ['aircraft', 'extras', 'contingency', 'from_scratch', 'remaining']) for (const i of [0, 1]) close(js.cost_usd[b][i], py.cost_usd[b][i], `cost ${b}`);
    close(js.static_margin_pct[0], py.static_margin_pct[0], 'sm fwd');
    close(js.static_margin_pct[1], py.static_margin_pct[1], 'sm aft');
    for (const i of [0, 1]) close(js.cg_window_x_mm[i], py.cg_window_x_mm[i], 'cg window');
    for (const k of ['PASS', 'FIX']) close(js.bench_max_thrust_needed_g[k], py.bench_max_thrust_needed_g[k], `bench ${k}`);
    close(js.mass_for_hover_pass_g, py.mass_for_hover_pass_g, 'mass for pass');
    close(js.hover_current_a, py.hover_current_a, 'hover current');
    close(js.worst_case_current_a, py.worst_case_current_a, 'worst current');
    py.gates.forEach((g, i) => { assert.equal(js.gates[i].status, g.status, `${g.id} status`); close(js.gates[i].value, g.value, `${g.id} value`); });
  });
}

test('bench ingest parity with tools/ingest_bench.py', () => {
  const log = readFileSync(join(root, 'tests/data/synthetic_bench_log.csv'), 'utf8');
  const js = ingestBench(log);
  const py = execFileSync('python3', [join(root, 'tools/ingest_bench.py'), join(root, 'tests/data/synthetic_bench_log.csv')]).toString();
  const lines = py.trim().split('\n').slice(1);
  assert.equal(js.length, lines.length);
  lines.forEach((ln, i) => {
    const [pct, thrust, amps, volts] = ln.trim().split(/\s+/).map(Number);
    assert.equal(js[i].throttle_pct, pct);
    close(js[i].thrust_g, thrust, 'thrust'); close(js[i].current_a, amps, 'current'); close(js[i].voltage_v, volts, 'voltage');
  });
});
