// Small DOM helpers shared by the views.
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const fmt = (v, nd = 0) => (v === null || v === undefined || Number.isNaN(v) ? '-' : Number(v).toLocaleString('en-US', { minimumFractionDigits: nd, maximumFractionDigits: nd }));
export const usd = (v) => `$${fmt(v)}`;
export const badge = (s) => `<span class="badge" data-s="${esc(s)}">${esc(s)}</span>`;
export function html(target, markup) { target.innerHTML = markup; return target; }
export const $ = (root, sel) => root.querySelector(sel);
export const $$ = (root, sel) => [...root.querySelectorAll(sel)];
export function worst(statuses) {
  const order = ['STOP', 'FAIL', 'FIX', 'FLAG', 'UNKNOWN', 'PASS'];
  return order.find((s) => statuses.includes(s)) ?? 'PASS';
}
