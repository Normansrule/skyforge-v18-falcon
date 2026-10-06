// The fore-aft balance ruler under the 3D view: nose to tail, with the rotor rows, rotor centroid,
// neutral-point band, the flight CG window and the CG. The gap between CG and where it must be is the
// story of V18, so it is drawn rather than written.
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs = {}, text) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
};

export function drawRuler(host, { cgX, rotorX, rotorRows, npBand, window: win, length = 810 }) {
  const W = Math.max(host.clientWidth - 32, 320);
  const H = 92;
  const pad = 14;
  const sx = (x) => pad + ((W - 2 * pad) * x) / length;
  const y0 = 56;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `CG at x ${cgX.toFixed(0)} mm, rotor centroid x ${rotorX.toFixed(0)} mm, neutral point x ${npBand[0].toFixed(0)} to ${npBand[1].toFixed(0)} mm` });
  const defs = el('defs');
  const mk = el('marker', { id: 'arrow', viewBox: '0 0 8 8', refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' });
  mk.append(el('path', { d: 'M0,0 L8,4 L0,8 z', fill: 'var(--stop)' }));
  defs.append(mk);
  svg.append(defs);

  svg.append(el('rect', { class: 'np-band', x: sx(npBand[0]), y: y0 - 26, width: Math.max(sx(npBand[1]) - sx(npBand[0]), 2), height: 30 }));
  if (win) svg.append(el('rect', { x: sx(win[0]), y: y0 - 4, width: sx(win[1]) - sx(win[0]), height: 8, fill: 'var(--np)', opacity: 0.55 }));
  svg.append(el('line', { class: 'axis', x1: sx(0), x2: sx(length), y1: y0, y2: y0 }));
  for (let x = 0; x <= length; x += 100) {
    const g = el('g', { class: 'tick' });
    g.append(el('line', { class: 'axis', x1: sx(x), x2: sx(x), y1: y0, y2: y0 + 5 }));
    g.append(el('text', { x: sx(x), y: y0 + 17, 'text-anchor': 'middle' }, x === 0 ? 'nose' : String(x)));
    svg.append(g);
  }
  const narrow = W < 640;
  if (!narrow) svg.append(el('text', { class: 'lbl', x: sx(length), y: y0 + 30, 'text-anchor': 'end' }, 'x mm, aft from the nose'));
  for (const r of rotorRows) svg.append(el('line', { class: 'rotor-row', x1: sx(r), x2: sx(r), y1: y0 - 30, y2: y0 }));
  svg.append(el('line', { class: 'rotor', x1: sx(rotorX), x2: sx(rotorX), y1: y0 - 34, y2: y0 + 4 }));
  svg.append(el('text', { class: 'lbl rotor-lbl big', x: sx(rotorX), y: 14, 'text-anchor': 'middle' }, `rotor centre x${rotorX.toFixed(0)}`));
  svg.append(el('text', { class: 'lbl np-lbl', x: sx(npBand[0]), y: y0 + 30, 'text-anchor': 'start' }, win && !narrow ? 'neutral point band; flight CG window under it' : 'neutral point band'));

  const target = win ? (win[0] + win[1]) / 2 : rotorX;
  if (Math.abs(cgX - target) > 12) {
    svg.append(el('line', { class: 'gap', x1: sx(cgX) - Math.sign(cgX - target) * 9, x2: sx(target) + Math.sign(cgX - target) * 3, y1: y0 - 12, y2: y0 - 12 }));
    svg.append(el('text', { class: 'gap-lbl', x: sx(Math.max(cgX, target)) - 14, y: y0 - 17, 'text-anchor': 'end' }, narrow ? `${Math.abs(cgX - target).toFixed(0)} mm` : `${Math.abs(cgX - target).toFixed(0)} mm from the flight window`));
  }
  svg.append(el('path', { class: 'cg', d: `M${sx(cgX)},${y0 - 20} l9,9 l-9,9 l-9,-9 z` }));
  const close = Math.abs(sx(cgX) - sx(rotorX)) < 95;
  svg.append(el('text', { class: 'lbl cg-lbl big', x: sx(cgX), y: close ? 28 : 14, 'text-anchor': close ? 'start' : 'middle', dx: close ? 12 : 0 }, `CG x${cgX.toFixed(0)}`));
  host.replaceChildren(svg);
}
