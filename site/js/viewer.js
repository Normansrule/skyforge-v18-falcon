// Three.js viewer for the V18 assembly. Works in V18 coordinates (mm, +X aft, +Y starboard, +Z up)
// inside a root group that is rotated so that V18 +Z is screen-up.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export async function createViewer(canvas, { parts, hinges, onPick }) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.localClippingEnabled = true;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, 5, 20000);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = !reduceMotion;
  controls.dampingFactor = 0.12;

  scene.add(new THREE.HemisphereLight(0xf2f4f6, 0x5a6470, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(-600, 1400, 900);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xdfe7ef, 0.6);
  fill.position.set(900, 300, -800);
  scene.add(fill);

  const root = new THREE.Group();
  root.rotation.x = -Math.PI / 2; // V18 +Z -> screen up, +Y -> toward the viewer's left/right
  scene.add(root);

  // ground disc under the wheels (V18 wheels bottom at z=-127)
  const ground = new THREE.Mesh(new THREE.CircleGeometry(900, 64),
    new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.06, depthWrite: false }));
  ground.position.set(405, 0, -128);
  root.add(ground);

  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  const [v18, repo] = await Promise.all([loader.loadAsync('models/v18.glb'), loader.loadAsync('models/repo_parts.glb')]);

  const meta = new Map(parts.map((p) => [p.name, p]));
  const objects = new Map(); // name -> { obj, base: Vector3, layer, group }
  // world space: the root is rotated so V18 +Y (starboard) points along world -Z; keep world z >= 0 = V18 port half
  const clipStarboard = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const center = new THREE.Vector3(405, 0, 0);

  function register(gltf, isRepo) {
    const holder = new THREE.Group();
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const name = isRepo ? o.name.replace(/_\d+$/, '') : (meta.has(o.name) ? o.name : o.parent?.name);
      o.material = o.material.clone();
      o.material.side = THREE.DoubleSide;
      o.userData.partName = isRepo ? o.name : name;
    });
    for (const child of [...gltf.scene.children]) {
      const name = child.name;
      const m = meta.get(name);
      const layer = isRepo ? 'repo' : m?.layer ?? 'skin';
      const group = isRepo ? 'body' : m?.group ?? 'body';
      const pivot = new THREE.Group();
      pivot.name = name;
      pivot.add(child);
      holder.add(pivot);
      // control surfaces rotate about their hinge axis: put the pivot on the hinge line
      if (hinges[name]) {
        const hp = new THREE.Vector3(...hinges[name].point);
        pivot.position.copy(hp);
        child.position.sub(hp);
      }
      const box = new THREE.Box3().setFromObject(child);
      const c = box.getCenter(new THREE.Vector3());
      if (hinges[name]) c.add(pivot.position);
      objects.set(name, { obj: pivot, base: pivot.position.clone(), centroid: c, layer, group, name });
    }
    root.add(holder);
  }
  register(v18, false);
  register(repo, true);

  // ----- markers -----
  const markers = new THREE.Group();
  root.add(markers);
  const amber = new THREE.Color('#E5A34E');
  const cgBall = new THREE.Mesh(new THREE.SphereGeometry(10, 32, 16), new THREE.MeshStandardMaterial({ color: amber, roughness: 0.4, depthTest: false }));
  cgBall.renderOrder = 10;
  const cgStem = new THREE.Mesh(new THREE.CylinderGeometry(1.2, 1.2, 160, 8), new THREE.MeshBasicMaterial({ color: amber, depthTest: false, transparent: true, opacity: 0.85 }));
  cgStem.rotation.x = Math.PI / 2;
  cgStem.renderOrder = 10;
  const cgGroup = new THREE.Group();
  cgGroup.add(cgBall, cgStem);
  cgStem.position.z = -80;
  markers.add(cgGroup);
  const rotorBar = new THREE.Mesh(new THREE.BoxGeometry(3, 560, 3), new THREE.MeshBasicMaterial({ color: '#3F6E9E', depthTest: false }));
  rotorBar.renderOrder = 9;
  rotorBar.position.z = 34;
  markers.add(rotorBar);
  const npBand = new THREE.Mesh(new THREE.BoxGeometry(1, 1020, 1.5), new THREE.MeshBasicMaterial({ color: '#2F7D5B', transparent: true, opacity: 0.16, depthWrite: false }));
  npBand.position.z = 31;
  markers.add(npBand);

  // ----- camera framing -----
  function frame(view = 'three-quarter') {
    const target = new THREE.Vector3(405, 0, -10).applyMatrix4(root.matrixWorld);
    controls.target.copy(target);
    const v = { 'three-quarter': [-700, 820, 1050], top: [0, 1700, 1], side: [0, 120, 1500], front: [-1500, 200, 0] }[view];
    const k = camera.aspect < 1.25 ? Math.pow(1.25 / camera.aspect, 0.85) : 1; // back off on tall/narrow screens
    camera.position.set(target.x + v[0] * k, target.y + v[1] * k, target.z + v[2] * k);
    controls.update();
    request();
  }

  // ----- render on demand -----
  let pending = false;
  function request() {
    if (pending) return;
    pending = true;
    requestAnimationFrame(() => {
      pending = false;
      if (controls.update()) request();
      renderer.render(scene, camera);
    });
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
  frame();
  let lastAspect = camera.aspect;
  new ResizeObserver(() => { if (Math.abs(camera.aspect - lastAspect) > 0.2) { lastAspect = camera.aspect; frame(); } }).observe(canvas);

  // ----- state -----
  const state = { explode: 0, deflect: { FLAP: 0, ELEVON: 0 }, shifts: { wing: 0, rotor: 0, battery: 0, avionics: 0 }, cut: false, layers: {} };
  const AVIONICS = new Set(['KEEP_OUT_FC_54x34x24', 'KEEP_OUT_VTX_42x26x14', 'KEEP_OUT_EDF_ESC_73x30x12_plus_margin']);
  function applyTransforms() {
    for (const o of objects.values()) {
      const p = o.base.clone();
      let dx = 0;
      if (o.group === 'wing') dx += state.shifts.wing;
      if (o.group === 'rotor') dx += state.shifts.wing + state.shifts.rotor;
      if (o.group === 'battery') dx += state.shifts.battery;
      if (AVIONICS.has(o.name)) dx += state.shifts.avionics;
      p.x += dx;
      if (state.explode > 0) {
        const dir = o.centroid.clone().sub(center);
        dir.x *= 0.35;
        p.addScaledVector(dir, state.explode * 0.9);
        if (o.layer === 'structure' || o.layer === 'hardware') p.z -= state.explode * 120;
        if (o.layer === 'keepouts' || o.layer === 'fittings') p.z += state.explode * 90;
      }
      o.obj.position.copy(p);
      const key = o.name.startsWith('FLAP_') ? 'FLAP' : o.name.startsWith('ELEVON_') ? 'ELEVON' : null;
      if (key && hinges[o.name]) {
        const d = new THREE.Vector3(...hinges[o.name].dir).normalize();
        o.obj.quaternion.setFromAxisAngle(d, THREE.MathUtils.degToRad(state.deflect[key]));
      }
    }
    request();
  }
  function setLayer(layer, visible) {
    state.layers[layer] = visible;
    for (const o of objects.values()) if (o.layer === layer) o.obj.visible = visible;
    request();
  }
  function setCut(on) {
    state.cut = on;
    for (const o of objects.values()) {
      if (!['skin', 'controls'].includes(o.layer)) continue;
      o.obj.traverse((m) => { if (m.isMesh) { m.material.clippingPlanes = on ? [clipStarboard] : []; m.material.needsUpdate = true; } });
    }
    request();
  }
  function setMarkers({ cg, rotorX, np }) {
    if (cg) cgGroup.position.set(cg[0], cg[1], Math.max(cg[2], 0) + 48);
    if (rotorX !== undefined) rotorBar.position.x = rotorX;
    if (np) { npBand.scale.x = Math.max(np[1] - np[0], 2); npBand.position.x = (np[0] + np[1]) / 2; }
    request();
  }

  // ----- picking -----
  const ray = new THREE.Raycaster();
  let selected = null;
  function highlight(name) {
    if (selected) selected.obj.traverse((m) => { if (m.isMesh && m.material.emissive) m.material.emissive.setHex(0x000000); });
    selected = name ? objects.get(name) : null;
    if (selected) selected.obj.traverse((m) => { if (m.isMesh && m.material.emissive) m.material.emissive.setHex(0x5a3a08); });
    request();
  }
  let down = null;
  canvas.addEventListener('pointerdown', (e) => { down = [e.clientX, e.clientY]; });
  canvas.addEventListener('pointerup', (e) => {
    if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
    const r = canvas.getBoundingClientRect();
    ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const vis = [];
    for (const o of objects.values()) if (o.obj.visible) vis.push(o.obj);
    const hits = ray.intersectObjects(vis, true).filter((h) => !state.cut || h.point.clone().applyMatrix4(root.matrixWorld.clone().invert()).y <= 0.5);
    let name = null;
    for (const h of hits) {
      let o = h.object;
      while (o && !objects.has(o.name)) o = o.parent;
      if (o) { name = o.name; break; }
    }
    highlight(name);
    onPick?.(name);
  });

  return {
    objects, frame, request, resize, setLayer, setCut, setMarkers, select: highlight,
    setExplode(f) { state.explode = f; applyTransforms(); },
    setDeflection(key, deg) { state.deflect[key] = deg; applyTransforms(); },
    setShifts(s) { Object.assign(state.shifts, s); applyTransforms(); },
  };
}
