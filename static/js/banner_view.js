/* banner_view v3 (Coder): inlines every visible .fp-park img[data-park="<key>"] layer (3d design 1 park items, unique id prefixes) into the
   enlarged clone at the same box, and animates each by its own ids (clouds, far trees, flowers, lamp glow, birds, people, jogger, dog, kids,
   vut-page page turn). Falls back to v2's single legacy park <img>. Failed fetch -> that layer stays the static <img>.
   v2: inlines the single park SVG. v1: tap/click .fp-banner -> opens large over a dimmed backdrop. Close: backdrop tap, X, Esc.
   Focus returns to the banner, body scroll locked, paused when the tab is hidden, nothing moves under reduced motion. transform/opacity only. */
(function () {
  var ban = document.querySelector('.fp-banner'); if (!ban) return;
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches, back = null;
  ban.setAttribute('role', 'button'); ban.setAttribute('tabindex', '0'); ban.setAttribute('aria-label', ban.getAttribute('aria-label') || 'Open banner');
  function vis() { back && back.classList.toggle('bv-paused', document.hidden); }
  function key(e) { if (e.key === 'Escape') close(); else if (e.key === 'Tab' && back) { e.preventDefault(); back.querySelector('.bv-x').focus(); } }
  function close() { if (!back) return; var b = back; back = null; b.classList.remove('on'); document.documentElement.classList.remove('bv-lock');
    document.removeEventListener('keydown', key); document.removeEventListener('visibilitychange', vis);
    setTimeout(function () { b.remove(); }, RM ? 0 : 260); try { ban.focus({ preventScroll: true }); } catch (e) { ban.focus(); } }
  function shown(im) { if (!im || !(im.currentSrc || im.src)) return false; var r = im.getBoundingClientRect(), s = getComputedStyle(im);
    return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden'; }
  function open() { if (back) return;
    /* decide visibility on the live banner (clone is not laid out yet); keep index pairing */
    var live = [].slice.call(ban.querySelectorAll('.fp-park img[data-park], img[data-park], svg[data-park][data-src]')), keep = live.map(function (n) { return n.nodeName.toLowerCase() === 'svg' ? !!(n.getClientRects().length && getComputedStyle(n).display !== 'none') : shown(n); });
    back = document.createElement('div'); back.className = 'bv-back'; back.setAttribute('role', 'dialog'); back.setAttribute('aria-modal', 'true'); back.setAttribute('aria-label', 'Profile banner');
    var stage = document.createElement('div'); stage.className = 'bv-stage'; var clone = ban.cloneNode(true); clone.removeAttribute('tabindex'); clone.removeAttribute('role');
    clone.querySelectorAll('.pf-hit').forEach(function (n) { n.remove(); });  // v9: friend visitors go back to <img> in the viewer and are re-inlined + re-tinted by layers()
    clone.querySelectorAll('svg[data-park][data-src]').forEach(function (n) { var im = document.createElement('img'); im.className = n.getAttribute('class'); im.setAttribute('data-park', n.getAttribute('data-park')); im.src = n.getAttribute('data-src'); im.alt = ''; n.getAttribute('data-tint') && im.setAttribute('data-tint', n.getAttribute('data-tint')); n.replaceWith(im); });
    clone.querySelectorAll('[id]').forEach(function (n) { n.removeAttribute('id'); });
    var x = document.createElement('button'); x.type = 'button'; x.className = 'bv-x'; x.setAttribute('aria-label', 'Close'); x.textContent = '×';
    stage.appendChild(clone); stage.appendChild(x); back.appendChild(stage); document.body.appendChild(back);
    back.addEventListener('click', function (e) { if (e.target === back) close(); }); x.onclick = close;
    document.documentElement.classList.add('bv-lock'); document.addEventListener('keydown', key); document.addEventListener('visibilitychange', vis); vis();
    if (!RM) { var lay = [].slice.call(clone.querySelectorAll('.fp-park img[data-park], img[data-park]')); if (lay.length) layers(clone, lay, keep.length === lay.length ? keep : lay.map(function () { return true; })); else liven(clone); }
    requestAnimationFrame(function () { back && back.classList.add('on'); }); x.focus({ preventScroll: true }); }
  function tint(sv, c) { if (!c) return; var w1 = null; sv.querySelectorAll('.tint').forEach(function (g) { var m = ((g.id || g.getAttribute('data-id') || '')).match(/tint-([a-z]+)-(?:top|bottom)$/), nm = m ? m[1] : ''; if (w1 === null) w1 = nm; if (nm === w1) g.style.color = c; }); }
  function piv(n) { var p = (n.getAttribute('data-pivot') || '').split(/[ ,]+/).map(parseFloat); if (p.length > 1 && !isNaN(p[1])) { n.style.transformBox = 'view-box'; n.style.transformOrigin = p[0] + 'px ' + p[1] + 'px'; } else { n.style.transformBox = 'fill-box'; n.style.transformOrigin = '50% 100%'; } }
  function box(o) { return function (n) { n.style.transformBox = 'fill-box'; n.style.transformOrigin = o; }; }
  var DUR = { 'bv-cloud': [40, 9], 'bv-bird': [9, 2], 'bv-tree': [6, .7], 'bv-flower': [4, .5], 'bv-people': [5, .6], 'bv-jog': [.7, 0], 'bv-dog': [.9, 0], 'bv-wag': [.45, 0], 'bv-kids': [1.1, .2], 'bv-page': [6, 0], 'bv-vut': [5.5, 0], 'bv-glow': [4, 0] };
  function anim(sv) { var A = function (sel, cls, fn) { sv.querySelectorAll(sel).forEach(function (n, i) { if (n.classList.contains('bv-a')) return; fn && fn(n); n.classList.add('bv-a', cls);
        var d = DUR[cls] || [4, 0]; n.style.animationDelay = (-i * 1.9) + 's'; n.style.animationDuration = (d[0] + i * d[1]) + 's'; }); };
    A('[id^=cloud-],[id*="-cloud-"]', 'bv-cloud'); A('[id^=far-tree-],[id*="-far-tree-"]', 'bv-tree', piv); A('[id^=flowers-],[id*="-flowers-"]', 'bv-flower', piv);
    A('#lamp-glow,[id$="-lamp-glow"]', 'bv-glow'); A('[id^=bird-],[id*="-bird-"]', 'bv-bird', box('50% 50%'));
    A('[id*="jogger_"]', 'bv-jog', box('50% 100%')); A('[id$="dog-tail"],[id$="-tail"]', 'bv-wag', piv); A('[id$="-dog"]', 'bv-dog', box('50% 100%'));
    A('[id$="-kids"],[id*="-kid-"]', 'bv-kids', box('50% 100%')); A('#vut-page', 'bv-page', box('50% 100%')); A('#vut-body', 'bv-vut', box('0% 100%'));
    A('#layer-bench_people,[id^=bp-person],[id$="-people"],[id$="reader_walk"]', 'bv-people', box('50% 100%')); }
  function clean(t) { var d = new DOMParser().parseFromString(t, 'image/svg+xml'), sv = d.documentElement; if (!sv || sv.nodeName.toLowerCase() !== 'svg' || d.querySelector('parsererror')) return null;
    sv.querySelectorAll('script,foreignObject,iframe,embed,object').forEach(function (n) { n.remove(); });
    [sv].concat([].slice.call(sv.querySelectorAll('*'))).forEach(function (el) { [].slice.call(el.attributes).forEach(function (a) {
      if (/^on/i.test(a.name) || (/href$/i.test(a.name) && /^\s*javascript:/i.test(a.value))) el.removeAttribute(a.name); }); });
    sv.removeAttribute('width'); sv.removeAttribute('height'); sv.setAttribute('aria-hidden', 'true'); sv.setAttribute('focusable', 'false'); return sv; }
  function get(im) { return fetch(im.currentSrc || im.src, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : ''; }); }
  function par(s) { var f = s.objectFit, p = (s.objectPosition || '50% 50%').split(' '), ax = function (v, lo, hi) { v = parseFloat(v); return v <= 0 ? lo : v >= 100 ? hi : 'Mid'; };
    if (f === 'fill') return 'none'; return 'x' + ax(p[0], 'Min', 'Max') + 'Y' + ax(p[1] || p[0], 'Min', 'Max') + (f === 'cover' ? ' slice' : ' meet'); }
  /* v3: one inline SVG per visible layer, overlaid on the img's exact box (as % of its offset parent so it tracks resizes) */
  function layers(clone, lay, keep) { lay.forEach(function (im, i) { if (!keep[i]) return;
    get(im).then(function (t) { if (!t || !back || !clone.isConnected || !im.isConnected) return; var sv = clean(t); if (!sv) return;
      var op = im.offsetParent || im.parentNode, pr = op.getBoundingClientRect(), r = im.getBoundingClientRect(); if (!pr.width || !pr.height || !r.width) return;
      var s = getComputedStyle(im); sv = document.importNode(sv, true);
      sv.setAttribute('preserveAspectRatio', par(s)); sv.setAttribute('class', 'bv-layer'); sv.setAttribute('data-park', im.getAttribute('data-park') || '');
      sv.style.cssText = 'position:absolute;left:' + ((r.left - pr.left - op.clientLeft) / pr.width * 100) + '%;top:' + ((r.top - pr.top - op.clientTop) / pr.height * 100) + '%;width:' + (r.width / pr.width * 100) + '%;height:' + (r.height / pr.height * 100) + '%;z-index:' + s.zIndex + ';pointer-events:none;overflow:visible';
      im.insertAdjacentElement('afterend', sv); im.style.opacity = '0'; anim(sv); tint(sv, im.getAttribute('data-tint')); }).catch(function () {}); }); }
  /* v2 legacy: a single park <img> */
  function liven(clone) { var im = clone.querySelector('.fp-park img:not([data-park]), img.fp-park, img[src*="banner_"]'); if (!im || !im.currentSrc && !im.src) return;
    get(im).then(function (t) { if (!t || !back || !clone.isConnected) return; var sv = clean(t); if (!sv) return;
      sv.setAttribute('class', ((im.getAttribute('class') || '') + ' bv-park').trim()); sv.setAttribute('preserveAspectRatio', 'xMidYMax slice');
      sv.style.cssText = im.style.cssText; sv.style.width = '100%'; sv.style.height = '100%'; sv.style.display = 'block';
      sv = document.importNode(sv, true); im.replaceWith(sv); anim(sv); }).catch(function () {}); }
  ban.addEventListener('click', function (e) { if (!e.target.closest('a,button')) open(); });
  ban.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
})();
/* v5 friends in the park: each visitor spot is an online friend; empty spots stay plain grass. Tap a visitor for a name tag. */
(function () {
  var park = document.querySelector('.fp-banner .fp-park'); if (!park) return;
  var ban = park.closest('.fp-banner'), fr = [], slots = [];
  try { fr = JSON.parse(park.getAttribute('data-friends') || '[]') || []; slots = JSON.parse(park.getAttribute('data-visitor-slots') || '[]') || []; } catch (e) { return; }
  var people = slots.filter(function (k) { return k !== 'v_dog' && k !== 'v_under_tree'; /*v8 Leader: the man under the tree is scenery*/ }), who = {};
  people.forEach(function (k, i) { if (fr[i]) who[k] = fr[i]; });
  var hide = function (k) { park.querySelectorAll('img[data-park="' + k + '"]').forEach(function (im) { im.hidden = true; im.style.display = 'none'; }); };
  people.forEach(function (k) { if (!who[k]) hide(k); });
  if (slots.indexOf('v_dog') > -1 && !who.v_reader_walk_phone) hide('v_dog');  // v7 Design: the dog comes with the phone walker
  var keys = Object.keys(who); if (!keys.length) return;
  var NS = 'http://www.w3.org/2000/svg', ov = document.createElementNS(NS, 'svg');
  ov.setAttribute('class', 'pf-hit'); ov.setAttribute('viewBox', '0 0 1200 240'); ov.setAttribute('preserveAspectRatio', 'xMidYMax slice'); ov.setAttribute('aria-hidden', 'false');
  park.appendChild(ov); var tag = null, tmr = 0;
  function drop() { clearTimeout(tmr); if (tag) { var t = tag; tag = null; t.classList.remove('on'); setTimeout(function () { t.remove(); }, 200); } }
  function mk(f, ph) { var t = document.createElement('div'); t.className = 'pf-tag'; t.setAttribute('role', 'status');
    var n = document.createElement('b'); n.textContent = f.display || f.username; var d = document.createElement('span'); d.className = 'pf-dot'; n.prepend(d);
    var a = document.createElement('small'); a.textContent = f.activity === 'studying' ? 'Studying' : 'Walking'; t.append(n, a); t.classList.toggle('pf-ph', ph); ban.appendChild(t); return t; }
  function heads(sv) { var out = [], m = sv && sv.getScreenCTM(); if (!m) return out; [sv].concat([].slice.call(sv.querySelectorAll('*'))).forEach(function (e) { [].forEach.call(e.attributes, function (a) { if (!/^data-head(-[a-z]+)?$/.test(a.name)) return;
      var v = a.value.split(/[ ,]+/).map(Number); if (v.length < 2 || !isFinite(v[0])) return; var pt = sv.createSVGPoint(); pt.x = v[0]; pt.y = v[1]; pt = pt.matrixTransform(m); out.push({ who: a.name.slice(10), x: pt.x, y: pt.y }); }); }); return out; }
  function headOf(r) { var hs = heads(r._sv), me = hs.filter(function (h) { return h.who === (r._sv && r._sv._who || ''); })[0] || hs[0]; if (me) return me;
    var q = r.getBoundingClientRect(), hd = r._hd, c = hd && hd.getClientRects().length && hd.getBoundingClientRect(); return { x: c && c.width ? c.left + c.width / 2 : q.left + q.width / 2, y: q.top + 4 }; }
  function place(r, t) {  // v15 Design: centred above own head, bottom 6u over it; only rule = don't cover another person's head (raise 14u steps); x 308-892
    var b = ban.getBoundingClientRect(), w = t.offsetWidth, h = t.offsetHeight, S = Math.max(b.width / 1200, b.height / 240), OX = (b.width - 1200 * S) / 2, cx2 = function (X) { return X * S + OX; };
    var me = headOf(r), cx = me.x - b.left, hy = me.y - b.top, R = 1 * S /*v17: actual head points only*/, others = [];
    [].forEach.call(ban.querySelectorAll('rect.pf-v'), function (o) { heads(o._sv).forEach(function (hh) { if (o === r && hh.who === me.who && Math.abs(hh.x - me.x) < 1) return; others.push(hh); }); });
    var vl = Math.max(cx2(308), -b.left + 8 * S, 0), vr = Math.min(cx2(892) - 2 * S, innerWidth - b.left - 8 * S, b.width), x = Math.max(vl, Math.min(cx - w / 2, vr - w)), y = hy - 6 * S - h - 5.5 - (innerWidth < 600 ? 2.4 * S : 0), k;  /*v18: phone tip measured 2.4 short*/  /*v17: pointer tip = rotated 7px square corner, 5.5px below pill; tip 6 units above head*/
    var cov = function (Y) { return others.some(function (o) { var ox = o.x - b.left, oy = o.y - b.top; return ox + R > x && ox - R < x + w && oy + R > Y && oy - R < Y + h; }); };
    for (k = 0; k < 12 && cov(y) && y - 14 * S >= 2; k++) y -= 14 * S;
    if (y < 2) y = 2; var px = Math.max(8, Math.min(w - 8, cx - x));
    return { x: x, y: y, side: 'down', px: px }; }
  function show(r, f) { drop(); var ph = innerWidth < 600, res; tag = mk(f, ph); res = place(r, tag);
    tag.style.setProperty('--pf-px', res.px + 'px'); tag.setAttribute('data-ptr', res.side); var x = res.x, y = res.y;
    tag.style.left = x + 'px'; tag.style.top = y + 'px'; requestAnimationFrame(function () { tag && tag.classList.add('on'); }); tmr = setTimeout(drop, 4000); }
  var seq = 0;
  function inline(im, f) { return fetch(im.currentSrc || im.src, { credentials: 'same-origin' }).then(function (r) { return r.ok ? r.text() : ''; }).then(function (t) {  // v9: inline so the friend's colour can reach the *-tint groups
    if (!t) return null; var pre = 'pf' + (++seq) + '_', ids = [];
    t.replace(/\sid="([^"]+)"/g, function (m, i) { ids.push(i); return m; });
    ids.forEach(function (i) { var e = i.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); t = t.replace(new RegExp('id="' + e + '"', 'g'), 'id="' + pre + i + '"').replace(new RegExp('#' + e + '([")\\s])', 'g'), '#' + pre + i + '$1'); });
    var d = new DOMParser().parseFromString(t, 'image/svg+xml'), sv = d.documentElement; if (!sv || sv.nodeName.toLowerCase() !== 'svg' || d.querySelector('parsererror')) return null;
    sv.querySelectorAll('script,foreignObject,iframe,embed,object').forEach(function (n) { n.remove(); });
    [sv].concat([].slice.call(sv.querySelectorAll('*'))).forEach(function (el) { [].slice.call(el.attributes).forEach(function (at) { if (/^on/i.test(at.name) || /javascript:/i.test(at.value)) el.removeAttribute(at.name); }); });
    sv = document.importNode(sv, true); sv.setAttribute('class', im.className); sv.setAttribute('data-park', im.getAttribute('data-park')); sv.setAttribute('aria-hidden', 'true'); sv.setAttribute('preserveAspectRatio', 'xMidYMax slice'); sv.setAttribute('data-src', im.currentSrc || im.src); f.color && sv.setAttribute('data-tint', f.color);
    var tg = [].slice.call(sv.querySelectorAll('.tint')), who1 = null; sv._hd = null;  // two-person files: tint only the first person (e.g. -tint-man-*), leave the other as drawn
    tg.forEach(function (g) { var m = (g.id || '').match(/tint-([a-z]+)-(?:top|bottom)$/); var nm = m ? m[1] : ''; if (who1 === null) who1 = nm; if (nm === who1 && f.color) g.style.color = f.color; if (nm === who1 && !sv._hd && /top$/.test(g.id || '')) sv._hd = g; }); if (!sv._hd) sv._hd = tg[0] || null; sv._who = who1 || '';
    im.replaceWith(sv); return sv; }).catch(function () { return null; }); }
  function shownEl(n) { return n && n.getClientRects().length && getComputedStyle(n).display !== 'none'; }
  keys.forEach(function (k) { var f = who[k], ims = [].slice.call(park.querySelectorAll('img[data-park="' + k + '"]'));
    Promise.all(ims.map(function (im) { return inline(im, f); })).then(function (svs) { var sv = svs.filter(shownEl)[0] || svs.filter(Boolean)[0]; if (!sv) return;
      var bb = null; try { var kids = [].slice.call(sv.children).filter(function (c) { return c.nodeName !== 'defs'; }); kids.forEach(function (c) { var q = c.getBBox(); if (!q.width) return; bb = bb ? { x: Math.min(bb.x, q.x), y: Math.min(bb.y, q.y), r: Math.max(bb.r, q.x + q.width), b: Math.max(bb.b, q.y + q.height) } : { x: q.x, y: q.y, r: q.x + q.width, b: q.y + q.height }; }); } catch (e) {}
      if (!bb) return; var r = document.createElementNS(NS, 'rect'), p = 4; r.setAttribute('x', bb.x - p); r.setAttribute('y', bb.y - p); r.setAttribute('width', bb.r - bb.x + 2 * p); r.setAttribute('height', bb.b - bb.y + 2 * p);
      r._f = f; r._i = keys.indexOf(k); r._hd = sv._hd; r._sv = sv; r.setAttribute('class', 'pf-v'); r.setAttribute('tabindex', '0'); r.setAttribute('role', 'button'); r.setAttribute('aria-label', (f.display || f.username) + ', ' + (f.activity === 'studying' ? 'studying' : 'online'));
      var go = function (e) { e.stopPropagation(); e.preventDefault(); show(r, f); };
      r.addEventListener('click', go); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') go(e); }); ov.appendChild(r); }); });
  document.addEventListener('click', function (e) { if (tag && !e.target.closest('.pf-v')) drop(); }, true);
})();
