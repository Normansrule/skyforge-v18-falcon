// The eight views. Panel views (aircraft, balance) render beside the 3D model; the rest are pages.
import { ingestBench } from './budget.js';
import { save, clear, download } from './store.js';
import { esc, fmt, usd, badge, html, $, $$ } from './util.js';

const LAYERS = [
  ['skin', 'Skin', '#929BA5'], ['controls', 'Controls', '#26313D'], ['fittings', 'Trays', '#343C44'],
  ['structure', 'Carbon + G10', '#B3BCC7'], ['hardware', 'Motors + gear', '#171B20'], ['props', 'Props', '#171B20'],
  ['keepouts', 'Envelopes', '#E5A34E'], ['repo', 'Repo parts', '#2E8C6B'],
];
const layerState = Object.fromEntries(LAYERS.map(([k]) => [k, true]));
let pickedName = null;

function whenViewer(ctx, fn) {
  if (ctx.viewer) fn(ctx.viewer);
  else document.addEventListener('viewer-ready', () => fn(ctx.viewer), { once: true });
}

// ------------------------------------------------------------------------------------------------
export function aircraft(ctx, el) {
  const r = ctx.results;
  const d = ctx.data;
  const [g1, g2, g3] = r.gates;
  const band = Object.values(r.neutral_point_band_x_mm);
  const sweep = d.geom_checks.C3_control_sweep;
  const wells = d.geom_checks.C1_C2_wells;
  const minTip = Math.min(...Object.values(wells).map((w) => w.tip_clearance_mm));
  html(el, `
    <h2>Where V18 balances today</h2>
    <dl class="readout">
      <dt>All-up mass</dt><dd>${fmt(r.all_up_g)} g</dd>
      <dt>Centre of gravity</dt><dd>x ${fmt(r.cg_mm[0])} mm</dd>
      <dt>Rotor centroid</dt><dd>x ${fmt(r.rotor_centroid_x_mm)} mm</dd>
      <dt>Neutral point</dt><dd>x ${fmt(Math.min(...band))} to ${fmt(Math.max(...band))} mm</dd>
    </dl>
    <div class="finding">
      <p>${badge(g1.status)} The CG sits ${fmt(g1.value)} mm aft of the rotor centroid, so in hover the rear motors carry ${fmt(g2.value, 1)} % of the weight each and the front pair almost nothing.</p>
      <p>${badge(g3.status)} For wing-borne flight the CG must be ahead of the neutral point; it is ${fmt(-r.static_margin_pct[0], 1)} % of the mean chord behind it.</p>
      <p><a href="#balance">Try the balance study</a> to see which changes move the CG where it needs to be.</p>
    </div>
    <p class="small muted">Model values from your V18 geometry and the BOM (${esc(r.basis)}). Enter measurements in <a href="#budget">Budget</a> and they replace the model.</p>

    <h2>View</h2>
    <div class="seg" role="group" aria-label="Camera">
      <button data-view="three-quarter" aria-pressed="true">3/4</button><button data-view="top">Top</button><button data-view="side">Side</button><button data-view="front">Front</button>
    </div>
    <div class="field"><span class="lab">Layers</span>
      <div class="layers">${LAYERS.map(([k, label, c]) => `<label><input type="checkbox" data-layer="${k}" ${layerState[k] ? 'checked' : ''}><span class="swatch" style="background:${c}"></span>${label}</label>`).join('')}</div>
    </div>
    <label class="check"><input type="checkbox" id="cut"> Cut away the starboard skin</label>
    <div class="field"><label for="explode">Explode</label><input type="range" id="explode" min="0" max="1" step="0.01" value="0"></div>

    <h2>Control surfaces</h2>
    <div class="field"><label for="flap">Flaps <span class="num" id="flap-v">0°</span></label><input type="range" id="flap" min="-25" max="25" step="1" value="0"></div>
    <div class="field"><label for="elevon">Elevons <span class="num" id="elevon-v">0°</span></label><input type="range" id="elevon" min="-25" max="25" step="1" value="0">
      <span class="hint">Positive is trailing edge down. They rotate about the hinge line estimated from each leading edge.</span></div>
    <p>${badge(sweep.FLAP_R.status)} ${sweep.FLAP_R.collides_at_neutral ? `Flaps touch the inner D panel at neutral on both sides (x ≈ 657, y ≈ 229–247); clearance is ${fmt(sweep.FLAP_R.tightest.min_clearance_mm, 2)} mm at ${fmt(sweep.FLAP_R.tightest.deg)}° and about ${fmt(Math.min(...sweep.FLAP_R.clearance_at_pm5_mm), 1)} mm by ±5°. Relieve the panel lip by about 0.8 mm.` : `Flaps sweep −25° to +25° with at least ${fmt(sweep.FLAP_R.tightest.min_clearance_mm, 1)} mm clearance.`}</p>
    <p>${badge(sweep.ELEVON_R_falcon.status)} Elevons sweep −25° to +25° with at least ${fmt(sweep.ELEVON_R_falcon.tightest.min_clearance_mm, 1)} mm clearance, both sides.</p>
    <p>${badge('PASS')} Prop tips clear every well by ${fmt(minTip, 1)} mm; a seam crosses all four well walls, so assemble with the 145 mm gauge through the full opening.</p>

    <h2>Part</h2>
    <label class="field"><span class="lab">Find a part</span>
      <select id="part-select"><option value="">Click the model or choose…</option>${d.parts.parts.map((p) => `<option>${esc(p.name)}</option>`).join('')}</select></label>
    <div id="part-card" class="small muted">Nothing selected.</div>
  `);
  $$(el, '[data-view]').forEach((b) => b.addEventListener('click', () => {
    $$(el, '[data-view]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
    ctx.viewer?.frame(b.dataset.view);
  }));
  $$(el, '[data-layer]').forEach((c) => c.addEventListener('change', () => { layerState[c.dataset.layer] = c.checked; ctx.viewer?.setLayer(c.dataset.layer, c.checked); }));
  $(el, '#cut').addEventListener('change', (e) => ctx.viewer?.setCut(e.target.checked));
  $(el, '#explode').addEventListener('input', (e) => ctx.viewer?.setExplode(Number(e.target.value)));
  for (const k of ['flap', 'elevon']) {
    $(el, `#${k}`).addEventListener('input', (e) => {
      $(el, `#${k}-v`).textContent = `${e.target.value}°`;
      ctx.viewer?.setDeflection(k === 'flap' ? 'FLAP' : 'ELEVON', Number(e.target.value));
    });
  }
  $(el, '#part-select').addEventListener('change', (e) => { ctx.viewer?.select(e.target.value || null); onPick(ctx, e.target.value || null); });
  whenViewer(ctx, (v) => { for (const [k, on] of Object.entries(layerState)) v.setLayer(k, on); });
  if (pickedName) onPick(ctx, pickedName);
}

export function onPick(ctx, name) {
  pickedName = name;
  const card = document.getElementById('part-card');
  if (!card) return;
  const sel = document.getElementById('part-select');
  if (sel && name && [...sel.options].some((o) => o.value === name)) sel.value = name;
  if (!name) { card.textContent = 'Nothing selected.'; return; }
  const p = ctx.data.parts.parts.find((x) => x.name === name);
  if (!p) {
    const base = name.replace(/^REPO_/, '').replace(/_\d+$/, '');
    const ip = ctx.data.interface_parts.parts[base];
    card.innerHTML = ip ? `<h3>${esc(base)}</h3><p><span class="label-tag">${esc(ip.label)}</span> ${esc(ip.material)}, ${ip.qty_per_aircraft} per aircraft, fit check ${badge(ip.v18_fit)}</p><p>${esc(ip.notes)}</p>` : esc(name);
    card.classList.remove('muted');
    return;
  }
  const rho = p.material === 'LW-PLA' ? (ctx.meas.stage1?.lwpla_effective_density_g_cm3 || ctx.data.mass_model.lwpla_cases.planning) : ctx.data.mass_model.densities_g_cm3[p.material];
  const rows = [
    ['Kind', { printed: 'Printed', carbon: 'Carbon tube', g10: 'G10 plate (cut)', purchase: 'Purchased', keepout: 'Equipment envelope', prop: 'Purchased prop (reference)' }[p.class]],
    p.material && ['Material', `${p.material}${p.material === 'LW-PLA' ? ` at ${rho} g/cm³` : ''}`],
    p.volume_cm3 && p.class === 'printed' && ['Mass', `${fmt(p.volume_cm3 * rho)} g (${fmt(p.volume_cm3, 1)} cm³)`],
    p.class === 'g10' && ['Thickness', `${p.thickness_mm} mm${p.dxf ? `, cut profile <code>cad/v18/${esc(p.dxf)}</code>` : ''}`],
    p.length_mm && ['Tube', `${p.section_mm.join(' x ')} x ${p.length_mm} mm`],
    ['Centroid', `x ${fmt(p.centroid_mm[0])}, y ${fmt(p.centroid_mm[1])}, z ${fmt(p.centroid_mm[2])} mm`],
    ['Size', `${p.oriented_extents_mm.map((v) => fmt(v, 1)).join(' x ')} mm`],
    p.P1S && ['P1S bed', `${fmt(p.P1S.footprint_max_mm, 1)} mm footprint at ${p.P1S.rotation_deg}° (${fmt(p.P1S.margin_mm, 1)} mm spare)${p.P1S.diagonal ? ' - longer than the bed edge, place it rotated' : ''}`],
    ['Balance group', p.group],
  ].filter(Boolean);
  card.classList.remove('muted');
  card.innerHTML = `<h3>${esc(name)}</h3><dl class="readout">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;
}

// ------------------------------------------------------------------------------------------------
const knobs = { dw_mm: 0, dr_mm: 0, battery: 'V18 x362', tail_lwpla: false, avionics_forward: false, lwpla: 'planning' };
const BATT_DX = { 'V18 x362': 0, 'tray-front x284': -78, 'nose bay x150': -212 };

export function balance(ctx, el) {
  const st = ctx.data.balance_study;
  const rows = st.rows.map((r) => Object.fromEntries(st.keys.map((k, i) => [k, r[i]])));
  const uniq = (k) => [...new Set(rows.map((r) => r[k]))].sort((a, b) => (typeof a === 'number' ? a - b : 0));
  const seg = (k, vals, label) => `<div class="seg" role="group" aria-label="${label}">${vals.map((v) => `<button data-k="${k}" data-v="${esc(v)}" aria-pressed="${String(knobs[k]) === String(v)}">${typeof v === 'number' ? (v > 0 ? `+${v}` : v) : esc(v)}</button>`).join('')}</div>`;
  const anyOk = rows.filter((r) => r.both_ok).length;
  html(el, `
    <h2>Balance study</h2>
    <p>Each knob is a design change that keeps the falcon silhouette. The numbers come from the V18 mass model and the vortex-lattice model, precomputed for every combination (${rows.length}).</p>
    <div class="field"><span class="lab">Wing group aft of the nose (mm)</span>${seg('dw_mm', uniq('dw_mm'), 'Wing shift')}<span class="hint">Wings, flaps, elevons, fins, servo cassettes and rotors move together; nose, body and trays stay.</span></div>
    <div class="field"><span class="lab">Rotors within the wing (mm)</span>${seg('dr_mm', uniq('dr_mm'), 'Rotor shift')}<span class="hint">Forward of ${fmt(st.limits.forward, 1)} mm needs a leading-edge extension; aft is limited by the flaps (${fmt(st.limits.aft, 1)} mm).</span></div>
    <div class="field"><span class="lab">Battery</span>${seg('battery', uniq('battery'), 'Battery')}</div>
    <div class="field"><span class="lab">Other changes</span>
      <label class="check"><input type="checkbox" data-c="tail_lwpla" ${knobs.tail_lwpla ? 'checked' : ''}> Tail ducts and EDF saddles in LW-PLA</label>
      <label class="check"><input type="checkbox" data-c="avionics_forward" ${knobs.avionics_forward ? 'checked' : ''}> FC, VTX and EDF ESC into the empty battery bay (needs the nose-bay battery)</label>
      <label class="check"><input type="checkbox" data-c="lwpla_best" ${knobs.lwpla === 'best' ? 'checked' : ''}> Lightest LW-PLA (0.60 g/cm³)</label>
    </div>
    <div id="bal-out"></div>
    <h2>Every combination</h2>
    <p class="small">Static margin with the wells closed (forward neutral point) against the heaviest motor's share of the weight. The green corner is where both hover and wing-borne flight work: ${anyOk ? `${anyOk} combinations reach it` : 'no combination reaches it'}.</p>
    <svg class="chart" id="bal-chart" viewBox="0 0 360 250" role="img" aria-label="Scatter of all combinations"></svg>
  `);
  const update = () => {
    const pick = rows.find((r) => r.dw_mm === knobs.dw_mm && r.dr_mm === knobs.dr_mm && r.battery === knobs.battery && r.tail_lwpla === knobs.tail_lwpla
      && r.avionics_forward === knobs.avionics_forward && r.lwpla === knobs.lwpla);
    const out = $(el, '#bal-out');
    if (!pick) { out.innerHTML = '<p>That combination was not computed - avionics move forward only with the nose-bay battery.</p>'; return; }
    ctx.balance = pick;
    const both = pick.both_ok ? 'PASS' : 'STOP';
    out.innerHTML = `
      <dl class="readout">
        <dt>All-up mass</dt><dd>${fmt(pick.all_up_g)} g</dd>
        <dt>CG</dt><dd>x ${fmt(pick.cg_x_mm)} mm</dd>
        <dt>Rotor centroid</dt><dd>x ${fmt(pick.rotor_centroid_x_mm)} mm</dd>
        <dt>Neutral point</dt><dd>x ${fmt(pick.np_closed_x_mm)} (wells closed) to ${fmt(pick.np_open_x_mm)} (open)</dd>
        <dt>Static margin</dt><dd>${fmt(pick.sm_closed_pct, 1)} % to ${fmt(pick.sm_open_pct, 1)} % MAC</dd>
        <dt>Heaviest motor</dt><dd>${fmt(pick.worst_motor_pct_weight, 1)} % of weight</dd>
        <dt>Pitch trim, 15 m/s</dt><dd>${pick.all4_surfaces_trim_15ms_deg.map((v) => `${fmt(v, 1)}°`).join(' / ')} (all four surfaces)</dd>
      </dl>
      <p>${badge(pick.hover_ok ? 'PASS' : 'STOP')} Hover balance &nbsp; ${badge(pick.flight_ok ? 'PASS' : 'STOP')} Wing-borne stability &nbsp; ${badge(both)} Both</p>
      ${pick.needs_le_extension ? '<p class="small">This rotor position needs a forward leading-edge extension on the inner wing.</p>' : ''}`;
    ctx.viewer?.setShifts({ wing: pick.dw_mm, rotor: pick.dr_mm, battery: BATT_DX[pick.battery], avionics: pick.avionics_forward ? -140 : 0 });
    ctx.updateRuler();
    chart(pick);
  };
  const chart = (pick) => {
    const svg = $(el, '#bal-chart');
    const X = (v) => 40 + ((v + 30) / 50) * 300;
    const Y = (v) => 220 - ((v - 20) / 45) * 200;
    let s = `<rect x="${X(5)}" y="${Y(30)}" width="${X(20) - X(5)}" height="${Y(20) - Y(30)}" fill="var(--np)" opacity="0.14"/>`;
    for (let v = -30; v <= 20; v += 10) s += `<line class="grid" x1="${X(v)}" x2="${X(v)}" y1="20" y2="220"/><text x="${X(v)}" y="236" text-anchor="middle">${v}%</text>`;
    for (let v = 20; v <= 65; v += 15) s += `<line class="grid" x1="40" x2="340" y1="${Y(v)}" y2="${Y(v)}"/><text x="34" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`;
    for (const r of rows) {
      const x = X(Math.max(-30, Math.min(20, r.sm_closed_pct)));
      const y = Y(Math.max(20, Math.min(65, r.worst_motor_pct_weight)));
      s += `<circle cx="${x}" cy="${y}" r="2.2" fill="${r.both_ok ? 'var(--pass)' : 'var(--skin)'}" opacity="0.6"/>`;
    }
    s += `<circle cx="${X(Math.max(-30, Math.min(20, pick.sm_closed_pct)))}" cy="${Y(Math.max(20, Math.min(65, pick.worst_motor_pct_weight)))}" r="6" fill="var(--amber)" stroke="var(--cover)" stroke-width="1.5"/>`;
    s += '<text x="190" y="250" text-anchor="middle">static margin, wells closed</text>';
    svg.innerHTML = s;
  };
  $$(el, '[data-k]').forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.k;
    knobs[k] = k === 'battery' ? b.dataset.v : Number(b.dataset.v);
    if (k === 'battery' && knobs.battery !== 'nose bay x150') knobs.avionics_forward = false;
    balance(ctx, el);
  }));
  $$(el, '[data-c]').forEach((c) => c.addEventListener('change', () => {
    if (c.dataset.c === 'lwpla_best') knobs.lwpla = c.checked ? 'best' : 'planning';
    else knobs[c.dataset.c] = c.checked;
    if (c.dataset.c === 'avionics_forward' && c.checked) knobs.battery = 'nose bay x150';
    balance(ctx, el);
  }));
  update();
}

// ------------------------------------------------------------------------------------------------
function persist(ctx) { save('measurements', ctx.meas); ctx.recompute(); }

export function budget(ctx, el) {
  const r = ctx.results;
  const m = ctx.meas;
  const c = r.cost_usd;
  const motors = Object.entries(r.motor_hover_g);
  html(el, `
    <header><h1>Budget</h1>
      <p class="lede">Cost, mass, balance and the gates that decide what to buy next. Everything recalculates as you enter measurements; nothing leaves this browser until you download the file.</p></header>
    <div class="cols">
      <div>
        <div class="sheet"><h2>Gates</h2>
          <table><thead><tr><th>Gate</th><th class="n">Value</th><th>Status</th></tr></thead><tbody>
          ${r.gates.map((g) => `<tr><td>${esc(g.id)} ${esc(g.gate)}<div class="small muted">${esc(g.basis)}</div></td><td class="n">${g.value === null ? '-' : fmt(g.value, g.unit === '' ? 2 : 1)} ${esc(g.unit)}</td><td>${badge(g.status)}</td></tr>`).join('')}
          </tbody></table></div>
        <div class="sheet"><h2>Hover</h2>
          <p>CG x ${fmt(r.cg_mm[0])} mm against the rotor centroid x ${fmt(r.rotor_centroid_x_mm)} mm.</p>
          <table><thead><tr><th>Motor</th><th class="n">Hover g</th><th class="n">Bench max for PASS</th></tr></thead><tbody>
          ${motors.map(([k, v]) => `<tr><td>${k}</td><td class="n">${fmt(v)}</td><td class="n">${fmt(Math.max(v, 0) / ctx.data.power.gates.hover_fraction_pass_max)} g</td></tr>`).join('')}
          </tbody></table></div>
      </div>
      <div>
        <div class="sheet"><h2>Cost</h2>
          <table><tbody>
            <tr><td>Aircraft (V18 rows + added rows)</td><td class="n">${usd(c.aircraft[0])}–${usd(c.aircraft[1])}</td></tr>
            <tr><td>Contingency (15 % / 20 %)</td><td class="n">${usd(c.contingency[0])}–${usd(c.contingency[1])}</td></tr>
            <tr><td>Extras if not owned</td><td class="n">${usd(c.extras[0])}–${usd(c.extras[1])}</td></tr>
            <tr><td><strong>From scratch, excluding the printer</strong></td><td class="n"><strong>${usd(c.from_scratch[0])}–${usd(c.from_scratch[1])}</strong></td></tr>
            <tr><td>Still to buy (tick owned parts in <a href="#bom">Parts list</a>)</td><td class="n">${usd(c.remaining[0])}–${usd(c.remaining[1])}</td></tr>
          </tbody></table></div>
        <div class="sheet"><h2>Mass by LW-PLA density</h2>
          <table><thead><tr><th>Case</th><th class="n">g/cm³</th><th class="n">All-up g</th><th class="n">CG x</th></tr></thead><tbody>
          ${Object.entries(r.mass_cases).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="n">${fmt(v.lwpla, 2)}</td><td class="n">${fmt(v.all_up_g)}</td><td class="n">${fmt(v.cg_mm[0])}</td></tr>`).join('')}
          </tbody></table></div>
        <div class="sheet"><h2>Your measurements</h2>
          <div class="field"><label for="m-rho">LW-PLA effective density (g/cm³), Stage 1</label><input id="m-rho" type="number" step="0.01" min="0.3" max="1.3" value="${m.stage1?.lwpla_effective_density_g_cm3 ?? ''}"></div>
          <div class="field"><label for="m-mass">Weighed all-up mass (g), Stage 9</label><input id="m-mass" type="number" step="1" value="${m.stage9?.all_up_mass_g ?? ''}"></div>
          <div class="field"><label for="m-cg">Measured CG x (mm from the nose), Stage 9</label><input id="m-cg" type="number" step="1" value="${m.stage9?.flight_cg_x_mm ?? ''}"></div>
          <p class="small muted">Bench data comes from the <a href="#bench">Bench</a> tab.</p>
          <div class="row"><button class="btn primary" id="dl">Download measurements.json</button><label class="btn">Load a file<input type="file" id="ul" accept=".json" hidden></label><button class="btn" id="demo">Load the synthetic demo</button><button class="btn" id="reset">Reset to the repo file</button></div>
          <p class="small muted">Commit the downloaded file as <code>config/measurements.json</code>, then run <code>python3 tools/budget.py</code>.</p></div>
      </div>
    </div>`);
  const num = (id) => { const v = $(el, id).value; return v === '' ? null : Number(v); };
  for (const [id, set] of [['#m-rho', (v) => { m.stage1 = { ...(m.stage1 || {}), lwpla_effective_density_g_cm3: v }; }],
    ['#m-mass', (v) => { m.stage9 = { ...(m.stage9 || {}), all_up_mass_g: v }; }],
    ['#m-cg', (v) => { m.stage9 = { ...(m.stage9 || {}), flight_cg_x_mm: v }; }]]) {
    $(el, id).addEventListener('change', () => { set(num(id)); persist(ctx); budget(ctx, el); });
  }
  $(el, '#dl').addEventListener('click', () => download('measurements.json', ctx.meas));
  $(el, '#ul').addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    try { ctx.meas = JSON.parse(await f.text()); persist(ctx); budget(ctx, el); } catch { alert('That file is not valid JSON.'); }
  });
  $(el, '#demo').addEventListener('click', () => { ctx.meas = structuredClone(ctx.data.synthetic_measurements); persist(ctx); budget(ctx, el); });
  $(el, '#reset').addEventListener('click', () => { clear('measurements'); ctx.meas = structuredClone(ctx.data.measurements); ctx.recompute(); budget(ctx, el); });
}

