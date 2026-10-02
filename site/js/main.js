// Entry point: load data, build the viewer, route between tabs.
import { compute } from './budget.js';
import { load } from './store.js';
import { drawRuler } from './ruler.js';
import { $$, worst } from './util.js';
import * as views from './views.js';

const files = ['parts', 'bom', 'mass_model', 'mass_cg', 'aero', 'geom_checks', 'harness', 'balance_study', 'power', 'materials',
  'measurements', 'pinmap', 'carbon_cut_list', 'interface_parts', 'docs_index', 'stages', 'synthetic_measurements'];

async function getData() {
  const entries = await Promise.all(files.map(async (f) => {
    const r = await fetch(`data/${f}.json`);
    if (!r.ok) throw new Error(`data/${f}.json: ${r.status}`);
    return [f, await r.json()];
  }));
  return Object.fromEntries(entries);
}

const ctx = {
  data: null, viewer: null, results: null, meas: null, balance: null,
  els: { workbench: document.getElementById('workbench'), page: document.getElementById('page'), panel: document.getElementById('panel'), ruler: document.getElementById('ruler') },
  recompute() {
    const d = this.data;
    this.results = compute(this.meas, { bom: d.bom, model: d.mass_model, aero: d.aero, power: d.power });
    const s = worst(this.results.gates.slice(0, 3).map((g) => g.status));
    const pill = document.getElementById('status-pill');
    pill.textContent = `Model gates: ${s}`;
    pill.dataset.s = s;
    this.updateRuler();
  },
  updateRuler() {
    if (!this.results) return;
    const r = this.results;
    const b = this.balance;
    const band = b ? [b.np_closed_x_mm, b.np_open_x_mm] : [Math.min(...Object.values(r.neutral_point_band_x_mm)), Math.max(...Object.values(r.neutral_point_band_x_mm))];
    const cgX = b ? b.cg_x_mm : r.cg_mm[0];
    const rotorX = b ? b.rotor_centroid_x_mm : r.rotor_centroid_x_mm;
    const shift = b ? b.dw_mm + b.dr_mm : 0;
    const mac = r.mac_mm;
    const win = [band[0] - 0.12 * mac, band[0] - 0.05 * mac];
    drawRuler(this.els.ruler, { cgX, rotorX, rotorRows: [240 + shift, 420 + shift], npBand: band, window: win });
    this.viewer?.setMarkers({ cg: b ? [cgX, 0, 0] : r.cg_mm, rotorX, np: band });
  },
};

const PANEL_TABS = new Set(['aircraft', 'balance']);
let current = null;

function route() {
  const tab = (location.hash.replace('#', '').split('/')[0]) || 'aircraft';
  const name = views[tab] ? tab : 'aircraft';
  for (const a of $$(document, '.tabs a')) { if (a.dataset.tab === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
  const wb = PANEL_TABS.has(name);
  ctx.els.workbench.hidden = !wb;
  ctx.els.page.hidden = wb;
  if (current !== name || !wb) {
    if (current === 'balance' && name !== 'balance') { ctx.balance = null; ctx.viewer?.setShifts({ wing: 0, rotor: 0, battery: 0, avionics: 0 }); }
    current = name;
    views[name](ctx, wb ? ctx.els.panel : ctx.els.page, location.hash.split('/').slice(1).join('/'));
  }
  if (wb) { ctx.viewer?.resize(); ctx.updateRuler(); }
  window.scrollTo(0, 0);
}

async function start() {
  try {
    ctx.data = await getData();
  } catch (e) {
    ctx.els.panel.innerHTML = `<h2>Data did not load</h2><p>${e.message}. Serve the site folder over HTTP (for example <code>npm run serve</code>) rather than opening index.html as a file.</p>`;
    return;
  }
  ctx.meas = load('measurements', ctx.data.measurements);
  ctx.recompute();
  window.addEventListener('hashchange', route);
  route();
  try {
    const { createViewer } = await import('./viewer.js');
    const hinges = {};
    for (const [k, v] of Object.entries(ctx.data.geom_checks.C3_control_sweep)) if (v && v.hinge_point_mm) hinges[k] = { point: v.hinge_point_mm, dir: v.hinge_dir };
    ctx.viewer = await createViewer(document.getElementById('three'), {
      parts: ctx.data.parts.parts, hinges,
      onPick: (name) => views.onPick?.(ctx, name),
    });
    document.dispatchEvent(new CustomEvent('viewer-ready'));
    ctx.updateRuler();
    window.addEventListener('resize', () => ctx.updateRuler());
  } catch (e) {
    document.getElementById('viewport-hint').textContent = `3D view unavailable: ${e.message}. Everything else still works.`;
  }
}

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
start();
