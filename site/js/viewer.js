// Three.js viewer for the V18 assembly and the V19 variants. Works in V18 coordinates (mm, +X aft,
// +Y starboard, +Z up) inside a root group rotated so V18 +Z is screen-up.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const dark = () => window.matchMedia('(prefers-color-scheme: dark)').matches;
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

// material look per kind of part
const LOOK = {
  skin: { roughness: 0.58, metalness: 0.0, env: 0.75 },
  controls: { roughness: 0.5, metalness: 0.0, env: 0.7 },
  fittings: { roughness: 0.6, metalness: 0.0, env: 0.6 },
  structure: { roughness: 0.42, metalness: 0.25, env: 0.9 },
  hardware: { roughness: 0.38, metalness: 0.55, env: 1.0 },
  props: { roughness: 0.4, metalness: 0.1, env: 0.6, opacity: 0.42 },
  keepouts: { roughness: 0.6, metalness: 0.0, env: 0.3, opacity: 0.24 },
  repo: { roughness: 0.5, metalness: 0.05, env: 0.7 },
};

function gridMaterial() {
  return new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { uColor: { value: new THREE.Color(dark() ? 0x9fb0c2 : 0x5a6878) }, uFade: { value: 1250.0 } },
    vertexShader: 'varying vec2 vP; void main(){ vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `varying vec2 vP; uniform vec3 uColor; uniform float uFade;
      float line(float w, float s){ vec2 g = abs(fract(vP / s - 0.5) - 0.5) / fwidth(vP / s); return 1.0 - min(min(g.x, g.y), 1.0); }
      void main(){ float d = length(vP); float fade = smoothstep(uFade, uFade * 0.25, d);
        float a = max(line(1.0, 50.0) * 0.10, line(1.0, 250.0) * 0.22) * fade;
        if (a < 0.002) discard; gl_FragColor = vec4(uColor, a); }`,
    extensions: { derivatives: true },
  });
}

function xrayMaterial(color) {
  // translucent single-layer tint: depth-written so stacked shells do not build up
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.16, depthWrite: true, side: THREE.FrontSide });
}

function cgSprite() {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  g.translate(64, 64);
  g.beginPath(); g.arc(0, 0, 58, 0, Math.PI * 2); g.fillStyle = '#fff'; g.fill();
  g.fillStyle = '#1C242D';
  g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, 58, 0, Math.PI / 2); g.closePath(); g.fill();
  g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, 58, Math.PI, Math.PI * 1.5); g.closePath(); g.fill();
  g.lineWidth = 6; g.strokeStyle = '#E5A34E'; g.beginPath(); g.arc(0, 0, 58, 0, Math.PI * 2); g.stroke();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, depthTest: false, transparent: true }));
  s.scale.set(34, 34, 1);
  s.renderOrder = 20;
  return s;
}

export async function createViewer(canvas, { parts, hinges, onPick, variants = {}, onProgress }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.localClippingEnabled = true;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.55;
  const camera = new THREE.PerspectiveCamera(32, 1, 5, 30000);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = !reduceMotion;
  controls.dampingFactor = 0.1;
  controls.maxPolarAngle = Math.PI * 0.53;
  controls.minDistance = 250;
  controls.maxDistance = 6000;

  scene.add(new THREE.HemisphereLight(0xeef3f8, 0x3a434d, 0.45));
  const sun = new THREE.DirectionalLight(0xfff6ea, 2.4);
  sun.position.set(-500, 1500, 700);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -1000, right: 1000, top: 1000, bottom: -1000, near: 200, far: 4000 });
  sun.shadow.bias = -0.0004;
  sun.shadow.normalBias = 1.2;
  sun.shadow.radius = 5;
  scene.add(sun, sun.target);
  const rim = new THREE.DirectionalLight(0xcfe0f2, 0.7);
  rim.position.set(900, 500, -900);
  scene.add(rim);

  const root = new THREE.Group();
  root.rotation.x = -Math.PI / 2; // V18 +Z -> screen up
  scene.add(root);

  // floor: soft shadow catcher + fading grid, just under the wheels (z = -127)
  const floorZ = -127.6;
  const shadowFloor = new THREE.Mesh(new THREE.PlaneGeometry(5000, 5000), new THREE.ShadowMaterial({ opacity: dark() ? 0.42 : 0.2 }));
  shadowFloor.position.set(520, 0, floorZ);
  shadowFloor.receiveShadow = true;
  root.add(shadowFloor);
  const grid = new THREE.Mesh(new THREE.PlaneGeometry(3200, 3200), gridMaterial());
  grid.position.set(520, 0, floorZ + 0.3);
  grid.renderOrder = -1;
  root.add(grid);
  sun.target.position.set(520, 0, 0);

  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const track = (p) => { onProgress?.(p); return p; };
  const [v18, repo] = await Promise.all([loader.loadAsync('models/v18.glb', (e) => e.total && track(e.loaded / e.total)), loader.loadAsync('models/repo_parts.glb')]);

  const meta = new Map(parts.map((p) => [p.name, p]));
  // GLTFLoader strips '.', ':', '/' and brackets from node names (PropertyBinding.sanitizeNodeName); map them back so
  // parts such as SP1_side_servo_cassette_PRINT4_360.222222222 find their metadata and variant moves
  const realName = new Map();
  const sanitize = (n) => THREE.PropertyBinding.sanitizeNodeName(n);
  for (const n of meta.keys()) realName.set(sanitize(n), n);
  for (const v of Object.values(variants)) for (const n of [...(v.modified || []), ...(v.new || []).map((x) => x.name)]) realName.set(sanitize(n), n);
  const all = []; // every registered entry, V18 and variants
  const objects = new Map(); // V18 name -> entry
  const vobjects = new Map(); // slug -> Map(name -> entry)
  const clipStarboard = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  let center = new THREE.Vector3(405, 0, 0);

  function styleMesh(m, layer, isNew) {
    const src = m.material;
    const look = LOOK[layer] || LOOK.skin;
    const mat = new THREE.MeshStandardMaterial({
      color: src.color ? src.color.clone().convertSRGBToLinear() : new THREE.Color(0x929ba5),
      roughness: look.roughness, metalness: look.metalness, envMapIntensity: look.env, side: THREE.DoubleSide,
      transparent: !!look.opacity || (src.opacity ?? 1) < 1, opacity: look.opacity ?? src.opacity ?? 1,
      depthWrite: !(look.opacity && look.opacity < 0.5), polygonOffset: layer === 'keepouts', polygonOffsetFactor: 1,
    });
    if (isNew && layer !== 'keepouts' && layer !== 'structure') mat.roughness = 0.45;
    mat.userData.baseOpacity = mat.opacity;
    mat.userData.baseTransparent = mat.transparent;
    m.material = mat;
    m.castShadow = !look.opacity;
    m.receiveShadow = layer === 'skin' || layer === 'controls' || layer === 'fittings';
  }

  function register(gltf, { kind, variant = null, metaFor }) {
    const holder = new THREE.Group();
    const map = variant ? new Map() : objects;
    for (const child of [...gltf.scene.children]) {
      const name = realName.get(child.name) ?? child.name;
      child.name = name;
      const m = metaFor(name);
      const pivot = new THREE.Group();
      pivot.name = name;
      pivot.add(child);
      holder.add(pivot);
      if (hinges[name] && kind === 'v18') {
        const hp = new THREE.Vector3(...hinges[name].point);
        pivot.position.copy(hp);
        child.position.sub(hp);
      }
      child.traverse((o) => { if (o.isMesh) { styleMesh(o, m.layer, kind === 'new'); o.userData.partName = name; } });
      const box = new THREE.Box3().setFromObject(child);
      const c = box.getCenter(new THREE.Vector3());
      if (hinges[name] && kind === 'v18') c.add(pivot.position);
      const e = { obj: pivot, base: pivot.position.clone(), centroid: c, layer: m.layer, group: m.group, name, kind, variant,
        offset: new THREE.Vector3(), from: new THREE.Vector3(), to: new THREE.Vector3(), opacity: 1, show: true, isNew: kind === 'new' };
      if (variant) { e.show = false; e.opacity = 0; pivot.visible = false; }
      map.set(name, e);
      all.push(e);
    }
    root.add(holder);
    return map;
  }
  register(v18, { kind: 'v18', metaFor: (n) => ({ layer: meta.get(n)?.layer ?? 'skin', group: meta.get(n)?.group ?? 'body' }) });
  register(repo, { kind: 'repo', metaFor: () => ({ layer: 'repo', group: 'body' }) });
  for (const e of all) if (e.kind === 'repo') objects.set(e.name, e);

  // ----- markers -----
  const markers = new THREE.Group();
  root.add(markers);
  const cgGroup = new THREE.Group();
  const cgIcon = cgSprite();
  cgIcon.position.z = 78;
  const cgStem = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 200, 8), new THREE.MeshBasicMaterial({ color: '#E5A34E', depthTest: false, transparent: true, opacity: 0.85 }));
  cgStem.rotation.x = Math.PI / 2;
  cgStem.position.z = -22;
  cgStem.renderOrder = 19;
  cgGroup.add(cgIcon, cgStem);
  markers.add(cgGroup);
  const rotorBar = new THREE.Mesh(new THREE.BoxGeometry(3, 560, 3), new THREE.MeshBasicMaterial({ color: '#3F6E9E', depthTest: false, transparent: true, opacity: 0.9 }));
  rotorBar.renderOrder = 18;
  rotorBar.position.z = 40;
  markers.add(rotorBar);
  const npBand = new THREE.Mesh(new THREE.BoxGeometry(1, 1060, 1.5), new THREE.MeshBasicMaterial({ color: '#2F7D5B', transparent: true, opacity: 0.2, depthWrite: false }));
  npBand.position.z = 36;
  markers.add(npBand);

  // ----- X-ray ghost of V18 for comparing a variant against it -----
  let ghost = null;
  function buildGhost() {
    ghost = new THREE.Group();
    const mat = xrayMaterial(dark() ? 0x7fd3ff : 0x3d86d8);
    for (const e of objects.values()) {
      if (e.kind !== 'v18' || !['skin', 'controls'].includes(e.layer)) continue;
      e.obj.updateMatrixWorld(true);
      e.obj.traverse((o) => {
        if (!o.isMesh) return;
        const g = new THREE.Mesh(o.geometry, mat);
        g.matrixAutoUpdate = false;
        // matrix relative to root at the V18 position (no offsets)
        const m = new THREE.Matrix4().copy(root.matrixWorld).invert().multiply(o.matrixWorld);
        const off = new THREE.Matrix4().makeTranslation(-e.offset.x, -e.offset.y, -e.offset.z);
        g.matrix.copy(off.multiply(m));
        g.renderOrder = 30;
        ghost.add(g);
      });
    }
    ghost.visible = false;
    root.add(ghost);
  }

  // ----- camera framing -----
  const VIEWS = { 'three-quarter': [-860, 600, 1180], top: [0, 1850, 1], side: [0, 110, 1650], front: [-1650, 210, 0], rear: [1650, 260, 300] };
  let lastView = 'three-quarter';
  let spanX = 810;
  // pilot's eye: just ahead of the FPV camera envelope, wherever the current variant puts it
  function cockpitPose() {
    const e = objects.get('KEEP_OUT_CAMERA_19mm');
    const c = e ? e.centroid.clone().add(e.offset) : new THREE.Vector3(103, 0, 40);
    const eye = new THREE.Vector3(c.x - 11, c.y, c.z).applyMatrix4(root.matrixWorld);
    const look = new THREE.Vector3(c.x - 12, c.y, c.z - 0.12).applyMatrix4(root.matrixWorld);
    return { pos: eye, target: look };
  }
  // in the pilot's seat a real camera sees through the clear canopy, not the envelopes around it
  const PILOT_HIDE = /canopy_clear|cockpit_camera_seat|^CAM_19mm_cradle$/;
  let pilot = false;
  function setLens(cockpit) {
    if (cockpit !== pilot) {
      pilot = cockpit;
      for (const e of all) {
        if (e.layer === 'keepouts' || PILOT_HIDE.test(e.name)) e.obj.visible = cockpit ? false : (e.show && state.layers[e.layer] !== false);
      }
    }
    camera.fov = cockpit ? 84 : 32;
    camera.near = cockpit ? 0.5 : 5;
    camera.updateProjectionMatrix();
    controls.minDistance = cockpit ? 0.2 : 250;
    controls.enableZoom = !cockpit;
    controls.enablePan = !cockpit;
    controls.maxPolarAngle = cockpit ? Math.PI : Math.PI * 0.53;
    markers.visible = !cockpit;
  }
  function viewPose(view = 'three-quarter', cx = center.x, len = spanX) {
    if (view === 'cockpit') return cockpitPose();
    const target = new THREE.Vector3(cx, 0, -10).applyMatrix4(root.matrixWorld);
    const v = VIEWS[view];
    const k = (camera.aspect < 1.25 ? Math.pow(1.25 / camera.aspect, 1.05) : 1) * Math.max(1, Math.pow(len / 900, 0.95));
    return { target, pos: new THREE.Vector3(target.x + v[0] * k, target.y + v[1] * k, target.z + v[2] * k) };
  }
  let camTween = null;
  function frame(view = 'three-quarter', ms = reduceMotion ? 0 : 750, cx = center.x, len = spanX) {
    lastView = view;
    const { target, pos } = viewPose(view, cx, len);
    setLens(view === 'cockpit');
    if (view === 'cockpit') ms = 0; // jump straight into the seat
    if (!ms) { controls.target.copy(target); camera.position.copy(pos); controls.update(); request(); return; }
    camTween = { t0: performance.now(), ms, p0: camera.position.clone(), p1: pos, q0: controls.target.clone(), q1: target };
    request();
  }

  // ----- render loop (on demand) -----
  let pending = false;
  let anim = null;
  function request() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(tick);
  }
  function tick(now) {
    pending = false;
    let more = false;
    if (camTween) {
      const t = Math.min(1, (now - camTween.t0) / camTween.ms);
      const k = ease(t);
      camera.position.lerpVectors(camTween.p0, camTween.p1, k);
      controls.target.lerpVectors(camTween.q0, camTween.q1, k);
      if (t >= 1) camTween = null; else more = true;
    }
    if (anim) {
      const t = Math.min(1, (now - anim.t0) / anim.ms);
      stepAnim(ease(t));
      if (t >= 1) { finishAnim(); anim = null; } else more = true;
    }
    if (controls.update()) more = true;
    renderer.render(scene, camera);
    if (more) request();
  }
  controls.addEventListener('change', request);
  function resize() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    request();
  }
  new ResizeObserver(resize).observe(canvas);
  root.updateMatrixWorld(true);
  resize();

  // intro: swing in from a low side angle
  {
    const { target, pos } = viewPose('three-quarter');
    controls.target.copy(target);
    if (reduceMotion) camera.position.copy(pos);
    else {
      camera.position.copy(target.clone().add(new THREE.Vector3(-2600, 260, 1500)));
      camTween = { t0: performance.now() + 120, ms: 1700, p0: camera.position.clone(), p1: pos, q0: target.clone(), q1: target };
    }
    controls.update();
    request();
  }
  let lastAspect = camera.aspect;
  new ResizeObserver(() => { if (Math.abs(camera.aspect - lastAspect) > 0.2) { lastAspect = camera.aspect; frame('three-quarter', 0); } }).observe(canvas);

  // ----- state -----
  const state = { explode: 0, deflect: { FLAP: 0, ELEVON: 0 }, shifts: { wing: 0, rotor: 0, battery: 0, avionics: 0 }, cut: false, layers: {}, variant: null };
  const AVIONICS = new Set(['KEEP_OUT_FC_54x34x24', 'KEEP_OUT_VTX_42x26x14', 'KEEP_OUT_EDF_ESC_73x30x12_plus_margin']);
  const layerOn = (e) => state.layers[e.layer] !== false;

  function applyTransforms() {
    for (const e of all) {
      const p = e.base.clone().add(e.offset);
      if (!state.variant && e.kind !== 'new') {
        let dx = 0;
        if (e.group === 'wing') dx += state.shifts.wing;
        if (e.group === 'rotor') dx += state.shifts.wing + state.shifts.rotor;
        if (e.group === 'battery') dx += state.shifts.battery;
        if (AVIONICS.has(e.name)) dx += state.shifts.avionics;
        p.x += dx;
      }
      if (state.explode > 0) {
        const dir = e.centroid.clone().add(e.offset).sub(center);
        dir.x *= 0.35;
        p.addScaledVector(dir, state.explode * 0.9);
        if (e.layer === 'structure' || e.layer === 'hardware') p.z -= state.explode * 120;
        if (e.layer === 'keepouts' || e.layer === 'fittings') p.z += state.explode * 90;
      }
      e.obj.position.copy(p);
      const key = e.name.startsWith('FLAP_') ? 'FLAP' : e.name.startsWith('ELEVON_') ? 'ELEVON' : null;
      if (key && hinges[e.name]) {
        const d = new THREE.Vector3(...hinges[e.name].dir).normalize();
        e.obj.quaternion.setFromAxisAngle(d, THREE.MathUtils.degToRad(state.deflect[key]));
      }
    }
    request();
  }

  function setOpacity(e, a) {
    e.opacity = a;
    e.obj.traverse((o) => {
      if (!o.isMesh) return;
      const m = o.material;
      const fading = a < 0.999;
      m.transparent = fading || m.userData.baseTransparent;
      m.opacity = m.userData.baseOpacity * a;
      m.depthWrite = !fading && !(m.userData.baseOpacity < 0.5);
    });
  }
  function stepAnim(k) {
    for (const e of all) {
      if (e.animMove) e.offset.lerpVectors(e.from, e.to, k);
      if (e.fade) setOpacity(e, e.fade[0] + (e.fade[1] - e.fade[0]) * k);
    }
    center.lerpVectors(anim.c0, anim.c1, k);
    applyTransforms();
  }
  function finishAnim() {
    for (const e of all) {
      if (e.fade) { if (e.fade[1] === 0) e.obj.visible = false; setOpacity(e, 1); }
      e.fade = null;
      e.animMove = false;
    }
    if (ghost && state.ghost) ghost.visible = true;
    applyTransforms();
  }

  const loading = new Map();
  async function loadVariant(slug) {
    if (vobjects.has(slug)) return vobjects.get(slug);
    if (!loading.has(slug)) {
      loading.set(slug, loader.loadAsync(`models/${slug}.glb`).then((gltf) => {
        const v = variants[slug];
        const modified = new Set(v.modified);
        const newMeta = new Map(v.new.map((n) => [n.name, n]));
        const map = register(gltf, {
          kind: 'new', variant: slug,
          metaFor: (n) => (modified.has(n) ? { layer: meta.get(n)?.layer ?? 'skin', group: meta.get(n)?.group ?? 'body' }
            : { layer: newMeta.get(n)?.layer ?? 'skin', group: 'new' }),
        });
        for (const [n, e] of map) if (modified.has(n)) { e.kind = 'mod'; e.isNew = false; }
        for (const e of map.values()) e.obj.traverse((o) => { if (o.isMesh && state.cut && ['skin', 'controls'].includes(e.layer)) o.material.clippingPlanes = [clipStarboard]; });
        vobjects.set(slug, map);
        return map;
      }));
    }
    return loading.get(slug);
  }

  let requestId = 0;
  async function setVariant(slug, { animate = true } = {}) {
    if (slug && !variants[slug]) slug = null;
    const v = slug ? variants[slug] : null;
    const my = ++requestId;
    if (slug) await loadVariant(slug);
    if (my !== requestId) return; // a newer switch arrived while this model was loading
    state.variant = slug;
    const hidden = new Set(v ? [...v.hidden, ...v.modified] : []);
    const moves = v ? { ...v.moves, ...v.repo_moves } : {};
    const ms = animate && !reduceMotion ? 1100 : 0;
    for (const e of all) {
      let show;
      let to = new THREE.Vector3();
      if (e.variant) {
        show = e.variant === slug;
        if (show && e.kind === 'mod' && moves[e.name]) to.set(...moves[e.name]);
      } else {
        show = !hidden.has(e.name);
        if (moves[e.name]) to.set(...moves[e.name]);
      }
      e.from.copy(e.offset);
      e.to.copy(to);
      e.animMove = !e.from.equals(e.to);
      // a modified part appears where its V18 original currently is, then travels with it
      if (e.kind === 'mod' && show && !e.show) { const orig = objects.get(e.name); if (orig) { e.offset.copy(orig.offset); e.from.copy(orig.offset); e.animMove = !e.from.equals(e.to); } }
      const visible = show && layerOn(e) && !(pilot && (e.layer === 'keepouts' || PILOT_HIDE.test(e.name)));
      if (visible && !e.obj.visible) { e.obj.visible = true; setOpacity(e, 0); e.fade = [0, 1]; }
      else if (!visible && e.obj.visible) e.fade = [e.opacity, 0];
      else e.fade = null;
      e.show = show;
    }
    const c1 = new THREE.Vector3(v ? Math.max(405, v.length_mm / 2) : 405, 0, 0);
    spanX = v ? v.length_mm : 810;
    if (ghost) ghost.visible = false;
    if (lastView === 'cockpit') setTimeout(() => frame('cockpit', 0), (ms || 0) + 30);
    else frame(lastView, ms ? ms * 0.95 : 0, c1.x, spanX);
    if (ms) { anim = { t0: performance.now(), ms, c0: center.clone(), c1 }; request(); }
    else { anim = { c0: center.clone(), c1 }; stepAnim(1); finishAnim(); anim = null; }
    sun.target.position.set(c1.x, 0, 0);
    grid.position.x = shadowFloor.position.x = c1.x;
  }

  function setLayer(layer, visible) {
    state.layers[layer] = visible;
    for (const e of all) if (e.layer === layer) e.obj.visible = visible && e.show;
    request();
  }
  function setCut(on) {
    state.cut = on;
    for (const e of all) {
      if (!['skin', 'controls'].includes(e.layer)) continue;
      e.obj.traverse((m) => { if (m.isMesh) { m.material.clippingPlanes = on ? [clipStarboard] : []; m.material.needsUpdate = true; } });
    }
    request();
  }
  function setGhost(on) {
    state.ghost = on;
    if (on && !ghost) buildGhost();
    if (ghost) ghost.visible = on && !anim;
    request();
  }
  function setMarkers({ cg, rotorX, np }) {
    if (cg) cgGroup.position.set(cg[0], cg[1], Math.max(cg[2], 0) + 40);
    if (rotorX !== undefined) rotorBar.position.x = rotorX;
    if (np) { npBand.scale.x = Math.max(np[1] - np[0], 2); npBand.position.x = (np[0] + np[1]) / 2; }
    request();
  }
  function setMarkersVisible(on) { markers.visible = on; request(); }

  // ----- picking -----
  const ray = new THREE.Raycaster();
  let selected = null;
  function highlight(name) {
    const paint = (e, hex) => e?.obj.traverse((m) => { if (m.isMesh && m.material.emissive) m.material.emissive.setHex(hex); });
    if (selected) paint(selected, 0x000000);
    selected = null;
    if (name) {
      const vmap = state.variant ? vobjects.get(state.variant) : null;
      selected = (vmap && vmap.get(name)) || objects.get(name) || null;
    }
    if (selected) paint(selected, 0x6a430a);
    request();
  }
  let down = null;
  canvas.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
    const r = canvas.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const vis = all.filter((x) => x.obj.visible).map((x) => x.obj);
    const inv = root.matrixWorld.clone().invert();
    const hits = ray.intersectObjects(vis, true).filter((h) => !state.cut || h.point.clone().applyMatrix4(inv).y <= 0.5);
    let name = null;
    for (const h of hits) {
      let o = h.object;
      while (o && !o.userData.partName) o = o.parent;
      if (o) { name = o.userData.partName; break; }
    }
    highlight(name);
    onPick?.(name);
  });

  function snapshot() {
    renderer.render(scene, camera);
    return canvas.toDataURL('image/png');
  }

  return {
    objects, frame, request, resize, setLayer, setCut, setMarkers, setMarkersVisible, setGhost, select: highlight, snapshot,
    setVariant, preload: loadVariant,
    get variant() { return state.variant; },
    get pilot() { return pilot; },
    get busy() { return !!anim || !!camTween; },
    setExplode(f) { state.explode = f; applyTransforms(); },
    setDeflection(key, deg) { state.deflect[key] = deg; applyTransforms(); },
    setShifts(s) { Object.assign(state.shifts, s); applyTransforms(); },
  };
}