// ------------------------------------------------------------------------------------------------
export function bom(ctx, el) {
  const owned = new Set(ctx.meas.owned_items?.ids ?? []);
  const groups = [...new Set(ctx.data.bom.map((r) => r.group))];
  const c = ctx.results.cost_usd;
  html(el, `
    <header><h1>Parts list</h1>
      <p class="lede">V18 rows keep your V18 parts; ADD rows close the gaps (total-current monitor, FC isolation, lost-model alarm, itemized adhesives, spare motor). Tick what you already own and the still-to-buy total updates.</p>
      <p class="num">Still to buy: ${usd(c.remaining[0])}–${usd(c.remaining[1])} incl. contingency</p></header>
    <div class="table-wrap"><table>
      <thead><tr><th>Own</th><th>ID</th><th>Stage</th><th>Item</th><th class="n">Buy</th><th class="n">USD</th><th class="n">g each</th><th>Before you buy</th><th></th></tr></thead>
      <tbody>${groups.map((g) => `<tr class="group-head"><td colspan="9">${esc(g)}</td></tr>${ctx.data.bom.filter((r) => r.group === g).map((r) => `
        <tr class="${owned.has(r.id) ? 'owned' : ''}">
          <td><input type="checkbox" data-id="${esc(r.id)}" ${owned.has(r.id) ? 'checked' : ''} aria-label="I own ${esc(r.item)}"></td>
          <td class="num">${esc(r.id)}</td><td class="num">${esc(r.stage)}</td>
          <td class="item"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.reference_candidate)}</a><div class="small muted">${esc(r.item)}; ${esc(r.dims_mm)}</div></td>
          <td class="n">${fmt(r.buy_qty)}</td><td class="n">${fmt(r.row_usd_low)}–${fmt(r.row_usd_high)}</td>
          <td class="n">${r.mass_basis === 'geometry' ? 'from V18' : r.unit_mass_g ? fmt(r.unit_mass_g, 1) : '-'}</td>
          <td class="small">${esc(r.purchase_gate)}</td><td><span class="chip-tag" data-c="${esc(r.change)}">${esc(r.change)}</span></td>
        </tr>`).join('')}`).join('')}</tbody></table></div>`);
  $$(el, '[data-id]').forEach((cb) => cb.addEventListener('change', () => {
    const ids = new Set(ctx.meas.owned_items?.ids ?? []);
    if (cb.checked) ids.add(cb.dataset.id); else ids.delete(cb.dataset.id);
    ctx.meas.owned_items = { ...(ctx.meas.owned_items || {}), ids: [...ids].sort() };
    persist(ctx);
    bom(ctx, el);
  }));
}

