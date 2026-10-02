// V19 web data: every variant the viewer can switch to has its model, its moves name real V18 parts,
// and the recommended variant passes.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = new URL('..', import.meta.url).pathname;
const j = (p) => JSON.parse(readFileSync(join(root, p), 'utf8'));
const V = j('site/data/variants.json');
const v18 = new Set(j('site/data/parts.json').parts.map((p) => p.name));

test('recommended variant passes', () => {
  const r = V.variants[V.recommended];
  assert.ok(r.eval.passes, 'gates');
  assert.equal(r.checks.collisions, 0, 'collisions');
});

for (const slug of V.order) {
  test(`variant ${slug} is complete`, () => {
    const v = V.variants[slug];
    assert.ok(existsSync(join(root, 'site/models', `${slug}.glb`)), 'glb');
    for (const n of Object.keys(v.moves)) assert.ok(v18.has(n), `move for unknown part ${n}`);
    for (const n of [...v.hidden, ...v.modified]) assert.ok(v18.has(n), `unknown hidden/modified part ${n}`);
    assert.ok(v.new.length > 0 && v.changes.length > 0);
    assert.ok(v.length_mm >= 810);
  });
}
