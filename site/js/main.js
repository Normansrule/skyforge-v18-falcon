// Entry point: load data, build the viewer, route between tabs, keep the selected variant in sync.
import { compute } from './budget.js';
import { load } from './store.js';
import { drawRuler } from './ruler.js';
import { $$, esc, worst } from './util.js';
import * as views from './views.js';

const files = ['parts', 'bom', 'mass_model', 'mass_cg', 'aero', 'geom_checks', 'harness', 'balance_study', 'power', 'materials',
  'measurements', 'pinmap', 'carbon_cut_list', 'interface_parts', 'docs_index', 'stages', 'synthetic_measurements'];
const optional = ['variants'];

async function getData() {
  const get = async (f, must) => {
    const r = await fetch(`data/${f}.json`);
    if (!r.ok) { if (must) throw new Error(`data/${f}.json: ${r.status}`); return [f, null]; }
    return [f, await r.json()];
  };
  const entries = await Promise.all([...files.map((f) => get(f, true)), ...optional.map((f) => get(f, false))]);
  return Object.fromEntries(entries);
}

const ctx = {
  data: null, viewer: null, results: null, meas: null, balance: null, variant: null, ghost: false,
  els: { workbench: document.getElementById('workbench'), page: document.getElementById('page'), panel: document.getElementById('panel'), ruler: document.getElementById('ruler') },
  recompute() {
    const d = this.data;
    this.results = compute(this.meas, { bom: d.bom, model: d.mass_model, aero: d.aero, power: d.power });
    const s = worst(this.results.gates.slice(0, 3).map((g) => g.status));
    const pill = document.getElementById('status-pill');
    const rec = d.variants && d.variants.variants[d.variants.recommended];
    pill.innerHTML = `<span data-s="${s}">V18 ${s}</span>${rec ? `<span data-s="${rec.eval.passes ? 'PASS' : 'STOP'}">${esc(rec.short)} ${rec.eval.passes ? 'PASS' : 'STOP'}</span>` : ''}`;
    this.updateRuler();
  },
  updateRuler() {
    if (!this.results) return;
    const r = this.results;
    const v = this.variant && this.data.variants?.variants[this.variant];
    if (v) {
      const e = v.eval;
      const band = [e.np_closed_x_mm, e.np_open_x_mm];
      const win = [band[0] - 0.12 * e.mac_mm, band[0] - 0.05 * e.mac_mm];
      drawRuler(this.els.ruler, { cgX: e.cg_mm[0], rotorX: e.rotor_centroid_x_mm, rotorRows: [e.rotor_front_x_mm, e.rotor_rear_x_mm], npBand: band, window: win, length: Math.ceil(v.length_mm / 100) * 100 });
      this.viewer?.setMarkers({ cg: e.cg_mm, rotorX: e.rotor_centroid_x_mm, np: band });
      return;
    }
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
  setVariant(slug, { rerender = true } = {}) {
    const V = this.data.variants;
    if (!V || !V.variants[slug]) slug = null;
    if (slug === this.variant) return;
    this.variant = slug;
    this.viewer?.setVariant(slug);
    if (slug) this.balance = null;
    pills();
    this.updateRuler();
    if (rerender && (current === 'aircraft' || current === 'v19')) render(true);
  },
};

// ----- variant pills over the 3D view -----
function pills() {
  const host = document.getElementById('variant-pills');
  const V = ctx.data?.variants;
  if (!host || !V) return;
  host.hidden = current === 'balance';
  const items = [['', 'V18'], ...V.order.map((s) => [s, V.variants[s].short])];
  host.innerHTML = items.map(([s, label]) => {
    const on = (ctx.variant || '') === s;
    const ok = s ? V.variants[s].eval.passes : V.v18.passes;
    return `<button data-v="${esc(s)}" aria-pressed="${on}" title="${s ? esc(V.variants[s].label) : 'V18 as designed'}"><i class="dot ${ok ? 'ok' : 'no'}"></i>${esc(label)}</button>`;
  }).join('');
  $$(host, 'button').forEach((b) => b.addEventListener('click', () => {
    if (current === 'v19') location.hash = b.dataset.v ? `#v19/${b.dataset.v}` : '#v19/v18';
    else ctx.setVariant(b.dataset.v || null);
  }));
}

const PANEL_TABS = new Set(['aircraft', 'v19', 'balance']);
let current = null;
let currentSub = null;

function render(force = false) {
  const parts = location.hash.replace('#', '').split('/');
  const tab = parts[0] || 'aircraft';
  const TABS = ['aircraft', 'v19', 'balance', 'budget', 'bom', 'bench', 'wiring', 'stages', 'docs'];
  const name = TABS.includes(tab) ? tab : 'aircraft';
  const sub = parts.slice(1).join('/');
  for (const a of $$(document, '.tabs a')) { if (a.dataset.tab === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
  const wb = PANEL_TABS.has(name);
  ctx.els.workbench.hidden = !wb;
  ctx.els.page.hidden = wb;
  if (force || current !== name || currentSub !== sub || !wb) {
    if (current === 'balance' && name !== 'balance') { ctx.balance = null; ctx.viewer?.setShifts({ wing: 0, rotor: 0, battery: 0, avionics: 0 }); }
    if (name === 'balance' && ctx.variant) ctx.setVariant(null, { rerender: false });
    if (current === 'aircraft' && name !== 'aircraft' && ctx.viewer) { ctx.viewer.setExplode(0); ctx.viewer.setDeflection('FLAP', 0); ctx.viewer.setDeflection('ELEVON', 0); }
    const changed = current !== name;
    current = name;
    currentSub = sub;
    pills();
    views[name](ctx, wb ? ctx.els.panel : ctx.els.page, sub);
    if (changed && wb) ctx.els.panel.scrollTop = 0;
  }
  if (wb) { ctx.viewer?.resize(); ctx.updateRuler(); }
  if (!force) window.scrollTo(0, 0);
}

function intro() {
  const host = document.getElementById('intro');
  const V = ctx.data.variants;
  let seen = false;
  try { seen = localStorage.getItem('skyforge-intro-v3') === '1'; } catch { /* storage blocked */ }
  if (seen || !V || location.hash) return;
  const rec = V.variants[V.recommended];
  host.innerHTML = `
    <div class="intro-card" role="dialog" aria-modal="true" aria-labelledby="intro-h">
      <p class="eyebrow">SKYFORGE Falcon · build workbench</p>
      <h2 id="intro-h">Your V18, measured. And a V19 that balances.</h2>
      <p>V18 as designed sits ${Math.round(V.v18.cg_mm[0] - V.v18.rotor_centroid_x_mm)} mm tail-heavy of its rotors and behind its neutral point. <strong>${esc(rec.label)}</strong> (${esc(rec.summary.toLowerCase())}) passes every model gate with the parts as modelled.</p>
      <div class="row"><button class="btn primary" data-go="#v19/${esc(V.recommended)}">See ${esc(rec.short)}</button><button class="btn" data-go="#aircraft">Explore V18</button><button class="btn ghost" data-go="#docs/v19-variants">Read the plan</button></div>
    </div>`;
  host.hidden = false;
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  const close = (go) => {
    host.hidden = true;
    document.removeEventListener('keydown', onKey);
    try { localStorage.setItem('skyforge-intro-v3', '1'); } catch { /* storage blocked */ }
    if (go) location.hash = go;
  };
  $$(host, '[data-go]').forEach((b) => b.addEventListener('click', () => close(b.dataset.go)));
  host.addEventListener('click', (e) => { if (e.target === host) close(); });
  document.addEventListener('keydown', onKey);
  host.querySelector('button')?.focus();
}

async function start() {
  try {
    ctx.data = await getData();
  } catch (e) {
    ctx.els.panel.innerHTML = `<h2>Data did not load</h2><p>${e.message}. Serve the site folder over HTTP (for example <code>make serve</code>) rather than opening index.html as a file.</p>`;
    return;
  }
  ctx.meas = load('measurements', ctx.data.measurements);
  ctx.recompute();
  window.addEventListener('hashchange', () => render());
  render();
  intro();
  const bar = document.getElementById('load-bar');
  try {
    const { createViewer } = await import('./viewer.js');
    const hinges = {};
    for (const [k, v] of Object.entries(ctx.data.geom_checks.C3_control_sweep)) if (v && v.hinge_point_mm) hinges[k] = { point: v.hinge_point_mm, dir: v.hinge_dir };
    ctx.viewer = await createViewer(document.getElementById('three'), {
      parts: ctx.data.parts.parts, hinges, variants: ctx.data.variants?.variants ?? {},
      onPick: (name) => views.onPick?.(ctx, name),
      onProgress: (p) => { bar.style.setProperty('--p', p); },
    });
    window.__viewer = ctx.viewer;
    document.getElementById('viewport').classList.add('ready');
    document.dispatchEvent(new CustomEvent('viewer-ready'));
    if (ctx.variant) await ctx.viewer.setVariant(ctx.variant, { animate: false });
    ctx.updateRuler();
    window.addEventListener('resize', () => ctx.updateRuler());
    // warm the recommended variant so the first switch is instant
    const rec = ctx.data.variants?.recommended;
    if (rec) setTimeout(() => ctx.viewer.preload(rec), 1500);
  } catch (e) {
    document.getElementById('viewport').classList.add('ready');
    document.getElementById('viewport-hint').textContent = `3D view unavailable: ${e.message}. Everything else still works.`;
  }
}

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
start();