// ------------------------------------------------------------------------------------------------
export function bench(ctx, el) {
  const s2 = ctx.meas.stage2 || {};
  html(el, `
    <header><h1>Bench</h1>
      <p class="lede">Paste or open a log from the thrust-stand firmware (<code>firmware/thrust_stand</code>). Each throttle step is averaged over its last five seconds, the same way <code>tools/ingest_bench.py</code> does it.</p></header>
    <div class="cols">
      <div class="sheet">
        <div class="field"><label for="log">Thrust-stand log (CSV)</label><textarea id="log" spellcheck="false" placeholder="t_ms,phase,throttle_pct,pwm_us,thrust_g,current_a,voltage_v,temp_c"></textarea></div>
        <div class="row"><label class="btn">Open a log file<input type="file" id="logfile" accept=".csv,.txt,.log" hidden></label><button class="btn" id="sample">Load the synthetic sample</button></div>
        <div class="field"><label for="prop">Prop on this run</label><input id="prop" type="text" value="${esc(s2.prop || 'APC B5x3E')}"></div>
        <div class="row"><button class="btn primary" id="use-lift">Use as lift motor data</button><button class="btn" id="use-edf">Use as EDF data</button></div>
        <p id="bench-msg" class="small muted"></p>
      </div>
      <div class="sheet"><h2>Steps</h2><div id="bench-table" class="small muted">No log yet.</div><svg class="chart" id="bench-chart" viewBox="0 0 360 230" role="img" aria-label="Thrust and current by throttle"></svg></div>
    </div>`);
  let table = [];
  const render = () => {
    table = ingestBench($(el, '#log').value);
    const t = $(el, '#bench-table');
    if (!table.length) { t.textContent = 'No complete steps found yet.'; $(el, '#bench-chart').innerHTML = ''; return; }
    t.classList.remove('muted');
    t.innerHTML = `<table><thead><tr><th class="n">%</th><th class="n">Thrust g</th><th class="n">A</th><th class="n">V/cell</th><th class="n">°C</th></tr></thead><tbody>${table.map((r) => `<tr><td class="n">${r.throttle_pct}</td><td class="n">${fmt(r.thrust_g, 1)}</td><td class="n">${fmt(r.current_a, 2)}</td><td class="n">${fmt(r.voltage_v / 4, 3)}</td><td class="n">${r.motor_temp_c_max ?? '-'}</td></tr>`).join('')}</tbody></table>`;
    const maxT = Math.max(...table.map((r) => r.thrust_g), 1);
    const maxA = Math.max(...table.map((r) => r.current_a), 1);
    const X = (p) => 40 + (p / 100) * 290;
    const Yt = (v) => 200 - (v / maxT) * 170;
    const Ya = (v) => 200 - (v / maxA) * 170;
    let s = '';
    for (let p = 0; p <= 100; p += 25) s += `<line class="grid" x1="${X(p)}" x2="${X(p)}" y1="30" y2="200"/><text x="${X(p)}" y="216" text-anchor="middle">${p}%</text>`;
    s += `<polyline fill="none" stroke="var(--cover)" stroke-width="2" points="${table.map((r) => `${X(r.throttle_pct)},${Yt(r.thrust_g)}`).join(' ')}"/>`;
    s += `<polyline fill="none" stroke="var(--amber)" stroke-width="2" stroke-dasharray="4 3" points="${table.map((r) => `${X(r.throttle_pct)},${Ya(r.current_a)}`).join(' ')}"/>`;
    s += `<text x="40" y="20">thrust (solid) to ${fmt(maxT)} g, current (dashed) to ${fmt(maxA, 1)} A</text>`;
    const need = ctx.results.bench_max_thrust_needed_g.PASS;
    if (need < maxT * 1.4) s += `<line x1="40" x2="330" y1="${Yt(need)}" y2="${Yt(need)}" stroke="var(--stop)" stroke-dasharray="2 3"/><text x="332" y="${Yt(need) + 4}">PASS needs ${fmt(need)} g</text>`;
    $(el, '#bench-chart').innerHTML = s;
  };
  $(el, '#log').addEventListener('input', render);
  $(el, '#logfile').addEventListener('change', async (e) => { const f = e.target.files[0]; if (f) { $(el, '#log').value = await f.text(); render(); } });
  $(el, '#sample').addEventListener('click', async () => { $(el, '#log').value = await (await fetch('data/synthetic_bench_log.csv')).text(); render(); });
  const msg = (t) => { $(el, '#bench-msg').textContent = t; };
  $(el, '#use-lift').addEventListener('click', () => {
    if (!table.length) return msg('Paste a log first.');
    const top = table.reduce((a, b) => (b.thrust_g > a.thrust_g ? b : a));
    ctx.meas.stage2 = { ...(ctx.meas.stage2 || {}), thrust_table: table, max_static_thrust_g_loaded: top.thrust_g, max_current_a: Math.max(...table.map((r) => r.current_a)), prop: $(el, '#prop').value };
    persist(ctx);
    msg(`Saved: max ${fmt(top.thrust_g)} g. Gate G4 is now ${ctx.results.gates[3].status}; see Budget.`);
  });
  $(el, '#use-edf').addEventListener('click', () => {
    if (!table.length) return msg('Paste a log first.');
    ctx.meas.stage2 = { ...(ctx.meas.stage2 || {}), edf_max_thrust_g: Math.max(...table.map((r) => r.thrust_g)), edf_max_current_a: Math.max(...table.map((r) => r.current_a)) };
    persist(ctx);
    msg(`Saved EDF: ${fmt(ctx.meas.stage2.edf_max_current_a, 1)} A max. Gates G6 and G7 now read ${ctx.results.gates[5].status} and ${ctx.results.gates[6].status}.`);
  });
}

