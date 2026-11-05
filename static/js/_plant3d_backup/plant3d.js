/* Prody plant in 3D (Three.js, vendored). Progressive enhancement over the server-rendered SVG.
 *   import { mount, update } from '/static/js/plant3d.js'
 *   mount(el, state)   el: any element (usually <div class="plant3d">); state: plant_state()/state_3d() dict
 *   update(el, state)  rebuild an already-mounted plant with a new state (e.g. live preview)
 * Every .plant3d[data-plant] on the page (including ones inserted later) is mounted automatically.
 * Light always comes from the top-left; the plant turns, the light and sill do not. */
import * as THREE from '../vendor/three.module.min.js';

const C = { cream: '#F4EEE2', green: '#2F5D46', terra: '#C46A43', olive: '#B3AA7C' };
const POTS = {
  pot_terracotta: ['#C46A43', '#B35B36', '#2B241E', null, 0.92],
  pot_cream: ['#EFE7D8', '#E2D7C3', '#2B241E', 'stripes', 0.3],
  pot_speckle: ['#E6D6B8', '#D8C6A4', '#2B241E', 'speckle', 0.45],
  pot_sage: ['#9DB59A', '#86A083', '#22301F', 'drip', 0.28],
  pot_wave: ['#F2ECE0', '#E5DCCB', '#2B241E', 'wave', 0.32],
  pot_basket: ['#D2B48A', '#BE9C6E', '#2B241E', 'weave', 0.95],
  pot_forest: ['#2F5D46', '#264D3A', '#F4EEE2', 'glaze', 0.18],
  pot_kintsugi: ['#3A3A36', '#2E2E2A', '#F4EEE2', 'gold', 0.35],
};
const reduce = matchMedia('(prefers-reduced-motion: reduce)');
const U = 0.011;                     // SVG units -> world units (pot is ~0.9 tall)
const POT_H = 0.9, POT_RT = 0.6, POT_RB = 0.46, SOIL_Y = 0.84;

