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
const POT_H = 0.9, POT_RT = 0.6, POT_RB = 0.46, SOIL_Y = 0.76;

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
    r.toneMapping = THREE.ACESFilmicToneMapping; r.toneMappingExposure = 1.0;
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFShadowMap;
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
  // budget: small/store cards are still frames unless hovered/selected; on phones only one plant animates
  let budget = window.innerWidth < 600 ? 1 : Infinity;
  for (const p of live) {
    if (!p.el.isConnected) { destroy(p); continue; }
    if (!p.visible) continue;
    const want = p.small ? (p.hover || p.el.matches('.selected, .is-selected, :focus-within') || !!p.el.closest('.selected, .is-selected')) : true;
    const active = want && budget > 0; if (active) budget--;
    const animating = p.tick(dt, now / 1000, active);
    if (animating || p.dirty) draw(p, p.small ? Math.min(dpr, 1.25) : dpr);
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
  // if an overflow:hidden ancestor clips the element, frame the plant inside the visible part
  let top = 0, bot = rect.height;
  for (let a = p.el.parentElement; a && a !== document.body; a = a.parentElement) {
    const cs = getComputedStyle(a); if (cs.overflow === 'visible' && cs.overflowY === 'visible') continue;
    const ar = a.getBoundingClientRect(); top = Math.max(top, ar.top - rect.top); bot = Math.min(bot, ar.bottom - rect.top); break;
  }
  const y0 = Math.round(Math.max(0, top) * dpr), vh = Math.max(1, Math.round(Math.max(1, bot - Math.max(0, top)) * dpr)) | 0, hh = Math.min(h - y0, vh);
  p.camera.aspect = w / hh; p.camera.updateProjectionMatrix();
  if (p.fit) p.fit();
  R.setViewport(0, H - hh, w, hh); R.setScissor(0, H - hh, w, hh); R.setScissorTest(true);
  R.clear(); R.render(p.scene, p.camera);
  p.ctx.clearRect(0, 0, w, h); p.ctx.drawImage(gl, 0, 0, w, hh, 0, y0, w, hh);
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
  return tex(c);
}
function backdropTex(key) {
  if (texCache[key]) return texCache[key];
  const [c, x] = canvas(1024, 1024);
  x.filter = 'blur(10px)';                  // soft focus, like depth of field
  if (key === 'scene_window') {
    const sky = x.createLinearGradient(0, 0, 0, 1024); sky.addColorStop(0, '#DCEAF0'); sky.addColorStop(0.6, '#EEF2E6'); sky.addColorStop(1, '#E8EDDC');
    x.fillStyle = sky; x.fillRect(-40, -40, 1104, 1104);
    x.fillStyle = '#FBEFC8'; x.beginPath(); x.arc(800, 260, 90, 0, 7); x.fill();
    [['#B9CFA6', 600, 0.0], ['#9EBB8A', 700, 1.3], ['#86A877', 800, 2.1]].forEach(([f, y, ph]) => {
      x.fillStyle = f; x.beginPath(); x.moveTo(-40, 1100);
      for (let px = -40; px <= 1080; px += 20) x.lineTo(px, y + Math.sin(px / 260 + ph) * 70 + Math.sin(px / 90 + ph) * 12);
      x.lineTo(1080, 1100); x.fill();
    });
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
function leafGeo(len, wid) {
  // plump almond / lens: pointed tip, inflated middle, soft indented midrib
  const g = new THREE.SphereGeometry(1, 32, 18), ps = g.attributes.position, v = new THREE.Vector3();
  for (let k = 0; k < ps.count; k++) {
    v.fromBufferAttribute(ps, k);
    const u = (v.x + 1) / 2, prof = Math.sin(Math.PI * Math.pow(u, 0.9));   // 0 at base and (pointed) tip
    const z = v.z * prof;
    let y = v.y * 0.32 * Math.sqrt(prof);
    if (y > 0) y *= 1 - 0.35 * Math.exp(-(z * z) / 0.02);
    ps.setXYZ(k, u * len, y * wid, z * wid);
  }
  g.computeVertexNormals(); return g;
}
let noiseT = null;
function clayNoise() {
  if (noiseT) return noiseT;
  const [c, x] = canvas(256, 256), r = rng(5), d = x.createImageData(256, 256);
  for (let i = 0; i < d.data.length; i += 4) { const n = 118 + r() * 20; d.data[i] = d.data[i + 1] = d.data[i + 2] = n; d.data[i + 3] = 255; }
  x.putImageData(d, 0, 0); x.filter = 'blur(1px)'; x.drawImage(c, 0, 0);
  noiseT = tex(c, false, true); noiseT.repeat.set(3, 3); return noiseT;
}
function clay(color, extra = {}) {
  return new THREE.MeshStandardMaterial(Object.assign({ color, roughness: 0.9, metalness: 0, bumpMap: clayNoise(), bumpScale: 0.35 }, extra));
}
function leafMat(color) { return clay(color, { roughness: 0.88 }); }

// ---------------------------------------------------------------- the plant build
function build(p, st) {
  const scene = new THREE.Scene(), r = rng(st.seed || 1);
  const g = +st.growth || 0, idx = st.stage_idx | 0, vit = st.vitality ?? 1, droop = 1 - vit;
  const accs = new Set(st.accs || []);
  p.sway = []; p.anim = []; p.droop = droop;

  const small = !!p.small, thick = small ? 1.3 : 1;
  // soft, diffuse studio light: big warm sky fill + a gentle key from the top-left with very soft shadows
  const hemi = new THREE.HemisphereLight(0xFFF1DE, 0xD9A878, 1.35); scene.add(hemi);
  const sun = new THREE.DirectionalLight(0xFFE6C8, 1.45);
  sun.position.set(-3.2, 5.2, 3.2); sun.target.position.set(0, 0.8, 0);
  sun.castShadow = true; const sm = small ? 512 : 1024; sun.shadow.mapSize.set(sm, sm);
  sun.shadow.bias = -0.0006; sun.shadow.normalBias = 0.03; sun.shadow.radius = small ? 4 : 7;
  Object.assign(sun.shadow.camera, { left: -3, right: 3, top: 4, bottom: -1.5, near: 0.5, far: 16 });
  scene.add(sun, sun.target);
  const rim = new THREE.DirectionalLight(0xFFF3E6, 0.45); rim.position.set(3, 1.5, 4); scene.add(rim);   // front fill, no shadow
  const back = new THREE.DirectionalLight(0xFFF6EC, 0.5); back.position.set(1.5, 3, -4); scene.add(back);   // light rim

  // warm wooden sill spanning the whole frame, a cream wall and a thick window frame with a soft-focus view
  const sk = st.scene || '';
  const sillMat = clay(sk === 'scene_desk' ? '#A86E44' : '#C48A58', { roughness: 0.85 });
  const surf = new THREE.Mesh(new THREE.BoxGeometry(24, 2.4, 2.6), sillMat);
  surf.position.set(0, -1.2, 0.2); surf.receiveShadow = true; scene.add(surf);
  const lip = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 24, 12), sillMat); lip.rotation.z = Math.PI / 2; lip.position.set(0, -0.03, 1.5); lip.receiveShadow = true; scene.add(lip);
  const wallMat = clay(sk === 'scene_greenhouse' ? '#E3E8D6' : '#EADCC6', { roughness: 1 });
  const wall = new THREE.Mesh(new THREE.PlaneGeometry(24, 14), wallMat); wall.position.set(0, 4, -1.6); wall.receiveShadow = true; scene.add(wall);
  const frameMat = clay('#F3EADB');
  const bd = new THREE.Mesh(new THREE.PlaneGeometry(3.4, 3.4), new THREE.MeshBasicMaterial({ map: backdropTex(sk || 'scene_window'), toneMapped: false }));
  bd.position.set(0, 1.75, -1.58); bd.scale.set(2.8 / 3.4, 3.1 / 3.4, 1); scene.add(bd);
  if (sk !== 'scene_desk' && sk !== 'scene_greenhouse') {
    const W = 2.7, Hh = 3.0, y0 = 0.25, T = 0.2, D = 0.24, z = -1.45;
    const box = (w, h, x, y) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, D), frameMat); m.position.set(x, y, z); m.castShadow = m.receiveShadow = true; scene.add(m); };
    box(W + 2 * T, T, 0, y0 + Hh + T / 2); box(W + 2 * T, T * 1.2, 0, y0 - T * 0.6); box(T, Hh, -W / 2 - T / 2, y0 + Hh / 2); box(T, Hh, W / 2 + T / 2, y0 + Hh / 2);
    box(W, T * 0.45, 0, y0 + Hh * 0.62); box(T * 0.45, Hh * 0.38, 0, y0 + Hh * 0.81);
  } else { bd.scale.setScalar(2.4); bd.position.y = 2.6; }
  const contact = new THREE.Mesh(new THREE.PlaneGeometry(1.9, 1.9), new THREE.MeshBasicMaterial({ map: contactTex(), transparent: true, depthWrite: false, toneMapped: false, opacity: 0.85 }));
  contact.rotation.x = -Math.PI / 2; contact.position.y = 0.003; contact.renderOrder = 1; scene.add(contact);

  // turntable: pot + plant rotate together
  const turn = new THREE.Group(); scene.add(turn);
  const [body, rimC, faceC, pat] = POTS[st.pot] || POTS.pot_terracotta;
  const flatPat = pat && !['wave', 'stripes'].includes(pat);
  const potMat = clay(flatPat ? '#ffffff' : body, flatPat ? { map: potTex(st.pot) } : {});
  const BH = POT_H - 0.16, rAt = y => lerp(POT_RB, POT_RT - 0.03, Math.max(0, Math.min(1, y / BH)));
  const prof = [new THREE.Vector2(0, 0)];
  for (let k = 0; k <= 6; k++) { const a = k / 6 * Math.PI / 2; prof.push(new THREE.Vector2(POT_RB - 0.08 + Math.sin(a) * 0.08, 0.08 - Math.cos(a) * 0.08)); }
  prof.push(new THREE.Vector2(POT_RT - 0.03, BH), new THREE.Vector2(POT_RT - 0.03, BH + 0.02));
  const potGeo = new THREE.LatheGeometry(prof, 72); potGeo.rotateY(Math.PI);
  { const ps = potGeo.attributes.position, uv = potGeo.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setY(i, Math.min(1, ps.getY(i) / BH)); }
  const pot = new THREE.Mesh(potGeo, potMat); pot.castShadow = pot.receiveShadow = true; turn.add(pot);
  const rimTop = new THREE.Mesh(new THREE.TorusGeometry(POT_RT - 0.005, 0.085, 20, 72), clay(rimC === body ? body : (flatPat ? rimC : body)));
  rimTop.rotation.x = Math.PI / 2; rimTop.scale.z = 1.25; rimTop.position.y = POT_H - 0.09; rimTop.castShadow = rimTop.receiveShadow = true; turn.add(rimTop);
  const onPot = (m, th, y, out = 0.012) => { const rr = rAt(y) + out; m.position.set(Math.sin(th) * rr, y, Math.cos(th) * rr); m.rotation.y = th; turn.add(m); return m; };
  // puffy clay stripes
  if (pat === 'wave' || pat === 'stripes') {
    const sc = pat === 'wave' ? C.terra : C.green;
    for (const y of [0.2, 0.54]) {
      const pts = []; for (let k = 0; k < 96; k++) { const a = k / 96 * Math.PI * 2, yy = y + (pat === 'wave' ? Math.sin(a * 12) * 0.03 : 0), rr = rAt(yy) + 0.004; pts.push(new THREE.Vector3(Math.sin(a) * rr, yy, Math.cos(a) * rr)); }
      const m = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 192, 0.022, 8, true), clay(sc)); m.castShadow = true; turn.add(m);
    }
  }
  // cute clay face: dot eyes, smile, blush
  const eyeY = 0.42, inkM = clay(faceC === '#F4EEE2' ? '#F4EEE2' : '#3A2A22', { roughness: 0.6 });
  if (st.mood === 'thirsty') {
    for (const s2 of [-1, 1]) { const e = new THREE.Mesh(new THREE.TorusGeometry(0.035, 0.013, 8, 16, Math.PI), inkM); onPot(e, s2 * 0.2, eyeY, 0.02); e.rotation.z = Math.PI; }
    const mo = new THREE.Mesh(new THREE.TorusGeometry(0.05, 0.012, 8, 16, Math.PI), inkM); onPot(mo, 0, eyeY - 0.17);
    const drop = new THREE.Mesh(new THREE.SphereGeometry(0.03, 12, 10), clay('#9CC3D6')); drop.scale.y = 1.4; onPot(drop, 0.5, eyeY + 0.08, 0.02);
  } else {
    for (const s2 of [-1, 1]) { const e = new THREE.Mesh(new THREE.SphereGeometry(0.038, 16, 12), inkM); e.scale.set(1, 1.15, 0.45); onPot(e, s2 * 0.2, eyeY); }
    const mo = new THREE.Mesh(new THREE.TorusGeometry(st.mood === 'happy' ? 0.055 : 0.045, 0.012, 8, 20, Math.PI * (st.mood === 'happy' ? 1 : 0.6)), inkM);
    onPot(mo, 0, eyeY - 0.08); mo.rotation.z = st.mood === 'happy' ? Math.PI : Math.PI * 1.2;
    for (const s2 of [-1, 1]) { const b = new THREE.Mesh(new THREE.SphereGeometry(0.055, 16, 10), clay('#F2A6A0')); b.scale.set(1.2, 0.7, 0.25); onPot(b, s2 * 0.36, eyeY - 0.07); }
  }
  if (accs.has('acc_sticker')) {
    const st2 = new THREE.Group();
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.14, 0.03), clay('#F6EBD6')); st2.add(base);
    const inner = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.07, 0.03), clay('#8FB3C4')); inner.position.z = 0.012; st2.add(inner);
    const brd = new THREE.Mesh(new THREE.BoxGeometry(0.19, 0.16, 0.02), clay('#7FA36C')); brd.position.z = -0.008; st2.add(brd);
    onPot(st2, 0.62, 0.2, 0.02); st2.rotation.z = -0.15;
  }
  if (pat === 'gold') { const gl = new THREE.Mesh(new THREE.TorusGeometry(POT_RT + 0.07, 0.012, 6, 64), clay('#D6B058', { roughness: 0.5, metalness: 0.4 })); gl.rotation.x = Math.PI / 2; gl.position.y = POT_H - 0.09; turn.add(gl); }
  const soil = new THREE.Mesh(new THREE.CircleGeometry(POT_RT - 0.04, 48), clay('#6E4C36', { roughness: 1 }));
  soil.rotation.x = -Math.PI / 2; soil.position.y = SOIL_Y; soil.receiveShadow = true; turn.add(soil);

  // plant hierarchy (sways at its base)
  const plant = new THREE.Group(); plant.position.y = SOIL_Y - 0.03; turn.add(plant); p.plant = plant;
  const stemC = col('#5E9A4E', droop), stemMat = clay(stemC, { roughness: 0.85 });
  const leafCols = ['#7FB55A', '#71A84E', '#8CC064'].map(c => col(c, droop)), mats = leafCols.map(leafMat);
  const youngMat = leafMat(col('#8CC46A', droop));
  const lean = (r() * 2 - 1) * 2 * U, side0 = r() < 0.5 ? -1 : 1;
  let tip = new THREE.Vector3(0, 0.05, 0), canopy = [];

  const addLeaf = (parent, pos, yaw, pitch, len, wid, mat) => {
    const piv = new THREE.Group(); piv.position.copy(pos); piv.rotation.set(0, yaw, 0);
    const inner = new THREE.Group(); inner.rotation.z = pitch - droop * 1.3; piv.add(inner);
    const pet = Math.max(0.025, len * 0.18);
    const stalk = new THREE.Mesh(new THREE.CylinderGeometry(0.008 * thick, 0.011 * thick, pet, 8), stemMat); stalk.rotation.z = -Math.PI / 2; stalk.position.x = pet / 2; inner.add(stalk);
    len *= 1.35; const m = new THREE.Mesh(leafGeo(len, wid * 1.3 * thick), mat); m.position.x = pet * 0.85;
    m.rotation.x = (Math.cos(yaw) >= 0 ? -0.55 : 0.55) * (1 - droop * 0.6); m.castShadow = true; m.receiveShadow = true; inner.add(m);
    parent.add(piv); p.sway.push({ o: inner, base: inner.rotation.z, ph: r() * 6.28, amp: 0.04 + r() * 0.04, axis: 'z' }); return piv;
  };
  const addFlower = (parent, pos, rad, petalHex) => {
    const fg = new THREE.Group(); fg.position.copy(pos); rad *= 1.95;
    const pm = clay(col(petalHex, droop), { roughness: 0.9 }), pg = new THREE.SphereGeometry(1, 18, 12);
    for (let k = 0; k < 5; k++) { const a = k * 1.2566; const m = new THREE.Mesh(pg, pm); m.scale.set(rad * 0.34, rad * 0.15, rad * 0.34);
      m.position.set(Math.cos(a) * rad * 0.42, -droop * 0.02, Math.sin(a) * rad * 0.42); m.rotation.y = -a; m.rotation.z = 0.1 + droop * 0.5; m.castShadow = true; fg.add(m); }
    const ctr = new THREE.Mesh(new THREE.SphereGeometry(rad * 0.24, 16, 10), clay('#EE8A3A')); ctr.scale.y = 0.8; ctr.position.y = rad * 0.08; fg.add(ctr);
    fg.rotation.order = 'YXZ'; fg.rotation.set(1.25 + droop * 0.4, -(parent.rotation ? parent.rotation.y : 0), 0);
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
    const sm = new THREE.Mesh(taperedTube(curve, w0 * 0.95 * thick, 0.018 * thick, 48, 14), stemMat); sm.castShadow = true; plant.add(sm);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.018 * thick, 12, 8), stemMat); cap.position.copy(curve.getPointAt(1)); plant.add(cap);
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
      const bm = new THREE.Mesh(taperedTube(bc, (2.4 + g * 2.6) * U * 1.0 * thick, 0.022 * thick, 16, 10), stemMat); bm.castShadow = true; bg.add(bm);
      p.sway.push({ o: bg, base: bg.rotation.y, ph: r() * 6.28, amp: 0.04, axis: 'y' });
      [0.3, 0.55, 0.8].forEach((tt, k) => addLeaf(bg, bc.getPoint(tt), (k ? 1 : -1) * 0.9, 0.35, (20 + g * 12) * U * 1.2, (7.5 + g * 3.5) * U * 1.1, mats[(i + k) % 3]));
      const tipW = new THREE.Vector3();
      if (idx >= 4 && vit > 0.25) {
        addLeaf(bg, end, 0.5, 0.2, (13 + g * 6) * U * 1.2, (5 + g * 2) * U, mats[i % 3]);
        const fl = addFlower(bg, end.clone().add(new THREE.Vector3(0, 0.02, 0)), (7 + g * 3) * U * 1.3, i % 2 ? '#F2A48A' : '#F2A48A');
        
      } else addLeaf(bg, end, 0, 0.1, (22 + g * 10) * U * 1.2, (8 + g * 3.2) * U * 1.1, mats[i % 3]);
      if (idx >= 5 && i % 2 === 0) {
        const fm = new THREE.Mesh(new THREE.SphereGeometry(4.6 * U * 1.4, 18, 12), clay(col('#E07A4A', droop)));
        fm.position.copy(bc.getPoint(0.5)).add(new THREE.Vector3(0, -0.07, 0)); fm.castShadow = true; bg.add(fm);
      }
      canopy.push(tipW.copy(end).applyEuler(bg.rotation).add(bg.position).add(plant.position));
    }
    // leaves on the main stem
    if (idx === 1) {
      for (const s of [-1, 1]) addLeaf(plant, tipL, s > 0 ? 0.2 : Math.PI + 0.2, 0.55, (15 + g * 40) * U * 1.2, (7.5 + g * 12) * U * 1.1, mats[(s + 1) / 2]);
    } else {
      const nl = 4 + Math.floor(g * 8);
      for (let i = 0; i < nl; i++) {
        const t = 0.14 + 0.72 * i / Math.max(nl - 1, 1), len = (25 + g * 14) * (1 - 0.35 * t) * (0.88 + r() * 0.2) * U * 1.1;
        addLeaf(plant, curve.getPointAt(t), (i % 2 ? -0.3 : Math.PI + 0.3) + (r() - 0.5) * 0.15, 0.785, len * 0.85, len * 0.3, mats[i % 2]);
      }
      for (const s of [-1, 1]) addLeaf(plant, tipL, s > 0 ? 0.8 : Math.PI + 0.8, 0.9, (12 + g * 6) * U * 1.2, (4.6 + g * 2) * U, youngMat);
      if (idx >= 4 && vit > 0.25 && !accs.has('acc_hat')) addFlower(plant, tipL.clone().add(new THREE.Vector3(0, 0.02, 0)), (9 + g * 3) * U * 1.3, '#F2A48A');
    }
  }
  if (!canopy.length) canopy = [tip.clone().add(new THREE.Vector3(-0.25, -0.15, 0)), tip.clone().add(new THREE.Vector3(0.25, -0.15, 0))];

  // ---- accessories
  const front = new THREE.Vector3(0, 0, 1);
  if (accs.has('acc_hat')) {
    const straw = clay('#E6C78E');
    const hat = new THREE.Group(); hat.position.copy(tip).sub(plant.position).add(new THREE.Vector3(0, 0.05, 0)); hat.rotation.set(0.35, 0, -0.25); hat.scale.setScalar(1.3);
    const brim = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.21, 0.03, 32), straw), crown = new THREE.Mesh(new THREE.SphereGeometry(0.1, 24, 12, 0, 6.29, 0, 1.57), straw);
    const band = new THREE.Mesh(new THREE.CylinderGeometry(0.101, 0.101, 0.03, 32, 1, true), clay('#4F8A56'));
    band.position.y = 0.02; [brim, crown, band].forEach(m => { m.castShadow = true; hat.add(m); }); plant.add(hat);
  }
  if (accs.has('acc_glasses')) {
    const gm = new THREE.MeshStandardMaterial({ color: faceC, roughness: 0.3, metalness: 0.4 }), gg = new THREE.Group();
    const vFace = 1 - 200 / 512, y = POT_H - 0.16 - (1 - vFace) * 0; // eye height on the body
    const ey = eyeY, rz = lerp(POT_RB, POT_RT - 0.03, (ey - 0.04) / (POT_H - 0.2)) + 0.03;
    for (const s of [-1, 1]) { const ring = new THREE.Mesh(new THREE.TorusGeometry(0.075, 0.008, 8, 32), gm); ring.position.set(s * 0.1, ey, rz); ring.rotation.y = s * 0.1; gg.add(ring);
      const lens = new THREE.Mesh(new THREE.CircleGeometry(0.072, 24), new THREE.MeshPhysicalMaterial({ color: '#fff', transparent: true, opacity: 0.18, roughness: 0.05 })); lens.position.copy(ring.position); gg.add(lens); }
    const bridge = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.006, 6, 12, Math.PI), gm); bridge.position.set(0, ey + 0.01, rz + 0.005); gg.add(bridge);
    gg.children.forEach(m => m.castShadow = true); turn.add(gg);
  }
  if (accs.has('acc_scarf')) {
    const knit = clay(C.terra);
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
  const top = Math.max(tip.y + 0.4, ...canopy.map(v => v.y + 0.15), 1.4), bottom = small ? -0.2 : -0.45, midY = (top + bottom) / 2;
  const cam = p.camera || new THREE.PerspectiveCamera(28, 0.8, 0.1, 50);
  const hgt = (top - bottom) * (small ? 1.05 : 1.15), halfW = 1.05;   // keep pot + a bit of sill inside the width too
  p.fit = () => {
    const tf = Math.tan(THREE.MathUtils.degToRad(cam.fov / 2));
    const dist = Math.max(hgt / 2 / tf, halfW / (tf * cam.aspect));
    cam.position.set(0, midY + dist * 0.2, dist); cam.lookAt(0, midY - 0.02, 0);
  };
  p.fit(); p.camera = cam;
  p.theme = { hemi, sun, rim, surf: [sillMat, wallMat, frameMat], bd: bd.material };
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
  T.surf.forEach(m => { m.userData.base = m.userData.base || m.color.clone(); m.color.copy(m.userData.base).multiply(new THREE.Color(d ? 0x8A8A92 : 0xFFFFFF)); });
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
  const p = { small: el.getBoundingClientRect().width < 260, hover: false, el, cv, ctx: cv.getContext('2d'), visible: !io, dirty: true, yaw: -0.25, vel: 0, drag: null, t0: performance.now() / 1000, growT: (state.grow || el.classList.contains('pl-grow')) && !reduce.matches ? 0 : 1 };
  try { build(p, state); } catch (e) { console.warn('plant3d: falling back to SVG', e); return null; }
  el.appendChild(cv); if (svg) svg.style.visibility = 'hidden'; el.classList.add('plant3d-on');
  p.tick = (dt, t, active = true) => {
    const motion = !reduce.matches && active;
    if (p.drag == null) { p.vel *= Math.pow(0.04, dt); p.yaw += p.vel * dt; if (motion) p.yaw += (Math.sin(t * 0.12) * 0.45 - 0.25 - p.yaw) * dt * 0.15; }
    p.turn.rotation.y = p.yaw;
    if (p.growT < 1) { p.growT = Math.min(1, p.growT + dt / 1.8); const k = 1 - Math.pow(1 - p.growT, 3); p.plant.scale.setScalar(0.04 + 0.96 * k); }
    if (motion) {
      const slow = 1 - p.droop * 0.6;
      p.plant.rotation.z = Math.sin(t * 0.9 * slow) * 0.025 + Math.sin(t * 2.3) * 0.006; p.plant.rotation.x = Math.sin(t * 0.7 + 1) * 0.015;
      for (const s of p.sway) s.o.rotation[s.axis] = s.base + Math.sin(t * 1.6 * slow + s.ph) * s.amp + Math.sin(t * 3.7 + s.ph * 2) * s.amp * 0.3;
      for (const f of p.anim) f(t);
    }
    if (!motion && p.growT >= 1 && p.wasMoving) { p.wasMoving = false; p.dirty = true; }
    p.wasMoving = motion;
    return motion || p.drag != null || Math.abs(p.vel) > 0.01 || p.growT < 1;
  };
  el.addEventListener('pointerenter', () => { p.hover = true; kick(); });
  el.addEventListener('pointerleave', () => { p.hover = false; kick(); });
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
export async function refresh(el, url = '/plant/state') {
  // refetch the server state (JSON) and rebuild; falls back to the element's data-plant
  let st = null;
  try { const r = await fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' }); if (r.ok) st = await r.json(); } catch (e) { }
  st = st || JSON.parse(el.dataset.plant || '{}'); el.dataset.plant = JSON.stringify(st); return update(el, st);
}
window.plant3d = { mount, update, unmount, refresh };
pending.forEach(([fn, el, st]) => { try { window.plant3d[fn](el, st); } catch (e) { console.warn('plant3d', e); } });