// ------------------------------------------------------------------------------------------------
const RUN_COLOURS = { 10: '#B3443A', 12: '#B3443A', 14: '#C46A2E', 18: '#9A6A10', 20: '#3F6E9E', 22: '#3F6E9E', 26: '#6B7682' };

export function wiring(ctx, el) {
  const h = ctx.data.harness;
  const st = ctx.data.aero.stations;
  const W = 900;
  const H = 520;
  const X = (y) => W / 2 + y * 0.84;
  const Y = (x) => 20 + x * 0.6;
  const outline = [...st.map((s) => [s.y, s.le]), ...st.slice().reverse().map((s) => [s.y, s.te])];
  const half = outline.map(([y, x]) => `${X(y)},${Y(x)}`).join(' ');
  const mirror = outline.map(([y, x]) => `${X(-y)},${Y(x)}`).join(' ');
  const pos = h.nodes;
  const route = (a, b) => {
    const pa = pos[a];
    const pb = pos[b];
    const ia = Math.sign(pa[1]) * Math.min(Math.abs(pa[1]), 30);
    const ib = Math.sign(pb[1]) * Math.min(Math.abs(pb[1]), 30);
    return [[pa[1], pa[0]], [ia, pa[0]], [ia, pb[0]], [ib, pb[0]], [pb[1], pb[0]]].map(([y, x]) => `${X(y)},${Y(x)}`).join(' ');
  };
  const assumed = new Set(Object.keys(h.assumed_positions));
  html(el, `
    <header><h1>Wiring</h1>
      <p class="lede">Every run drawn where your V18 puts the parts, with its cut length. Hover a run to isolate it. Pin-by-pin tables for each module are in <a href="#docs/wiring">the wiring document</a>.</p></header>
    <div class="cols" style="grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr)">
      <svg class="wiremap" viewBox="0 0 ${W} ${H}" role="img" aria-label="Top view of V18 with wiring runs">
        <polygon class="outline" points="${half}"/><polygon class="outline" points="${mirror}"/>
        ${Object.entries(pos).map(([n, p]) => `<g><rect class="box ${assumed.has(n) ? 'assumed' : ''}" x="${X(p[1]) - 9}" y="${Y(p[0]) - 6}" width="18" height="12" rx="2"/><text x="${X(p[1]) + 11}" y="${Y(p[0]) + 3}">${esc(n.replace(/_/g, ' '))}</text></g>`).join('')}
        ${h.runs.map((r, i) => `<polyline class="run" data-i="${i}" stroke="${RUN_COLOURS[r.awg] || '#6B7682'}" points="${route(r.from, r.to)}"><title>${esc(r.run)}: ${r.conductors} x ${r.awg} AWG, ${r.length_each_mm} mm</title></polyline>`).join('')}
      </svg>
      <div class="sheet"><h2>Cut list</h2><div class="table-wrap"><table><thead><tr><th>Run</th><th class="n">AWG</th><th class="n">mm each</th></tr></thead><tbody>
        ${h.runs.map((r, i) => `<tr data-i="${i}"><td>${esc(r.run)}<div class="small muted">${r.conductors} conductors${r.note ? `; ${esc(r.note)}` : ''}</div></td><td class="n">${r.awg}</td><td class="n">${fmt(r.length_each_mm)}</td></tr>`).join('')}
        </tbody></table></div>
        <h3>Wire to buy</h3><p class="num">${Object.entries(h.buy_per_gauge_m_with_25pct_spare).map(([k, v]) => `${k} AWG ${v} m`).join(', ')}</p>
        <p class="small muted">Dashed boxes are positions the V18 model does not define (star point, current sensor, servo bus, airspeed, buzzer, steering servo).</p></div>
    </div>
    <div class="sheet"><h2>Flight-controller outputs</h2><div class="table-wrap"><table><thead><tr><th>Output</th><th>Timer group</th><th>Function</th><th>Device</th><th>Power</th></tr></thead><tbody>
      ${ctx.data.pinmap.map((p) => `<tr><td class="num">${esc(p.fc_output)}</td><td class="num">${esc(p.timer_group)}</td><td>${esc(p.servo_function)} ${esc(p.function_name)}</td><td>${esc(p.device)}</td><td>${esc(p.power_source)}</td></tr>`).join('')}
    </tbody></table></div></div>`);
  const runs = $$(el, '.run');
  const focus = (i) => runs.forEach((r) => r.classList.toggle('dim', i !== null && r.dataset.i !== String(i)));
  [...runs, ...$$(el, 'tr[data-i]')].forEach((n) => {
    n.addEventListener('mouseenter', () => focus(n.dataset.i));
    n.addEventListener('mouseleave', () => focus(null));
  });
}