// ---------------------------------------------------------------- utils
function rng(seed) { let a = (seed * 7919 + 13) >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const lerp = (a, b, t) => a + (b - a) * t;
function col(hex, droop) { return new THREE.Color(hex).lerp(new THREE.Color(C.olive), droop * 0.75); }
function canvas(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; }
function tex(c, srgb = true, repeat = false) {
  const t = new THREE.CanvasTexture(c); if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4; if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}

// ---------------------------------------------------------------- shared renderer
let R = null, glOK = null;
function renderer() {
  if (R || glOK === false) return R;
  try {
    const r = new THREE.WebGLRenderer({ antialias: true, alpha: true, premultipliedAlpha: false, powerPreference: 'high-performance' });
    r.setClearColor(0x000000, 0);
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.05;
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    R = r; glOK = true;
  } catch (e) { glOK = false; }
  return R;
}
const live = new Set();
let raf = 0, last = 0;
const io = 'IntersectionObserver' in window ? new IntersectionObserver(es => {
  for (const e of es) { const p = e.target.__plant3d; if (p) { p.visible = e.isIntersecting; p.dirty = true; } }
  kick();
}, { rootMargin: '80px' }) : null;
document.addEventListener('visibilitychange', () => { if (!document.hidden) kick(); });
function kick() { if (!raf && !document.hidden) raf = requestAnimationFrame(loop); }
function loop(now) {
  raf = 0; if (document.hidden) return;
  const dt = Math.min(0.05, last ? (now - last) / 1000 : 0.016); last = now;
  let need = false;
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  for (const p of live) {
    if (!p.el.isConnected) { destroy(p); continue; }
    if (!p.visible) continue;
    const animating = p.tick(dt, now / 1000);
    if (animating || p.dirty) draw(p, dpr);
    need = need || animating;
  }
  if (need) raf = requestAnimationFrame(loop); else last = 0;
}
function draw(p, dpr) {
  const rect = p.el.getBoundingClientRect();
  const w = Math.max(1, Math.round(rect.width * dpr)), h = Math.max(1, Math.round(rect.height * dpr));
  if (!rect.width || !rect.height) return;
  const gl = R.domElement, size = R.getSize(new THREE.Vector2());
  if (size.x < w || size.y < h) R.setSize(Math.max(size.x, w), Math.max(size.y, h), false);
  const H = R.domElement.height;
  if (p.cv.width !== w || p.cv.height !== h) { p.cv.width = w; p.cv.height = h; }
  p.camera.aspect = w / h; p.camera.updateProjectionMatrix();
  R.setViewport(0, H - h, w, h); R.setScissor(0, H - h, w, h); R.setScissorTest(true);
  R.clear(); R.render(p.scene, p.camera);
  p.ctx.clearRect(0, 0, w, h); p.ctx.drawImage(gl, 0, 0, w, h, 0, 0, w, h);
  p.dirty = false;
}
function destroy(p) {
  live.delete(p); io && io.unobserve(p.el);
  p.scene.traverse(o => { o.geometry && o.geometry.dispose(); const m = o.material; if (m) [].concat(m).forEach(mm => { for (const k in mm) if (mm[k] && mm[k].isTexture) mm[k].dispose(); mm.dispose(); }); });
}

// ---------------------------------------------------------------- textures
const texCache = {};
function woodTex(kind) {
  if (texCache[kind]) return texCache[kind];
  const [c, x] = canvas(1024, 512), r = rng(kind === 'desk' ? 77 : 41);
  const base = kind === 'desk' ? ['#A87A52', '#8E6340'] : ['#C9A47A', '#B48A60'];
  const g = x.createLinearGradient(0, 0, 0, 512); g.addColorStop(0, base[0]); g.addColorStop(1, base[1]);
  x.fillStyle = g; x.fillRect(0, 0, 1024, 512);
  for (let i = 0; i < 140; i++) {           // grain lines
    const y0 = r() * 512, amp = 2 + r() * 6, f = 0.004 + r() * 0.01, ph = r() * 6;
    x.strokeStyle = `rgba(${kind === 'desk' ? '70,42,22' : '110,74,42'},${0.08 + r() * 0.22})`; x.lineWidth = 0.6 + r() * 2.2;
    x.beginPath(); for (let px = 0; px <= 1024; px += 8) { const py = y0 + Math.sin(px * f + ph) * amp + Math.sin(px * f * 3.1) * amp * 0.3; px ? x.lineTo(px, py) : x.moveTo(px, py); } x.stroke();
  }
  for (let k = 0; k < 2; k++) {             // knots
    const kx = 150 + r() * 700, ky = 80 + r() * 350;
    for (let j = 9; j > 0; j--) { x.strokeStyle = `rgba(90,58,32,${0.08 + 0.03 * (9 - j)})`; x.lineWidth = 1.2; x.beginPath(); x.ellipse(kx, ky, j * 5.5, j * 2.2, 0, 0, 7); x.stroke(); }
  }
  for (let i = 0; i < 60; i++) {            // wear: light scuffs + a few dents
    x.strokeStyle = `rgba(255,240,220,${0.05 + r() * 0.1})`; x.lineWidth = 0.6;
    const sx = r() * 1024, sy = r() * 512; x.beginPath(); x.moveTo(sx, sy); x.lineTo(sx + 10 + r() * 40, sy + (r() - 0.5) * 4); x.stroke();
  }
  const wear = x.createLinearGradient(0, 440, 0, 512); wear.addColorStop(0, 'rgba(255,236,210,0)'); wear.addColorStop(1, 'rgba(255,236,210,.18)');
  x.fillStyle = wear; x.fillRect(0, 440, 1024, 72);   // front edge rubbed lighter
  const t = tex(c, true, true); texCache[kind] = t; return t;
}
function contactTex() {
  if (texCache.contact) return texCache.contact;
  const [c, x] = canvas(256, 256), g = x.createRadialGradient(128, 128, 10, 128, 128, 128);
  g.addColorStop(0, 'rgba(20,14,8,.6)'); g.addColorStop(0.45, 'rgba(20,14,8,.25)'); g.addColorStop(1, 'rgba(20,14,8,0)');
  x.fillStyle = g; x.fillRect(0, 0, 256, 256); return (texCache.contact = tex(c));
}
function leafTex() {
  if (texCache.leaf) return texCache.leaf;
  const [c, x] = canvas(256, 256);      // grey-scale vein map (u = length, v = width), tinted by material colour
  x.fillStyle = '#d8d8d8'; x.fillRect(0, 0, 256, 256);
  const g = x.createLinearGradient(0, 0, 0, 256); g.addColorStop(0, 'rgba(0,0,0,.12)'); g.addColorStop(0.5, 'rgba(255,255,255,.25)'); g.addColorStop(1, 'rgba(0,0,0,.12)');
  x.fillStyle = g; x.fillRect(0, 0, 256, 256);
  x.strokeStyle = 'rgba(255,255,235,.85)'; x.lineWidth = 5; x.beginPath(); x.moveTo(0, 128); x.lineTo(256, 128); x.stroke();
  x.lineWidth = 2; x.strokeStyle = 'rgba(255,255,230,.5)';
  for (let i = 1; i < 9; i++) { const u = i * 27; for (const s of [-1, 1]) { x.beginPath(); x.moveTo(u, 128); x.quadraticCurveTo(u + 22, 128 + s * 50, u + 40, 128 + s * 118); x.stroke(); } }
  return (texCache.leaf = tex(c));
}
function potTex(key, mood, accs) {
  const [body, , face, pat] = POTS[key] || POTS.pot_terracotta;
  const W = 1024, Hh = 512, [c, x] = canvas(W, Hh), r = rng(11);
  x.fillStyle = body; x.fillRect(0, 0, W, Hh);
  // clay grain
  for (let i = 0; i < 2500; i++) { x.fillStyle = `rgba(${r() < .5 ? '0,0,0' : '255,255,255'},${r() * 0.05})`; x.fillRect(r() * W, r() * Hh, 2, 2); }
  if (pat === 'stripes') { x.fillStyle = 'rgba(47,93,70,.6)'; x.fillRect(0, 70, W, 14); x.fillRect(0, 360, W, 14); }
  if (pat === 'speckle') for (let i = 0; i < 700; i++) { x.fillStyle = 'rgba(122,98,71,.55)'; x.beginPath(); x.arc(r() * W, r() * Hh, 1.5 + r() * 3, 0, 7); x.fill(); }
  if (pat === 'drip') { x.fillStyle = '#6F8E6C'; x.beginPath(); x.moveTo(0, 0); x.lineTo(W, 0); for (let px = W; px >= 0; px -= 32) x.lineTo(px, 60 + r() * 70); x.closePath(); x.fill(); }
  if (pat === 'wave') { x.strokeStyle = C.terra; x.lineWidth = 9; for (const y of [130, 380]) { x.beginPath(); for (let px = 0; px <= W; px += 4) x.lineTo(px, y + Math.sin(px / 32) * 14); x.stroke(); } }
  if (pat === 'weave') {
    for (let y = 0; y < Hh; y += 32) for (let px = 0; px < W; px += 40) {
      const o = ((y / 32) % 2) * 20; x.fillStyle = 'rgba(164,132,90,.55)'; x.fillRect(px + o, y + 4, 30, 24);
      x.fillStyle = 'rgba(255,240,210,.18)'; x.fillRect(px + o, y + 4, 30, 6);
    }
  }
  if (pat === 'gold') {
    x.strokeStyle = '#D6B058'; x.lineWidth = 6; x.lineJoin = 'round';
    for (const path of [[[300, 0], [340, 120], [310, 220], [360, 300], [350, 512]], [[700, 0], [670, 150], [720, 230], [680, 330], [710, 512]], [[480, 512], [520, 420], [600, 390]]]) {
      x.beginPath(); path.forEach(([a, b], i) => i ? x.lineTo(a, b) : x.moveTo(a, b)); x.stroke();
    }
  }
  // face, centred at u=.5 (the front)
  const cx = W / 2, ey = 200, my = 290;
  x.strokeStyle = x.fillStyle = face; x.lineCap = 'round'; x.lineWidth = 9;
  if (mood === 'thirsty') {
    x.beginPath(); x.moveTo(cx - 70, ey); x.quadraticCurveTo(cx - 48, ey + 16, cx - 26, ey); x.moveTo(cx + 26, ey); x.quadraticCurveTo(cx + 48, ey + 16, cx + 70, ey); x.stroke();
    x.beginPath(); x.moveTo(cx - 30, my + 12); x.quadraticCurveTo(cx, my - 12, cx + 30, my + 12); x.stroke();
    x.fillStyle = '#8FB3C4'; x.beginPath(); x.moveTo(cx + 110, 120); x.quadraticCurveTo(cx + 128, 150, cx + 110, 162); x.quadraticCurveTo(cx + 92, 150, cx + 110, 120); x.fill();
  } else {
    for (const s of [-1, 1]) { x.beginPath(); x.ellipse(cx + s * 50, ey, 13, 16, 0, 0, 7); x.fill(); }
    x.fillStyle = 'rgba(255,255,255,.8)'; for (const s of [-1, 1]) { x.beginPath(); x.arc(cx + s * 50 + 5, ey - 6, 4.5, 0, 7); x.fill(); }
    const curve = mood === 'happy' ? 26 : 10;
    x.beginPath(); x.moveTo(cx - 28, my); x.quadraticCurveTo(cx, my + curve, cx + 28, my); x.stroke();
    if (mood === 'happy') { x.fillStyle = 'rgba(233,151,122,.45)'; for (const s of [-1, 1]) { x.beginPath(); x.ellipse(cx + s * 98, my - 8, 26, 15, 0, 0, 7); x.fill(); } }
  }
  if (accs.has('acc_sticker')) {           // sticker decal, lower right of the face
    x.save(); x.translate(cx + 130, 360); x.rotate(-0.14);
    x.fillStyle = '#F8F3E8'; x.strokeStyle = C.green; x.lineWidth = 4; x.beginPath(); x.roundRect(-44, -30, 88, 62, 16); x.fill(); x.stroke();
    x.fillStyle = '#8FB3C4'; x.fillRect(-20, -12, 36, 24); x.strokeRect(-20, -12, 36, 24);
    x.beginPath(); x.moveTo(16, -4); x.lineTo(34, -16); x.stroke(); x.restore();
  }
  return tex(c);
}
function backdropTex(key) {
  if (texCache[key]) return texCache[key];
  const [c, x] = canvas(1024, 1024);
  if (key === 'scene_window') {
    x.fillStyle = '#EEE6D6'; x.fillRect(0, 0, 1024, 1024);
    x.fillStyle = '#F8F4EC'; x.fillRect(180, 60, 664, 840);
    const sky = x.createLinearGradient(0, 100, 0, 860); sky.addColorStop(0, '#E4EDE8'); sky.addColorStop(1, '#CFDDD2');
    x.fillStyle = sky; x.fillRect(220, 100, 584, 760);
    x.fillStyle = '#BFD2C1'; x.beginPath(); x.moveTo(220, 640); x.quadraticCurveTo(420, 560, 560, 620); x.quadraticCurveTo(700, 660, 804, 600); x.lineTo(804, 860); x.lineTo(220, 860); x.fill();
    x.fillStyle = '#F8F4EC'; x.fillRect(500, 100, 24, 760); x.fillRect(220, 470, 584, 24);
  } else if (key === 'scene_desk') {
    x.fillStyle = '#E8E2D5'; x.fillRect(0, 0, 1024, 1024);
    x.fillStyle = '#F7F3EA'; x.strokeStyle = '#CDBFA6'; x.lineWidth = 12; x.fillRect(120, 180, 240, 300); x.strokeRect(120, 180, 240, 300);
    x.fillStyle = '#A9BFA2'; x.beginPath(); x.moveTo(150, 430); x.lineTo(210, 330); x.lineTo(250, 380); x.lineTo(290, 350); x.lineTo(330, 430); x.fill();
    [[C.green, 700, 820], [C.terra, 714, 870], ['#D9C7A3', 690, 920]].forEach(([f, px, py]) => { x.fillStyle = f; x.fillRect(px, py, 190, 46); });
  } else {
    const g = x.createLinearGradient(0, 0, 0, 1024); g.addColorStop(0, '#EBF1E6'); g.addColorStop(1, '#DCE6D5');
    x.fillStyle = g; x.fillRect(0, 0, 1024, 1024);
    x.strokeStyle = 'rgba(247,244,236,.95)'; x.lineWidth = 14;
    for (let px = -60; px < 1100; px += 170) { x.beginPath(); x.moveTo(px, 1024); x.lineTo(px, 260); x.quadraticCurveTo(px + 85, 140, px + 170, 260); x.stroke(); }
    x.fillStyle = '#A9C2A3'; for (const px of [140, 420, 700, 900]) { x.beginPath(); x.ellipse(px, 300 + (px % 3) * 30, 22, 40, 0, 0, 7); x.fill(); }
  }
  return (texCache[key] = tex(c));
}

// ---------------------------------------------------------------- geometry builders
function taperedTube(curve, r0, r1, seg = 40, rad = 10) {
  const geo = new THREE.TubeGeometry(curve, seg, 1, rad, false), pos = geo.attributes.position, p = new THREE.Vector3(), v = new THREE.Vector3();
  for (let i = 0; i <= seg; i++) {
    const t = i / seg; curve.getPointAt(t, p); const r = lerp(r0, r1, Math.pow(t, 0.8));
    for (let j = 0; j <= rad; j++) { const k = i * (rad + 1) + j; v.fromBufferAttribute(pos, k).sub(p).multiplyScalar(r).add(p); pos.setXYZ(k, v.x, v.y, v.z); }
  }
  geo.computeVertexNormals(); return geo;
}
// Leaf along +X, width along Z, cupped up (+Y) and arched.
function leafGeo(len, wid, cup = 0.35, arch = 0.18) {
  const nu = 14, nv = 6, P = [], UV = [], I = [];
  for (let i = 0; i <= nu; i++) {
    const u = i / nu, w = wid * Math.pow(Math.sin(Math.PI * Math.pow(u, 0.75)), 0.9);
    for (let j = 0; j <= nv; j++) {
      const v = j / nv * 2 - 1, z = v * w;
      P.push(u * len, -arch * len * u * u + cup * wid * v * v * (0.4 + 0.6 * Math.sin(Math.PI * u)) , z);
      UV.push(u, (v + 1) / 2);
    }
  }
  for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++) { const a = i * (nv + 1) + j, b = a + nv + 1; I.push(a, b, a + 1, b, b + 1, a + 1); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(UV, 2)); g.setIndex(I); g.computeVertexNormals(); return g;
}
function leafMat(color) {
  const m = new THREE.MeshStandardMaterial({ color, map: leafTex(), roughness: 0.62, metalness: 0, side: THREE.DoubleSide, emissive: color.clone().multiplyScalar(0.12) });
  // cheap translucency: light that hits the back face bleeds through, tinted yellow-green
  m.onBeforeCompile = s => {
    s.fragmentShader = s.fragmentShader.replace('#include <dithering_fragment>',
      '#include <dithering_fragment>\n if(!gl_FrontFacing) gl_FragColor.rgb += vec3(0.05,0.08,0.01);');
  };
  return m;
}

