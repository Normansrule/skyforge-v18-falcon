// Copy the browser libraries and fonts the site needs from node_modules into site/vendor,
// so the site works offline (GitHub Pages, installed web app, Tauri desktop) with no CDN.
import { cpSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';

const root = new URL('../..', import.meta.url).pathname;
const nm = join(root, 'node_modules');
const out = join(root, 'site', 'vendor');
const copy = (from, to) => { mkdirSync(dirname(join(out, to)), { recursive: true }); cpSync(join(nm, from), join(out, to)); };

for (const f of ['build/three.module.js', 'build/three.core.js', 'LICENSE',
  'examples/jsm/controls/OrbitControls.js', 'examples/jsm/loaders/GLTFLoader.js',
  'examples/jsm/utils/BufferGeometryUtils.js', 'examples/jsm/utils/SkeletonUtils.js', 'examples/jsm/libs/meshopt_decoder.module.js']) {
  copy(`three/${f}`, `three/${f}`);
}
copy('marked/lib/marked.esm.js', 'marked/marked.esm.js');
copy('marked/LICENSE', 'marked/LICENSE');
const fonts = [
  ['@fontsource/atkinson-hyperlegible-next', 'atkinson-hyperlegible-next-latin-400-normal.woff2'],
  ['@fontsource/atkinson-hyperlegible-next', 'atkinson-hyperlegible-next-latin-700-normal.woff2'],
  ['@fontsource/atkinson-hyperlegible-next', 'atkinson-hyperlegible-next-latin-400-italic.woff2'],
  ['@fontsource/saira-semi-condensed', 'saira-semi-condensed-latin-500-normal.woff2'],
  ['@fontsource/saira-semi-condensed', 'saira-semi-condensed-latin-700-normal.woff2'],
];
for (const [pkg, f] of fonts) copy(`${pkg}/files/${f}`, `fonts/${f}`);
copy('@fontsource/atkinson-hyperlegible-next/LICENSE', 'fonts/LICENSE-atkinson-hyperlegible-next.txt');
copy('@fontsource/saira-semi-condensed/LICENSE', 'fonts/LICENSE-saira-semi-condensed.txt');
const versions = Object.fromEntries(['three', 'marked', '@fontsource/atkinson-hyperlegible-next', '@fontsource/saira-semi-condensed']
  .map((p) => [p, JSON.parse(readFileSync(join(nm, p, 'package.json'))).version]));
writeFileSync(join(out, 'VERSIONS.json'), JSON.stringify(versions, null, 1));
console.log('vendored', versions);