// ------------------------------------------------------------------------------------------------
export function stages(ctx, el) {
  const notes = ctx.meas.stage_tracker || {};
  const bomById = Object.fromEntries(ctx.data.bom.map((r) => [r.id, r]));
  html(el, `
    <header><h1>Build stages</h1>
      <p class="lede">Buy and print only what each stage needs. Mark each gate as you measure it; the marks are saved with your measurements. Full numbers are in <a href="#docs/build-stages-and-gates">the gates document</a>.</p></header>
    ${ctx.data.stages.stages.map((s) => `
      <section class="stage"><div class="stage-n">${s.n}</div><div>
        <h3>${esc(s.title)}</h3>
        <ul>${s.do.map((d) => `<li>${esc(d)}</li>`).join('')}</ul>
        ${s.buy.length ? `<p class="small">Buy now: ${s.buy.map((id) => `<abbr title="${esc(bomById[id]?.item || '')}">${esc(id)}</abbr>`).join(', ')}</p>` : ''}
        ${s.gates.map((g, i) => {
          const k = `${s.n}.${i}`;
          const v = notes[k] || '';
          return `<div class="gate-row"><select data-k="${k}" aria-label="Status of: ${esc(g)}"><option value="">not yet</option>${['PASS', 'FIX', 'STOP'].map((o) => `<option ${v === o ? 'selected' : ''}>${o}</option>`).join('')}</select><span>${esc(g)}</span></div>`;
        }).join('')}
      </div></section>`).join('')}`);
  $$(el, 'select[data-k]').forEach((s) => s.addEventListener('change', () => {
    ctx.meas.stage_tracker = { ...(ctx.meas.stage_tracker || {}), [s.dataset.k]: s.value };
    persist(ctx);
  }));
}