// ---------------------------------------------------------------- the plant build
function build(p, st) {
  const scene = new THREE.Scene(), r = rng(st.seed || 1);
  const g = +st.growth || 0, idx = st.stage_idx | 0, vit = st.vitality ?? 1, droop = 1 - vit;
  const accs = new Set(st.accs || []);
  p.sway = []; p.anim = []; p.droop = droop;

  // lights: daylight from the top-left (fixed relative to the camera)
  const hemi = new THREE.HemisphereLight(0xFBF4E6, 0x8C7458, 0.9); scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFF1DC, 3.0);
  sun.position.set(-3.2, 5.2, 2.6); sun.target.position.set(0, 0.8, 0);
  sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02; sun.shadow.radius = 2;
  Object.assign(sun.shadow.camera, { left: -2.6, right: 2.6, top: 3.4, bottom: -1.2, near: 0.5, far: 14 });
  scene.add(sun, sun.target);
  const rim = new THREE.DirectionalLight(0xDDE8F0, 0.35); rim.position.set(2.5, 2, -3); scene.add(rim);

  // surface: windowsill (default/window), desk, or greenhouse bench
  const sk = st.scene || '';
  const surf = new THREE.Mesh(new THREE.BoxGeometry(7, 0.16, 2.2),
    new THREE.MeshStandardMaterial({ map: woodTex(sk === 'scene_desk' ? 'desk' : 'sill'), roughness: 0.72, bumpMap: woodTex(sk === 'scene_desk' ? 'desk' : 'sill'), bumpScale: 0.6 }));
  surf.position.set(0, -0.08, 0.35); surf.receiveShadow = true; scene.add(surf);
  // slight lip / bevel strip on the front edge for a real sill silhouette
  const lip = new THREE.Mesh(new THREE.BoxGeometry(7, 0.06, 0.06), surf.material); lip.position.set(0, -0.19, 1.43); lip.receiveShadow = true; scene.add(lip);
  let bd = null;
  if (sk) {
    bd = new THREE.Mesh(new THREE.PlaneGeometry(7, 7), new THREE.MeshStandardMaterial({ map: backdropTex(sk), roughness: 1 }));
    bd.position.set(0, 2.6, -0.85); bd.receiveShadow = true; scene.add(bd);
  }
  const contact = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.5), new THREE.MeshBasicMaterial({ map: contactTex(), transparent: true, depthWrite: false, toneMapped: false }));
  contact.rotation.x = -Math.PI / 2; contact.position.y = 0.002; contact.renderOrder = 1; scene.add(contact);

  // turntable: pot + plant rotate together
  const turn = new THREE.Group(); scene.add(turn);
  const [body, rimC, faceC, pat, rough] = POTS[st.pot] || POTS.pot_terracotta;
  const glossy = rough < 0.5;
  const potMat = new THREE.MeshPhysicalMaterial({ map: potTex(st.pot, st.mood, accs), roughness: rough, metalness: 0,
    clearcoat: glossy ? 0.8 : 0, clearcoatRoughness: 0.25, sheen: pat === 'weave' ? 0.4 : 0 });
  if (pat === 'weave') { potMat.bumpMap = potMat.map; potMat.bumpScale = 3; }
  const prof = [new THREE.Vector2(0, 0), new THREE.Vector2(POT_RB - 0.04, 0), new THREE.Vector2(POT_RB, 0.04), new THREE.Vector2(POT_RT - 0.03, POT_H - 0.16), new THREE.Vector2(POT_RT - 0.03, POT_H - 0.14)];
  const potGeo = new THREE.LatheGeometry(prof, 64); potGeo.rotateY(Math.PI);
  { const ps = potGeo.attributes.position, uv = potGeo.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setY(i, Math.min(1, ps.getY(i) / (POT_H - 0.16))); }
  const pot = new THREE.Mesh(potGeo, potMat); pot.castShadow = pot.receiveShadow = true; turn.add(pot);
  const rimMat = new THREE.MeshPhysicalMaterial({ color: rimC, roughness: rough, clearcoat: glossy ? 0.8 : 0 });
  const rimGeo = new THREE.LatheGeometry([new THREE.Vector2(POT_RT - 0.08, POT_H - 0.02), new THREE.Vector2(POT_RT + 0.04, POT_H - 0.01), new THREE.Vector2(POT_RT + 0.05, POT_H - 0.2),
    new THREE.Vector2(POT_RT - 0.02, POT_H - 0.2)].reverse(), 64);
  const rimTop = new THREE.Mesh(rimGeo, rimMat); rimTop.castShadow = rimTop.receiveShadow = true; turn.add(rimTop);
  if (pat === 'gold') { const gl = new THREE.Mesh(new THREE.TorusGeometry(POT_RT + 0.045, 0.008, 6, 64), new THREE.MeshStandardMaterial({ color: '#D6B058', metalness: 1, roughness: 0.3 })); gl.rotation.x = Math.PI / 2; gl.position.y = POT_H - 0.12; turn.add(gl); }
  const soil = new THREE.Mesh(new THREE.CircleGeometry(POT_RT - 0.07, 48), new THREE.MeshStandardMaterial({ color: '#4E3B2C', roughness: 1, bumpMap: woodTex('sill'), bumpScale: 2 }));
  soil.rotation.x = -Math.PI / 2; soil.position.y = SOIL_Y; soil.receiveShadow = true; turn.add(soil);

  // plant hierarchy (sways at its base)
  const plant = new THREE.Group(); plant.position.y = SOIL_Y; turn.add(plant); p.plant = plant;
  const stemC = col('#4A7A4B', droop), stemMat = new THREE.MeshStandardMaterial({ color: stemC, roughness: 0.55 });
  const leafCols = ['#4E8052', '#5B9160', '#467548'].map(c => col(c, droop)), mats = leafCols.map(leafMat);
  const youngMat = leafMat(col('#7DB178', droop));
  const lean = (r() * 2 - 1) * 10 * U, side0 = r() < 0.5 ? -1 : 1;
  let tip = new THREE.Vector3(0, 0.05, 0), canopy = [];

  const addLeaf = (parent, pos, yaw, pitch, len, wid, mat) => {
    const piv = new THREE.Group(); piv.position.copy(pos); piv.rotation.set(0, yaw, 0);
    const inner = new THREE.Group(); inner.rotation.z = pitch - droop * 1.1; piv.add(inner);
    const m = new THREE.Mesh(leafGeo(len, wid, 0.35, 0.12 + droop * 0.4), mat); m.castShadow = true; m.receiveShadow = true; inner.add(m);
    parent.add(piv); p.sway.push({ o: inner, base: inner.rotation.z, ph: r() * 6.28, amp: 0.05 + r() * 0.05, axis: 'z' }); return piv;
  };
  const addFlower = (parent, pos, rad, petalHex) => {
    const fg = new THREE.Group(); fg.position.copy(pos);
    const pm = new THREE.MeshPhysicalMaterial({ color: col(petalHex, droop), roughness: 0.5, sheen: 1, sheenColor: new THREE.Color('#fff'), side: THREE.DoubleSide });
    for (let k = 0; k < 5; k++) { const pg = leafGeo(rad, rad * 0.42, 0.6, -0.1); const m = new THREE.Mesh(pg, pm); m.rotation.set(0, k * 1.2566 + r(), 0.45 + droop * 0.6); m.castShadow = true; fg.add(m); }
    const ctr = new THREE.Mesh(new THREE.SphereGeometry(rad * 0.3, 12, 8), new THREE.MeshStandardMaterial({ color: '#D9A04A', roughness: 0.8 })); ctr.scale.y = 0.6; fg.add(ctr);
    parent.add(fg); return fg;
  };

  if (idx === 0) {
    const seedM = new THREE.Mesh(new THREE.SphereGeometry(0.07, 16, 10), new THREE.MeshStandardMaterial({ color: '#9A7652', roughness: 0.7 }));
    seedM.scale.set(1, 0.65, 0.8); seedM.rotation.z = -0.3; seedM.position.y = 0.03; seedM.castShadow = true; plant.add(seedM);
    if (g > 0.02) {
      const c = new THREE.QuadraticBezierCurve3(new THREE.Vector3(0.02, 0, 0), new THREE.Vector3(0.01, 0.1, 0), new THREE.Vector3(0.06, 0.2, 0));
      plant.add(Object.assign(new THREE.Mesh(taperedTube(c, 0.018, 0.012, 12, 8), stemMat), { castShadow: true }));
      addLeaf(plant, c.getPoint(1), 0.3, 0.5, 0.16, 0.06, mats[0]); addLeaf(plant, c.getPoint(1), Math.PI + 0.3, 0.6, 0.11, 0.045, mats[1]);
      tip = c.getPoint(1).add(plant.position);
    } else tip = new THREE.Vector3(0, SOIL_Y + 0.08, 0);
  } else {
    let H = (idx > 1 ? 28 : 30) * U + g * 150 * U; H *= 1 - droop * 0.12;
    const stem = t => new THREE.Vector3(lean * Math.sin(Math.PI * t) * 0.7 + lean * 0.35 * t + side0 * droop * t * t * H * 0.5,
      H * t - droop * H * 0.55 * Math.max(0, t - 0.5) ** 2 * 1.3, Math.sin(t * 2.3 + r() * 0) * 0.04 * t);
    const curve = new THREE.CatmullRomCurve3(Array.from({ length: 10 }, (_, i) => stem(i / 9)));
    const w0 = (4.2 + g * 7) * U * 0.55;
    const sm = new THREE.Mesh(taperedTube(curve, w0, 0.012, 48, 12), stemMat); sm.castShadow = true; plant.add(sm);
    const tipL = curve.getPointAt(1); tip = tipL.clone().add(plant.position);

    // branches: one per course, alternating, spiralled around the stem
    const nb = idx < 2 ? 0 : Math.min(6, Math.max(1, Math.ceil((g - 0.15) * 7)));
    const mins = (st.branches || []).map(b => b.minutes); const mx = Math.max(1, ...mins, 1);
    for (let i = 0; i < nb; i++) {
      const t0 = nb > 1 ? 0.3 + 0.52 * (i / (nb - 1)) + (r() - 0.5) * 0.12 : 0.55;
      const s = side0 * (i % 2 ? -1 : 1), yaw = s > 0 ? -0.4 + i * 0.5 : Math.PI - 0.4 + i * 0.5;
      const cf = mins.length ? 0.8 + 0.4 * (mins[i % mins.length] / mx) : 1;
      const L = H * (0.58 - 0.22 * t0) * (0.82 + r() * 0.28) * cf * (0.7 + 0.3 * g), a = (34 + r() * 18) * Math.PI / 180;
      const bg = new THREE.Group(); bg.position.copy(curve.getPointAt(t0)); bg.rotation.y = yaw; plant.add(bg);
      const end = new THREE.Vector3(L * Math.cos(a), L * Math.sin(a) - droop * L * 0.75, 0);
      const bc = new THREE.QuadraticBezierCurve3(new THREE.Vector3(), new THREE.Vector3(L * 0.62 * Math.cos(a), L * 0.12, 0), end);
      const bm = new THREE.Mesh(taperedTube(bc, (2.4 + g * 2.6) * U * 0.5, 0.008, 16, 8), stemMat); bm.castShadow = true; bg.add(bm);
      p.sway.push({ o: bg, base: bg.rotation.y, ph: r() * 6.28, amp: 0.04, axis: 'y' });
      [0.45, 0.78].forEach((tt, k) => addLeaf(bg, bc.getPoint(tt), (k ? 1 : -1) * 0.9, 0.35, (20 + g * 12) * U * 1.2, (7.5 + g * 3.5) * U * 1.1, mats[(i + k) % 3]));
      const tipW = new THREE.Vector3();
      if (idx >= 4 && vit > 0.25) {
        addLeaf(bg, end, 0.5, 0.2, (13 + g * 6) * U * 1.2, (5 + g * 2) * U, mats[i % 3]);
        const fl = addFlower(bg, end.clone().add(new THREE.Vector3(0, 0.02, 0)), (7 + g * 3) * U * 1.3, i % 2 ? '#F4DCCB' : '#EFC3AE');
        fl.rotation.z = -0.6;
      } else addLeaf(bg, end, 0, 0.1, (22 + g * 10) * U * 1.2, (8 + g * 3.2) * U * 1.1, mats[i % 3]);
      if (idx >= 5 && i % 2 === 0) {
        const fm = new THREE.Mesh(new THREE.SphereGeometry(4.6 * U * 1.3, 18, 12), new THREE.MeshPhysicalMaterial({ color: col('#C2603A', droop), roughness: 0.35, clearcoat: 0.5 }));
        fm.position.copy(bc.getPoint(0.5)).add(new THREE.Vector3(0, -0.07, 0)); fm.castShadow = true; bg.add(fm);
      }
      canopy.push(tipW.copy(end).applyEuler(bg.rotation).add(bg.position).add(plant.position));
    }
    // leaves on the main stem
    if (idx === 1) {
      for (const s of [-1, 1]) addLeaf(plant, tipL, s > 0 ? 0.2 : Math.PI + 0.2, 0.55, (15 + g * 40) * U * 1.2, (7.5 + g * 12) * U * 1.1, mats[(s + 1) / 2]);
    } else {
      const nl = 3 + Math.floor(g * 6);
      for (let i = 0; i < nl; i++) {
        const t = 0.14 + 0.72 * i / Math.max(nl - 1, 1), len = (25 + g * 14) * (1 - 0.35 * t) * (0.88 + r() * 0.2) * U * 1.1;
        addLeaf(plant, curve.getPointAt(t), i * 2.4 + side0, 0.5 - 0.2 * t, len, len * 0.36, mats[i % 3]);
      }
      for (const s of [-1, 1]) addLeaf(plant, tipL, s > 0 ? 0.8 : Math.PI + 0.8, 0.9, (12 + g * 6) * U * 1.2, (4.6 + g * 2) * U, youngMat);
      if (idx >= 4 && vit > 0.25) addFlower(plant, tipL.clone().add(new THREE.Vector3(0, 0.02, 0)), (9 + g * 3) * U * 1.3, '#F4DCCB');
    }
  }
  if (!canopy.length) canopy = [tip.clone().add(new THREE.Vector3(-0.25, -0.15, 0)), tip.clone().add(new THREE.Vector3(0.25, -0.15, 0))];

  // ---- accessories
  const front = new THREE.Vector3(0, 0, 1);
  if (accs.has('acc_hat')) {
    const straw = new THREE.MeshStandardMaterial({ color: '#E0C690', roughness: 0.9, map: woodTex('sill') });
    const hat = new THREE.Group(); hat.position.copy(tip).sub(plant.position).add(new THREE.Vector3(0, 0.04, 0)); hat.rotation.z = -0.12;
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.19, 0.2, 0.012, 32), straw), crown = new THREE.Mesh(new THREE.SphereGeometry(0.1, 24, 12, 0, 6.29, 0, 1.57), straw);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.101, 0.101, 0.03, 32, 1, true), new THREE.MeshStandardMaterial({ color: C.green, roughness: 0.7 }));
    band.position.y = 0.02; [brim, crown, band].forEach(m => { m.castShadow = true; hat.add(m); }); plant.add(hat);
  }
  if (accs.has('acc_glasses')) {
    const gm = new THREE.MeshStandardMaterial({ color: faceC, roughness: 0.3, metalness: 0.4 }), gg = new THREE.Group();
    const vFace = 1 - 200 / 512, y = POT_H - 0.16 - (1 - vFace) * 0; // eye height on the body
    const ey = (POT_H - 0.16) * (1 - 200 / 512), rz = lerp(POT_RB, POT_RT - 0.03, (ey - 0.04) / (POT_H - 0.2)) + 0.03;
    for (const s of [-1, 1]) { const ring = new THREE.Mesh(new THREE.TorusGeometry(0.075, 0.008, 8, 32), gm); ring.position.set(s * 0.1, ey, rz); ring.rotation.y = s * 0.1; gg.add(ring);
      const lens = new THREE.Mesh(new THREE.CircleGeometry(0.072, 24), new THREE.MeshPhysicalMaterial({ color: '#fff', transparent: true, opacity: 0.18, roughness: 0.05 })); lens.position.copy(ring.position); gg.add(lens); }
    const bridge = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.006, 6, 12, Math.PI), gm); bridge.position.set(0, ey + 0.01, rz + 0.005); gg.add(bridge);
    gg.children.forEach(m => m.castShadow = true); turn.add(gg);
  }
  if (accs.has('acc_scarf')) {
    const knit = new THREE.MeshStandardMaterial({ color: C.terra, roughness: 0.95, bumpMap: woodTex('sill'), bumpScale: 1.5 });
    const sc = new THREE.Mesh(new THREE.TorusGeometry(POT_RT + 0.03, 0.045, 12, 64), knit); sc.rotation.x = Math.PI / 2; sc.scale.z = 1.4; sc.position.y = POT_H - 0.24; sc.castShadow = true; turn.add(sc);
    const tail = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.32, 0.03), knit); tail.position.set(0.36, POT_H - 0.42, POT_RT - 0.05); tail.rotation.set(-0.15, 0.55, -0.15); tail.castShadow = true; turn.add(tail);
  }
  if (accs.has('acc_lights')) {
    const [a, b] = [canopy.reduce((m, v) => v.x < m.x ? v : m), canopy.reduce((m, v) => v.x > m.x ? v : m)];
    a.y = Math.min(a.y, tip.y - 0.12); b.y = Math.min(b.y, tip.y - 0.12);
    const mid = a.clone().add(b).multiplyScalar(0.5); mid.y = Math.min(a.y, b.y) - 0.2; mid.z += 0.25;
    const wire = new THREE.CatmullRomCurve3([a.clone().sub(plant.position).setZ(0.15), mid.sub(plant.position), b.clone().sub(plant.position).setZ(0.15)]);
    plant.add(new THREE.Mesh(new THREE.TubeGeometry(wire, 40, 0.004, 5), new THREE.MeshStandardMaterial({ color: '#4A4A3E', roughness: 0.6 })));
    const bulbs = [];
    for (let i = 1; i < 9; i++) {
      const bm = new THREE.MeshStandardMaterial({ color: '#F6E2A8', emissive: '#F3C962', emissiveIntensity: 2, roughness: 0.3 });
      const bl = new THREE.Mesh(new THREE.SphereGeometry(0.022, 12, 8), bm); bl.position.copy(wire.getPoint(i / 9)).add(new THREE.Vector3(0, -0.02, 0)); plant.add(bl);
      const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: contactTex(), color: '#FFD98A', blending: THREE.AdditiveBlending, transparent: true, opacity: 0.3, depthWrite: false })); glow.scale.setScalar(0.12); glow.position.copy(bl.position); plant.add(glow);
      bulbs.push([bm, glow, i * 0.35]);
    }
    const pl = new THREE.PointLight('#FFD58A', 0.25, 1.5); pl.position.copy(wire.getPoint(0.5)); plant.add(pl);
    p.anim.push((t) => bulbs.forEach(([m, gl, d]) => { const k = 0.65 + 0.35 * Math.sin(t * 2.1 + d * 3); m.emissiveIntensity = 1 + 1.6 * k; gl.material.opacity = 0.18 + 0.2 * k; }));
  }
  if (accs.has('acc_butterfly')) {
    const [c2, x2] = canvas(128, 128); x2.fillStyle = C.terra; x2.beginPath(); x2.moveTo(0, 64); x2.bezierCurveTo(40, -10, 128, 0, 110, 60); x2.bezierCurveTo(128, 110, 40, 130, 0, 70); x2.fill();
    x2.fillStyle = '#E7B49A'; x2.beginPath(); x2.arc(80, 50, 12, 0, 7); x2.fill(); x2.strokeStyle = '#7A3A22'; x2.lineWidth = 3; x2.stroke();
    const wm = new THREE.MeshStandardMaterial({ map: tex(c2), transparent: true, alphaTest: 0.3, side: THREE.DoubleSide, roughness: 0.7 });
    const bf = new THREE.Group(), wg = new THREE.PlaneGeometry(0.12, 0.12); wg.translate(0.06, 0, 0); wg.rotateX(-Math.PI / 2);
    const L = new THREE.Mesh(wg, wm), Rw = new THREE.Mesh(wg, wm); Rw.scale.x = -1; [L, Rw].forEach(m => { m.castShadow = true; bf.add(m); });
    const bodyB = new THREE.Mesh(new THREE.CapsuleGeometry(0.008, 0.06, 4, 8), new THREE.MeshStandardMaterial({ color: '#2B241E' })); bodyB.rotation.x = Math.PI / 2; bf.add(bodyB);
    bf.rotation.y = Math.PI / 2; scene.add(bf);
    const home = canopy.reduce((m, v) => v.x > m.x ? v : m).clone().add(new THREE.Vector3(0.12, 0.15, 0.2));
    p.anim.push((t) => { const f = Math.sin(t * 14) * 0.9; L.rotation.z = f; Rw.rotation.z = -f;
      bf.position.set(home.x + Math.sin(t * 0.7) * 0.08, home.y + Math.sin(t * 1.3) * 0.05, home.z + Math.cos(t * 0.7) * 0.06); bf.rotation.y = Math.PI / 2 + Math.sin(t * 0.7) * 0.4; });
  }

  // camera framing: fit pot + plant
  const top = Math.max(tip.y + 0.25, ...canopy.map(v => v.y + 0.15), 1.4), bottom = -0.12, midY = (top + bottom) / 2;
  const cam = p.camera || new THREE.PerspectiveCamera(28, 0.8, 0.1, 50);
  const hgt = (top - bottom) * 1.08, dist = hgt / 2 / Math.tan(THREE.MathUtils.degToRad(cam.fov / 2)) / Math.min(1, cam.aspect * 1.25);
  cam.position.set(0, midY + dist * 0.22, dist); cam.lookAt(0, midY - 0.02, 0); p.camera = cam;
  p.theme = { hemi, sun, rim, surf: [surf.material], bd: bd && bd.material };
  p.scene = scene; p.turn = turn; applyTheme(p); p.dirty = true;
}

