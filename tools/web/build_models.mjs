// Weld, simplify and meshopt-compress the raw GLBs written by tools/export_web.py.
// Node names (V18 part names) are preserved - the viewer relies on them.
import { execFileSync } from 'node:child_process';
import { statSync } from 'node:fs';

const root = new URL('../..', import.meta.url).pathname;
const cli = `${root}node_modules/.bin/gltf-transform`;
const run = (...a) => execFileSync(cli, a, { stdio: ['ignore', 'ignore', 'inherit'] });
import { existsSync } from 'node:fs';
const variants = ['v19a_long_nose', 'v19b_falcon_tail', 'v19c_forward_rotors', 'v19r_boom_rotors', 'v19w_four_in_wings', 'v19s_stoop_crest', 'v19g_gyr_crest', 'v19f_swift_stoop']
  .filter((v) => existsSync(`${root}site/models/raw/${v}.glb`)).map((v) => [v, '0.25', '0.0005']);
for (const [name, ratio, error] of [['v18', '0.12', '0.0006'], ['repo_parts', '0.5', '0.0005'], ...variants]) {
  const raw = `${root}site/models/raw/${name}.glb`;
  const tmp = `${root}site/models/raw/${name}.tmp.glb`;
  const out = `${root}site/models/${name}.glb`;
  run('weld', raw, tmp);
  run('simplify', tmp, tmp, '--ratio', ratio, '--error', error);
  run('meshopt', tmp, out, '--level', 'medium');
  console.log(name, (statSync(raw).size / 1e6).toFixed(1), 'MB ->', (statSync(out).size / 1e6).toFixed(2), 'MB');
}