// ------------------------------------------------------------------------------------------------
let markedLib = null;
export async function docs(ctx, el, sub) {
  const idx = ctx.data.docs_index;
  const slug = sub || idx[0].slug;
  html(el, `<div class="docs"><nav aria-label="Documents">${idx.map((d) => `<a href="#docs/${d.slug}" ${d.slug === slug ? 'aria-current="page"' : ''}>${esc(d.title)}</a>`).join('')}</nav><article class="md" id="md">Loading…</article></div>`);
  if (!markedLib) markedLib = await import('../vendor/marked/marked.esm.js');
  const entry = idx.find((d) => d.slug === slug) || idx[0];
  const text = await (await fetch(`docs/${entry.slug}.md`)).text();
  const art = $(el, '#md');
  art.innerHTML = markedLib.marked.parse(text);
  // keep links that point at other docs inside the app; repo-relative files go to the repository
  const bySource = Object.fromEntries(idx.map((d) => [d.source.split('/').pop(), d.slug]));
  for (const a of $$(art, 'a[href]')) {
    const href = a.getAttribute('href');
    if (/^https?:/.test(href) || href.startsWith('#')) { if (/^https?:/.test(href)) { a.target = '_blank'; a.rel = 'noopener'; } continue; }
    const base = href.split('/').pop().split('#')[0];
    if (bySource[base]) a.setAttribute('href', `#docs/${bySource[base]}`);
    else a.removeAttribute('href');
  }
  for (const img of $$(art, 'img[src]')) {
    const name = img.getAttribute('src').split('/').pop();
    img.setAttribute('src', `img/${name}`);
  }
}