// ---------------------------------------------------------------- dark mode (html[data-theme=dark]), live
const isDark = () => document.documentElement.dataset.theme === 'dark';
function applyTheme(p) {
  const d = isDark(), T = p.theme; if (!T) return;
  // evening: dimmer, cooler daylight, still from the top-left; sill and backdrop dimmed like the SVG scene
  T.sun.color.set(d ? 0xC9D4EC : 0xFFF1DC); T.sun.intensity = d ? 1.6 : 3.0;
  T.hemi.color.set(d ? 0x8E9AB4 : 0xFBF4E6); T.hemi.groundColor.set(d ? 0x3A3026 : 0x8C7458); T.hemi.intensity = d ? 0.55 : 0.9;
  T.rim.color.set(d ? 0xF2C98A : 0xDDE8F0); T.rim.intensity = d ? 0.25 : 0.35;   // faint warm lamp glow from behind
  T.surf.forEach(m => m.color.set(d ? 0x8A8A92 : 0xFFFFFF));
  if (T.bd) T.bd.color.set(d ? 0x7E8494 : 0xFFFFFF);
  p.dirty = true;
}
new MutationObserver(() => { live.forEach(applyTheme); kick(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

// ---------------------------------------------------------------- public API
export function mount(el, state) {
  if (el.__plant3d) return update(el, state), el.__plant3d;
  if (!renderer()) return null;                       // no WebGL: keep the SVG
  state = state || JSON.parse(el.dataset.plant || '{}');
  if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
  const cv = document.createElement('canvas'); cv.className = 'plant3d-canvas';
  cv.setAttribute('role', 'img'); const svg = el.querySelector('svg');
  cv.setAttribute('aria-label', (svg && svg.getAttribute('aria-label')) || `${state.name || 'Prody'} the plant`);
  cv.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;touch-action:pan-y;cursor:grab';
  const p = { el, cv, ctx: cv.getContext('2d'), visible: !io, dirty: true, yaw: -0.25, vel: 0, drag: null, t0: performance.now() / 1000, growT: (state.grow || el.classList.contains('pl-grow')) && !reduce.matches ? 0 : 1 };
  try { build(p, state); } catch (e) { console.warn('plant3d: falling back to SVG', e); return null; }
  el.appendChild(cv); if (svg) svg.style.visibility = 'hidden'; el.classList.add('plant3d-on');
  p.tick = (dt, t) => {
    const motion = !reduce.matches;
    if (p.drag == null) { p.vel *= Math.pow(0.04, dt); p.yaw += p.vel * dt; if (motion) p.yaw += (Math.sin(t * 0.12) * 0.45 - 0.25 - p.yaw) * dt * 0.15; }
    p.turn.rotation.y = p.yaw;
    if (p.growT < 1) { p.growT = Math.min(1, p.growT + dt / 1.8); const k = 1 - Math.pow(1 - p.growT, 3); p.plant.scale.setScalar(0.04 + 0.96 * k); }
    if (motion) {
      const slow = 1 - p.droop * 0.6;
      p.plant.rotation.z = Math.sin(t * 0.9 * slow) * 0.025 + Math.sin(t * 2.3) * 0.006; p.plant.rotation.x = Math.sin(t * 0.7 + 1) * 0.015;
      for (const s of p.sway) s.o.rotation[s.axis] = s.base + Math.sin(t * 1.6 * slow + s.ph) * s.amp + Math.sin(t * 3.7 + s.ph * 2) * s.amp * 0.3;
      for (const f of p.anim) f(t);
    }
    return motion || p.drag != null || Math.abs(p.vel) > 0.01 || p.growT < 1;
  };
  cv.addEventListener('pointerdown', e => { p.drag = e.clientX; p.vel = 0; cv.setPointerCapture(e.pointerId); cv.style.cursor = 'grabbing'; kick(); });
  cv.addEventListener('pointermove', e => { if (p.drag == null) return; const d = (e.clientX - p.drag) * 0.01; p.yaw += d; p.vel = d * 60; p.drag = e.clientX; p.dirty = true; kick(); });
  const up = () => { p.drag = null; cv.style.cursor = 'grab'; kick(); };
  cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  el.__plant3d = p; live.add(p); io ? io.observe(el) : 0; kick();
  return p;
}
export function update(el, state) {
  const p = el.__plant3d; if (!p) return mount(el, state);
  const old = p.scene; build(p, state);
  old.traverse(o => { o.geometry && o.geometry.dispose(); });
  if (state.grow) p.growT = reduce.matches ? 1 : 0;
  p.dirty = true; kick(); return p;
}
export function unmount(el) { const p = el.__plant3d; if (!p) return; destroy(p); p.cv.remove(); const s = el.querySelector('svg'); if (s) s.style.visibility = ''; delete el.__plant3d; }

function scan(root) {
  (root.querySelectorAll ? root.querySelectorAll('.plant3d[data-plant]') : []).forEach(el => { if (!el.__plant3d) { try { mount(el, JSON.parse(el.dataset.plant)); } catch (e) { console.warn('plant3d', e); } } });
}
scan(document);
new MutationObserver(ms => { for (const m of ms) for (const n of m.removedNodes) if (n.nodeType === 1) (n.__plant3d ? [n] : n.querySelectorAll ? n.querySelectorAll('.plant3d') : []).forEach(x => x.__plant3d && !x.isConnected && unmount(x));
  for (const m of ms) for (const n of m.addedNodes) if (n.nodeType === 1) { n.matches && n.matches('.plant3d[data-plant]') ? scan(n.parentNode) : scan(n); } })
  .observe(document.documentElement, { childList: true, subtree: true });
reduce.addEventListener && reduce.addEventListener('change', () => { live.forEach(p => p.dirty = true); kick(); });
const pending = (window.plant3d && window.plant3d.q) || [];
window.plant3d = { mount, update, unmount };
pending.forEach(([fn, el, st]) => { try { window.plant3d[fn](el, st); } catch (e) { console.warn('plant3d', e); } });
