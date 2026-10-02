// Per-viewer state kept in the browser (measurements entered here, owned parts, stage notes).
// Storage can be unavailable (private windows, desktop webviews with storage off): every access is
// guarded and the app works without it. The durable record is config/measurements.json in the repo -
// use "Download measurements.json" and commit it.
const KEY = 'skyforge-v18:';

export function load(name, fallback) {
  try {
    const raw = window.localStorage.getItem(KEY + name);
    return raw ? JSON.parse(raw) : structuredClone(fallback);
  } catch {
    return structuredClone(fallback);
  }
}

export function save(name, value) {
  try {
    window.localStorage.setItem(KEY + name, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function clear(name) {
  try { window.localStorage.removeItem(KEY + name); } catch { /* storage unavailable */ }
}

export function download(filename, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2) + '\n'], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.append(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
