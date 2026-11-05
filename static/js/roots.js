/* Prody · Roots + Branches "semester plant" (Coder).
   Port of 3d design 1's prody_assets/roots_style/gen.py (taper, curve, leaf, flower, root) to live SVG.
   API: window.roots.mount(el, data) · update(el, data) · growLeaf(el, courseId) · mini(el, data)
   mini(el, data): static Profile "My plant" card render (see api.mini); data + optional tier ("rare"|"epic"|"legendary").
   data.species (optional) = {id, leaf_color, flower_color, bark_color, leaf_shape (one SVG path, base 0,0 pointing +x, ~60 long), blooms, bloom_color}; absent = default tree.
   Auto-mounts .roots[data-roots] (inline JSON) and .roots[data-roots-src] (fetch URL), including ones added later.
   Data: GET /roots/data → {today, streak, studied_today, branches:[{course_id,name,code,color,minutes,leaves,flowers}],
                            roots:[{deadline_id,course_id,name,due,days_left,weight,studied_minutes,dashed}]}
   Click fires `roots:select` {type:'branch'|'root', id}; navigates if item.url or el.dataset.branchUrl / rootUrl ("…{id}…") is set. */
(function () {
  'use strict';
  // ---- one place for every tunable (colours live in roots.css as --r-* vars) ----
  var CFG = {
    W: 900, Wnarrow: 520, narrowBelow: 560, ground: 400, H: 900,
    trunk: { w0: 24, w1: 6, top: 230, wob: 3, bumps: [[0, 7], [.03, 3.5], [.35, 1.4], [.6, 1.2]] },  // v33: flared base, tapers to the crown
    branch: { w0: 11, dec: 1.6, wMin: 5, w1: 2.4, wob: 4, freq: 2, bump: 2.6, nodes: [.28, .52, .76],
              sCurve: 60, sDrop: 30, minReach: .55, fullHours: 60 },
    leaf: { max: 14, tFrom: .25, tTo: .95, angMin: 35, angJit: 20, scMin: .55, scJit: .35, growBoost: .3,
            clusterHours: 50, young: ['#4E9A4F', '#8CC56B'], mature: ['#2F6B3A', '#4E9A4F'] },
    flower: { max: 5, tFrom: .55, span: .35, scale: 1.1 },
    root: { maxN: 12, top: 28, bottomPad: 34, horizon: 21, wob: 7, freq: 4, wMin: 4, wMax: 15, wDefault: 8, w1: 1,
            fullWeight: 40, dashOn: 6, dashOff: 3, spread0: 120, spreadStep: 70 },
    motion: { leafPop: 400, leafStagger: 60, branchDelay: 120, rootGrow: 600, rootStagger: 90, swayPhase: .7 },
    canopy: true, hit: 24, seedImg: '/static/img/roots/seed_empty.svg', addUrl: '/add_courses'
  };
  var NS = 'http://www.w3.org/2000/svg';
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)');
  function f(v) { return (Math.round(v * 10) / 10).toString(); }
  function rng(seed) { var s = (seed * 9301 + 49297) % 233280 || 1; return function () { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; }; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function mix(a, b, t) { var p = function (h, i) { return parseInt(h.substr(1 + i * 2, 2), 16); }, o = '#';
    for (var i = 0; i < 3; i++) o += ('0' + Math.round(p(a, i) + (p(b, i) - p(a, i)) * t).toString(16)).slice(-2); return o; }

  // ---- geometry (gen.py port) ----
  function bez(p0, p1, p2, p3, t) { var u = 1 - t; return [0, 1].map(function (k) { return u * u * u * p0[k] + 3 * u * u * t * p1[k] + 3 * u * t * t * p2[k] + t * t * t * p3[k]; }); }
  function smooth(pts, closed) {
    var n = pts.length, s = 'M' + f(pts[0][0]) + ',' + f(pts[0][1]), m = closed ? n : n - 1;
    for (var i = 0; i < m; i++) {
      var p0 = (closed || i > 0) ? pts[(i - 1 + n) % n] : pts[0], p1 = pts[i], p2 = pts[(i + 1) % n],
          p3 = (closed || i + 2 < n) ? pts[(i + 2) % n] : pts[n - 1];
      s += ' C' + f(p1[0] + (p2[0] - p0[0]) / 6) + ',' + f(p1[1] + (p2[1] - p0[1]) / 6) + ' ' + f(p2[0] - (p3[0] - p1[0]) / 6) + ',' +
           f(p2[1] - (p3[1] - p1[1]) / 6) + ' ' + f(p2[0]) + ',' + f(p2[1]);
    }
    return s + (closed ? ' Z' : '');
  }
  function curve(p0, p1, p2, p3, n, wob, seed, freq) {
    var ph = rng(seed)() * 6, out = [];
    for (var i = 0; i <= n; i++) { var t = i / n, p = bez(p0, p1, p2, p3, t); p[0] += wob * Math.sin(t * freq * Math.PI + ph) * t; out.push(p); }
    return out;
  }
  function normal(c, i) { var a = c[Math.max(i - 1, 0)], b = c[Math.min(i + 1, c.length - 1)], dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1; return [-dy / d, dx / d]; }
  function taper(c, w0, w1, bumps) {
    var n = c.length, L = [], R = [];
    for (var i = 0; i < n; i++) {
      var t = i / (n - 1), nm = normal(c, i), w = (w0 + (w1 - w0) * Math.pow(t, .8)) / 2;
      (bumps || []).forEach(function (b) { w += b[1] * Math.exp(-Math.pow((t - b[0]) / .018, 2)); });
      L.push([c[i][0] + nm[0] * w, c[i][1] + nm[1] * w]); R.push([c[i][0] - nm[0] * w, c[i][1] - nm[1] * w]);
    }
    var pts = L.concat([c[n - 1]], R.reverse());
    return smooth(pts.length > 60 ? pts.filter(function (_, i) { return i % 2 === 0; }) : pts, true);
  }
  function capsule(c, w0, w1) {
    var n = c.length, L = [], R = [];
    for (var i = 0; i < n; i++) { var t = i / (n - 1), nm = normal(c, i), w = (w0 + (w1 - w0) * t) / 2;
      L.push([c[i][0] + nm[0] * w, c[i][1] + nm[1] * w]); R.push([c[i][0] - nm[0] * w, c[i][1] - nm[1] * w]); }
    function cap(a, b, w) { var d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1; return [a[0] + (a[0] - b[0]) / d * w * .9, a[1] + (a[1] - b[1]) / d * w * .9]; }
    return smooth([cap(c[0], c[1], w0 / 2)].concat(L, [cap(c[n - 1], c[n - 2], w1 / 2)], R.reverse()), true);
  }
  function line(c) { return 'M' + c.map(function (p) { return f(p[0]) + ',' + f(p[1]); }).join(' L'); }
  function angAt(c, t) { var i = Math.max(1, Math.min(c.length - 2, Math.round(t * (c.length - 1)))); return Math.atan2(c[i + 1][1] - c[i - 1][1], c[i + 1][0] - c[i - 1][0]); }
  function at(c, t) { return c[Math.round(t * (c.length - 1))]; }

  // ---- symbols (leaf variants, bud, flowers): defined once per page ----
  var LEAVES = [{ L: 60, W: 22, curl: 6, asym: .8 }, { L: 52, W: 24, curl: -4, asym: .95 }, { L: 68, W: 18, curl: 9, asym: .7 }];
  function leafSym(o) {
    var L = o.L, W = o.W, c = o.curl, a = o.asym, mr = 'Q' + f(L * .5) + ',' + f(c * .35 + 1);
    var up = 'M0,0 C' + f(L * .18) + ',' + f(-W * .95) + ' ' + f(L * .68) + ',' + f(-W * .85 + c) + ' ' + f(L) + ',' + f(c) + ' ' + mr + ' 0,0 Z';
    var lo = 'M0,0 ' + mr + ' ' + f(L) + ',' + f(c) + ' C' + f(L * .72) + ',' + f(W * .62 * a + c) + ' ' + f(L * .22) + ',' + f(W * .72 * a) + ' 0,0 Z';
    var veins = [[.3, 1], [.5, 1], [.42, -.8], [.62, -.7]].map(function (v) { var t = v[0], s = v[1];
      return 'M' + f(L * t) + ',' + f(c * .35 * t * 2 * (1 - t) * 2 + .6) + ' q' + f(L * .09) + ',' + f(-W * .28 * s) + ' ' + f(L * .16) + ',' + f(-W * .38 * s); }).join(' ');
    return '<path d="' + up + ' ' + lo + '" transform="translate(2.5,2.5)" fill="#1F3A22" fill-opacity=".22"/><path d="' + up + '" fill="var(--la)"/><path d="' + lo + '" fill="var(--lb)"/><path d="' + up + ' ' + lo + '" fill="url(#pd-leaf)"/>' +
      '<path d="M' + f(L * .04) + ',0.3 ' + mr + ' ' + f(L * .93) + ',' + f(c * .95) + '" fill="none" stroke="var(--r-rib)" stroke-opacity=".55" stroke-width="1.1" stroke-linecap="round"/>' +
      '<path d="' + veins + '" fill="none" stroke="var(--r-rib)" stroke-opacity=".25" stroke-width=".7" stroke-linecap="round"/>';
  }
  function petal(l, w) {
    var P = function (x, y) { return f(x) + ',' + f(y); };
    return 'M0,0 C' + P(w, -l * .25) + ' ' + P(w * 1.05, -l * .8) + ' ' + P(w * .3, -l) +
      ' C' + P(w * .1, -l * 1.03) + ' ' + P(0, -l * .94) + ' ' + P(0, -l * .94) +
      ' C' + P(0, -l * .94) + ' ' + P(-w * .1, -l * 1.03) + ' ' + P(-w * .3, -l) +
      ' C' + P(-w * 1.05, -l * .8) + ' ' + P(-w, -l * .25) + ' 0,0Z';
  }
  function flowerSym(state, r) {
    r = r || 14; var o = '';
    if (state === 'closed') return '<path d="M0,0 C-6,-4 -6,-14 0,-20 C6,-14 6,-4 0,0Z" fill="var(--fc)"/><path d="M0,0 C-3,-5 -2,-12 1,-17" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1" stroke-linecap="round"/><path d="M0,0 C-7,-2 -9,-8 -8,-11 C-4,-7 -2,-4 0,0Z M0,0 C7,-2 9,-8 8,-11 C4,-7 2,-4 0,0Z" fill="var(--r-sepal)"/>';
    if (state === 'half') {
      [[-38, .85], [38, .85], [-14, 1], [14, 1], [0, .9]].forEach(function (p) { o += '<path transform="rotate(' + p[0] + ') scale(' + f(p[1] * .75) + ',' + p[1] + ')" d="' + petal(r * 1.1, r * .5) + '" fill="var(--fc)" stroke="#000" stroke-opacity=".08" stroke-width=".6"/>'; });
      return o + '<path d="M0,0 C-8,-1 -10,-6 -10,-9 C-5,-6 -2,-3 0,0Z M0,0 C8,-1 10,-6 10,-9 C5,-6 2,-3 0,0Z" fill="var(--r-sepal)"/>';
    }
    for (var i = 0; i < 5; i++) { var a = i * 72 + (i % 2 ? 3 : -3);
      o += '<path transform="rotate(' + a + ')" d="' + petal(r, r * .55) + '" fill="var(--fc)" stroke="#000" stroke-opacity=".08" stroke-width=".6"/><path transform="rotate(' + a + ')" d="' + petal(r, r * .55) + '" fill="url(#pd-petal)"/>' +
           '<path transform="rotate(' + a + ')" d="M0,-3 Q1,' + f(-r * .5) + ' 0,' + f(-r * .8) + '" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width=".8" stroke-linecap="round"/>'; }
    var pts = []; for (var k = 0; k < 12; k++) { var t = k * Math.PI / 6; pts.push([Math.cos(t) * 3.6 * (1 + .08 * Math.sin(5 * t)), Math.sin(t) * 3.6]); }
    o += '<path d="' + smooth(pts, true) + '" fill="var(--fcc)"/>';
    for (k = 0; k < 6; k++) { t = k * Math.PI / 3 + .3; o += '<circle cx="' + f(Math.cos(t) * 1.8) + '" cy="' + f(Math.sin(t) * 1.8) + '" r=".55" fill="#6B4A2F" opacity=".7"/>'; }
    return o;
  }
  var BUD = '<path d="M0,0 C4,-3 10,-6 16,-2 C19,0 19,3 16,4 C10,7 4,4 0,0 Z" fill="var(--r-bud)"/><path d="M0,0 C5,-1 10,-1 16,1" fill="none" stroke="#4E9A4F" stroke-width=".9" stroke-linecap="round"/><path d="M0,0 C3,-5 7,-6 9,-5 C6,-3 3,-1 0,0Z M0,0 C3,4 7,5 9,4 C6,3 3,1 0,0Z" fill="var(--r-sepal)"/>';
  function ensureDefs() {
    if (document.getElementById('roots-defs')) return;
    var s = document.createElementNS(NS, 'svg'); s.id = 'roots-defs'; s.setAttribute('aria-hidden', 'true');
    s.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden');
    s.innerHTML = '<defs>' + LEAVES.map(function (o, i) { return '<symbol id="rl' + i + '" overflow="visible">' + leafSym(o) + '</symbol>'; }).join('') +
      '<symbol id="rbud" overflow="visible">' + BUD + '</symbol>' + /*v8*/
      '<linearGradient id="pd-kraft" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F4E4C6"/><stop offset=".55" stop-color="#E9D3AE"/><stop offset="1" stop-color="#CDAE80"/></linearGradient>' +
      '<linearGradient id="pd-lit" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".5" stop-color="#fff" stop-opacity=".08"/><stop offset=".6" stop-color="#000" stop-opacity=".18"/><stop offset="1" stop-color="#000" stop-opacity=".32"/></linearGradient>' +
      '<linearGradient id="pd-litw" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#A87B55" stop-opacity=".35"/><stop offset=".5" stop-color="#A87B55" stop-opacity=".13"/><stop offset=".6" stop-color="#000" stop-opacity=".18"/><stop offset="1" stop-color="#000" stop-opacity=".32"/></linearGradient>' +
      '<linearGradient id="pd-leaf" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity=".30"/><stop offset=".5" stop-color="#000" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".25"/></linearGradient>' +
      '<radialGradient id="pd-petal" gradientUnits="userSpaceOnUse" cx="0" cy="0" r="14.7"><stop offset="0" stop-color="#000" stop-opacity=".38"/><stop offset=".3" stop-color="#000" stop-opacity=".18"/><stop offset=".7" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".08"/></radialGradient>' +
      '<linearGradient id="pd-soil" gradientUnits="userSpaceOnUse" x1="0" y1="396" x2="0" y2="840"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset=".02" stop-color="#fff" stop-opacity=".12"/><stop offset=".035" stop-color="#fff" stop-opacity="0"/><stop offset=".035" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".30"/></linearGradient>' +
      ['closed', 'half', 'open'].map(function (st) { return '<symbol id="rf-' + st + '" overflow="visible">' + flowerSym(st) + '</symbol>'; }).join('') + '</defs>';
    document.body.appendChild(s);
  }

  // ---- labels ----
  function days(n) { return n <= 0 ? (n === 0 ? 'today' : 'overdue') : n === 1 ? 'tomorrow' : 'in ' + n + ' days'; }
  function short(d) { try { return new Date(d + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); } catch (e) { return d; } }
  function hrs(m) { var h = (m || 0) / 60; return h < 1 ? Math.round(m || 0) + ' min' : (h < 10 ? Math.round(h * 10) / 10 : Math.round(h)) + ' h'; }
  var PAD = 12; /*v7*/
  function clampX(x, side, w, W) { return side > 0 ? Math.min(x, W - PAD - w) : Math.max(x, PAD + w); }
  function pill(x, y, anchor, txt, fs, cls, dot) { /*v3*/
    var dw = dot ? fs * .9 : 0, w = txt.length * fs * .5 + 12 + dw, h = fs + 8, rx = anchor === 'start' ? x - 6 : anchor === 'end' ? x - w + 6 : x - w / 2;
    return '<g class="r-pill' + cls + '"><rect x="' + f(rx) + '" y="' + f(y - h / 2) + '" width="' + f(w) + '" height="' + f(h) + '" rx="4"/>' +
      (dot ? '<circle class="r-dot" cx="' + f(rx + 6 + fs * .3) + '" cy="' + f(y) + '" r="' + f(fs * .3) + '" style="fill:' + esc(dot) + '"/>' : '') +
      '<text x="' + f(rx + 6 + dw) + '" y="' + f(y + fs * .35) + '" text-anchor="start" style="font-size:' + f(fs) + 'px">' + esc(txt) + '</text></g>';
  }
  function lblY(y, tipY, k, floor) { /*v10*/  // keep the whole block (name + days line) >=36px above the floor, else move it up beside the tip
    return y + 4 + 18 * k > floor - 36 ? Math.min(tipY - 18 * k, floor - 36 - 22 * k) : y;
  }
  function wallOut(el, b) {  // v19: px of screen box b outside the inner pot wall + 6px (0 when clear / no pot / above the rim)
    var st = el._roots, sv = el.querySelector('svg'), M = sv && sv.getScreenCTM(); if (!st || !st.pot || !M) return 0;
    var rb = st.Y + 18, yb = (b[3] - M.f) / M.d; if (yb < st.Y - 12) return 0;
    var yl = st.H - 48 - 30, t = Math.max(0, Math.min(1, (yb - rb) / (yl - rb))), lim = 26 + 26 * t + 6;
    var x0 = M.e + lim * M.a, x1 = M.e + (st.W - lim) * M.a; return Math.max(0, x0 - b[0]) + Math.max(0, b[2] - x1); }
  function placeTags(el) { /*v12*/ /*v12b*/  // search tie point x drop x side; least overlap with foliage, labels, bud, ground/pot rim and placed tags
    var tags = [].slice.call(el.querySelectorAll('.r-tag[data-cand]')); if (!tags.length) return;
    var narrow = el._roots && el._roots.narrow, drops = narrow ? [22, 28, 34, 50, 66, 78, 90] : [34, 50, 66];
    el.classList.add('r-measure');
    function box(n) { var r = n.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }
    function ov(a, b) { var w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]); return w > 0 && h > 0 ? w * h : 0; }
    var obs = [].slice.call(el.querySelectorAll('.r-rtext text,.r-addbud .r-budin,.stub .r-stubhit,.r-badge,.r-soil')).map(box); /*v13*/
    var foli = [].slice.call(el.querySelectorAll('use[href^="#rl"],use[href^="#rf"],use[href^="#rsp"]')), fb0 = foli.map(function (u) { var b = box(u), ix = (b[2] - b[0]) * .18, iy = (b[3] - b[1]) * .18; return [b[0] + ix, b[1] + iy, b[2] - ix, b[3] - iy]; });  // perf v26: leaf/flower shapes ~ inset boxes, measured once
    function hits(b) {  // sample a 6x4 grid inside the tag against the foliage boxes (pure math)
      var near = fb0.filter(function (o) { return ov(b, o) > 0; }); if (!near.length) return 0; var n = 0;
      for (var i = 0; i < 6; i++) for (var j = 0; j < 4; j++) { var x = b[0] + (b[2] - b[0]) * (.08 + .84 * i / 5), y = b[1] + (b[3] - b[1]) * (.15 + .7 * j / 3);
        for (var q = 0; q < near.length; q++) { var o = near[q]; if (x >= o[0] && x <= o[2] && y >= o[1] && y <= o[3]) { n++; break; } } }
      return n; }
    var SM = el.querySelector('svg').getScreenCTM();
    var soilB = el.querySelector('.r-soil'); if (soilB && el.querySelector('.r-potring')) { var sb = box(soilB), k = el.clientWidth / (el._roots.W || 900); obs.push([sb[0] - 20, sb[1] - 14 * k, sb[2] + 20, sb[3]]); }  // pot rim sits 12px above the soil line
    var sv = el.querySelector('svg').getBoundingClientRect(), E = narrow ? 8 : 0; function edges(E) { return [[sv.left - 99, sv.top - 99, sv.left + E, sv.bottom], [sv.right - E, sv.top - 99, sv.right + 99, sv.bottom], [sv.left, sv.top - 99, sv.right, sv.top + E]]; } var obs0 = obs.slice(); obs = obs0.concat(edges(E));  // stay inside the card
    var placed = [];
    tags.forEach(function (g) {
      var str = g.querySelector('.r-string'), body = g.querySelector('.r-tagbody'), tx = g.querySelector('text'), cx = +tx.getAttribute('x');
      var bt0 = body.dataset.bt || (body.dataset.bt = body.getAttribute('transform').replace(/^translate\([^)]*\)/, ''));
      var cand = g.dataset.cand.split(' '); if (!narrow) cand = cand.slice(0, 5);
      var GEO = {};  // perf v26: one real measurement per scale; every candidate box is derived in math
      function geo(sc) { if (GEO[sc]) return GEO[sc]; var p0 = cand[0].split(','), b = put(cand[0], 0, false, sc, true), ox = +p0[0] * SM.a + SM.e, oy = +p0[1] * SM.d + SM.f; return (GEO[sc] = [b[0] - ox, b[1] - oy, b[2] - ox, b[3] - oy]); }
      function boxAt(pt, dr, flip, sc) { var r = geo(sc), p = pt.split(','), ox = +p[0] * SM.a + SM.e, oy = +p[1] * SM.d + SM.f + dr * SM.d;
        return flip ? [ox - r[2], oy + r[1], ox - r[0], oy + r[3]] : [ox + r[0], oy + r[1], ox + r[2], oy + r[3]]; }
      function put(pt, dr, flip, sc, measure) {
        var bt = sc === 1 ? bt0 : bt0.replace(/scale\(([\d.]+)\)/, function (m, v) { return 'scale(' + f(v * sc) + ')'; });
        g.setAttribute('transform', 'translate(' + pt + ')'); body.setAttribute('transform', 'translate(0,' + dr + ')' + (flip ? ' scale(-1,1)' : '') + bt);
        if (flip) tx.setAttribute('transform', 'translate(' + f(2 * cx) + ',0) scale(-1,1)'); else tx.removeAttribute('transform');
        return box(body);
      }
      function search(sc) { var best = null;
        cand.forEach(function (pt) { drops.forEach(function (dr) { [false, true].forEach(function (fl) {
          var b = boxAt(pt, dr, fl, sc), cost = 400 * wallOut(el, b); obs.forEach(function (o) { cost += ov(b, o); }); placed.forEach(function (o) { cost += (narrow ? 60 : 1) * ov(b, o); });  /*v30: phone tags never overlap each other*/ if (cost < 1) cost += 400 * hits(b);
          cost += (fl ? .5 : 0) + dr / 1000;  // prefer unflipped, shorter drops when equally clear
          if (!best || cost < best.cost) best = { cost: cost, pt: pt, dr: dr, fl: fl, sc: sc };
        }); }); }); return best; }
      var best = search(1);
      if (narrow && best.cost >= 1) {  // shrink tag until its text is exactly 11px, then search again
        put(best.pt, best.dr, best.fl, 1); var px = tx.getBoundingClientRect().height / 1.2, cs = parseFloat(tx.style.fontSize) || 11;
        var m = tx.getScreenCTM(), now = cs * Math.hypot(m.a, m.b), sc = Math.min(1, 11 / now); if (sc < .999) { var b2 = search(sc); if (b2.cost < best.cost) best = b2; }
      }
      if (narrow && best.cost >= 1) { /*v18b*/ var d0 = drops; drops = []; for (var dd = 34; dd <= 90; dd += 4) drops.push(dd); var b5 = search(best.sc); if (b5.cost < best.cost) best = b5; drops = d0; }
      if (narrow && best.cost >= 1) { var keep = obs; obs = obs0.concat(edges(4)); var b4 = search(best.sc); if (b4.cost < best.cost) best = b4; obs = keep; }  // last resort: 4px card inset for this tag
      var fb = put(best.pt, best.dr, best.fl, best.sc);
      str.setAttribute('d', 'M0,0 C-2,' + f(best.dr * .35) + ' 2,' + f(best.dr * .6) + ' 0,' + best.dr);
      g.dataset.overlap = Math.floor(best.cost); placed.push(narrow ? [fb[0] - 2, fb[1] - 2, fb[2] + 2, fb[3] + 2] : fb);
    });
    el.classList.remove('r-measure');
    var svg0 = el.querySelector('svg'), top = svg0.querySelector('.r-tagtop') || svg0.appendChild(svgEl('g', { class: 'r-tagtop' }));  // v33: tags paint above every leaf/flower
    tags.forEach(function (g) { var it = g.closest('.r-item'); if (!it) return; var w = svgEl('g', { class: 'r-item r-tagwrap', 'data-type': it.dataset.type, 'data-id': it.dataset.id }); top.appendChild(w); w.appendChild(g); });
  }
  function placeStubs(el) {  // v27 Design spec: 44px hit area >=12px clear of every tag box, >=16px inside the garden; else move up one slot
    var stubs = [].slice.call(el.querySelectorAll('.stub[data-slots]')); if (!stubs.length) return;
    var sv = el.querySelector('svg'), M = sv.getScreenCTM(); if (!M) return; var k = M.a, sr = sv.getBoundingClientRect();
    var tags = [].slice.call(el.querySelectorAll('.r-tag .r-tagbody')).map(function (n) { var r = n.getBoundingClientRect(); return [r.left - 12, r.top - 12, r.right + 12, r.bottom + 12]; }), used = [];
    stubs.forEach(function (g) { var th = +g.dataset.th * Math.PI / 180, up = g.dataset.slots.split(' '), low = (g.dataset.lows || '').split(' ').filter(Boolean), pick = null, best = null;
      function test(sl) { var p = sl.split(','), x = +p[0], y = +p[1], cx = x + 10 * Math.sin(th), cy = y - 10 * Math.cos(th);  // hit-area centre ~10 units up the stub
        var X = cx * M.a + M.e, Y = cy * M.d + M.f, h = 22 * k, b = [X - h, Y - h, X + h, Y + h];
        var gap = Math.min.apply(null, [1e9].concat(tags.concat(used).map(function (t) { return Math.max(t[0] - b[2], b[0] - t[2], t[1] - b[3], b[1] - t[3]); })));  // 0 = exactly 12px clear
        var inside = b[0] >= sr.left + 16 && b[2] <= sr.right - 16 && b[1] >= sr.top + 16; return { x: x, y: y, b: b, gap: inside ? gap : -1e9 }; }
      var all = up.map(test), lw = low.map(test).reverse();  // Design v28: up slots clear 12px -> lowest-tag-free low slot clear 12px -> any slot with >=6px -> most room
      pick = all.filter(function (q) { return q.gap >= 0; })[0] || lw.filter(function (q) { return q.gap >= 0; })[0] || all.concat(lw).filter(function (q) { return q.gap >= -6; })[0];
      if (!pick) all.concat(lw).forEach(function (q) { if (!best || q.gap > best.gap) best = q; }); pick = pick || best;
      g.dataset.gap = Math.round(pick.gap + 12); pick = [pick.x, pick.y, pick.b];
      g.setAttribute('transform', 'translate(' + pick[0] + ',' + pick[1] + ') rotate(' + g.dataset.th + ')'); used.push(pick[2]); });
  }
  function placeLabels(el, floorY) {  // each deadline label stays near its own tip; avoid every root shape (own included) and other labels
    var sv = el.querySelector('svg'), M = sv.getScreenCTM(); if (!M) return; var Mi = M.inverse(), roots = [].slice.call(el.querySelectorAll('.r-root:not(.r-shade)')), placed = [], narrow = el._roots && el._roots.narrow;
    var pt = sv.createSVGPoint(), k = M.a;
    function box(n) { var r = n.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }
    function ov(a, b) { var w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]); return w > 0 && h > 0 ? w * h : 0; }
    // perf v26: roots as precomputed screen-space capsule segments (centerline + half width), pure math, no DOM in the search loop
    var SEG = []; el.querySelectorAll('.r-item[data-type=root]').forEach(function (it) { var hp = it.querySelector('.r-hitp'), rp = it.querySelector('.r-root:not(.r-shade)'); if (!hp || !rp) return;
      var L = hp.getTotalLength(), n = Math.max(6, Math.min(40, Math.round(L / 14))), bb = rp.getBBox(), w0 = Math.min(bb.width, CFG.root.wMax + 2) / 2, prev = null;
      for (var i = 0; i <= n; i++) { var e = hp.getPointAtLength(L * i / n), q = [e.x * M.a + M.e, e.y * M.d + M.f], hw = (Math.max(.6, w0 * (1 - i / n) + .5) + 1.5) * k;
        if (prev) SEG.push([prev[0], prev[1], q[0], q[1], Math.max(prev[2], hw), Math.min(prev[0], q[0]) - hw, Math.min(prev[1], q[1]) - hw, Math.max(prev[0], q[0]) + hw, Math.max(prev[1], q[1]) + hw]);
        prev = [q[0], q[1], hw]; } });
    function segHit(x, y) { for (var i = 0; i < SEG.length; i++) { var s = SEG[i]; if (x < s[5] || x > s[7] || y < s[6] || y > s[8]) continue;
      var dx = s[2] - s[0], dy = s[3] - s[1], l2 = dx * dx + dy * dy || 1, t = Math.max(0, Math.min(1, ((x - s[0]) * dx + (y - s[1]) * dy) / l2)), ex = s[0] + t * dx - x, ey = s[1] + t * dy - y;
      if (ex * ex + ey * ey <= s[4] * s[4]) return true; } return false; }
    function rootHits(b) { var n = 0, nx = Math.max(6, Math.min(30, Math.round((b[2] - b[0]) / 4))); for (var i = 0; i < nx; i++) for (var j = 0; j < 4; j++) if (segHit(b[0] + (b[2] - b[0]) * i / (nx - 1), b[1] + (b[3] - b[1]) * j / 3)) n++; return n * 420 / (nx * 4); }  // same scale as the old 60x7 grid
    var floor = M.f + floorY * k, sr = sv.getBoundingClientRect();
    el.querySelectorAll('.r-rlbl .r-rtext').forEach(function (g) {
      var it0 = el.querySelector('.r-item[data-type=root][data-id="' + g.parentNode.dataset.id + '"]'), hp = it0 && it0.querySelector('.r-hitp'), tip = null; if (hp) { var e = hp.getPointAtLength(hp.getTotalLength()); tip = [e.x * M.a + M.e, e.y * M.d + M.f]; }
      function far(b) { return tip ? Math.hypot(Math.max(b[0] - tip[0], 0, tip[0] - b[2]), Math.max(b[1] - tip[1], 0, tip[1] - b[3])) : 0; }
      var R0 = narrow ? 20 : 26, steps = [0, -1, 1, -2, 2, -3, 3, -4, 4, -5, 5];  // v36: desktop searches wider too (spread anchors + vertical nudges)  /*v17*/ // phone: 10px steps up to 50px
      function search(fine) { /*v19c*/ var best = null, st2 = fine ? [] : steps; if (fine) for (var q = -10; q <= 10; q++) st2.push(q / 2);
        g.removeAttribute('transform'); var b0 = box(g);  // perf: measure once, then translate the box in math
        st2.forEach(function (sy) { st2.forEach(function (sx) {
          var dx = sx * R0 / 2 / k, dy = sy * R0 / 2 / k, b = [b0[0] + dx * M.a, b0[1] + dy * M.d, b0[2] + dx * M.a, b0[3] + dy * M.d];
          var cost = 50 * Math.ceil(rootHits(b) / 2) + Math.abs(sx) + Math.abs(sy) * .8; placed.forEach(function (o) { cost += ov(b, o); });
          if (narrow && far(b) > 50) cost += 1e6; if (b[3] > floor) cost += 1e4; if (b[0] < sr.left + 4 || b[2] > sr.right - 4 || wallOut(el, b) > 0) cost += 1e4;
          if (!best || cost < best.cost) best = { cost: cost, dx: dx, dy: dy, b: b };
        }); }); return best; }
      var best = search();
      if (narrow && best.cost >= 50) {  // v33: no 8-char retry (labels wrap); fine pass + date fallback
        var bf = search(true); if (bf.cost < best.cost) best = bf;
        if (best.cost >= 50 && g.dataset.alt) { var tx = g.querySelector('text'), old2 = tx.innerHTML; tx.textContent = g.dataset.alt; var b3 = search(true); if (b3.cost < best.cost) best = b3; else tx.innerHTML = old2; }
      }
      g.setAttribute('transform', 'translate(' + f(best.dx) + ',' + f(best.dy) + ')'); g.dataset.hits = Math.floor((best.cost % 1e4) / 50); g.dataset.far = Math.round(far(best.b)); g.classList.toggle('r-halo', narrow && best.cost >= 50); placed.push(best.b);
    });
  }
  function rtext(x, y, anchor, a, b, k, alt) { /*v33 Design patch: a may be an array of lines*/
    var lines = Array.isArray(a) ? a : [a], fs = (Array.isArray(a) ? 11 : 12.5) * k, lh = (Array.isArray(a) ? 12.5 : 14) * k;
    var body = esc(lines[0]); for (var i = 1; i < lines.length; i++) body += '<tspan x="' + f(x) + '" dy="' + f(lh) + '">' + esc(lines[i]) + '</tspan>';
    return '<g class="r-pill r-rtext"' + (alt ? ' data-alt="' + esc(alt) + '"' : '') + '><text x="' + f(x) + '" y="' + f(y + 4) + '" text-anchor="' + anchor + '" style="font-size:' + f(fs) + 'px">' + body +
      (b ? '<tspan class="r-rdays" x="' + f(x) + '" dy="' + f(14 * k) + '" style="font-size:' + f(11 * k) + 'px">' + esc(b) + '</tspan>' : '') + '</text></g>';
  }
  function tag(px, py, code, col, k, drop, side, cand) { /*v12d*/  // STYLE.md "Garden tag" v3; text stays 11px, the tag widens instead
    code = String(code || '').toUpperCase().slice(0, 9); var fs = 11, mw = code.length * fs * .7 + 2, W = 64, H = 24, P = 10;
    if (23 + mw > 64) { W = Math.max(70, Math.ceil(23 + mw)); H = 30; P = 12; }
    var body = 'M6 0 H' + (W - P) + ' L' + W + ' ' + H / 2 + ' L' + (W - P) + ' ' + H + ' H6 A6 6 0 0 1 0 ' + (H - 6) + ' V6 A6 6 0 0 1 6 0 Z';
    return '<g class="r-tag"' + (cand ? ' data-cand="' + cand + '"' : '') + ' transform="translate(' + f(px) + ',' + f(py) + ')">' +
      '<ellipse class="r-tie" rx="3.2" ry="1.6"/><path class="r-string" d="M0,0 C-2,' + f(drop * .35) + ' 2,' + f(drop * .6) + ' 0,' + f(drop) + '" vector-effect="non-scaling-stroke"/>' +
      '<g class="r-tagbody" transform="translate(0,' + f(drop) + ') scale(' + f(k) + ') rotate(-6) translate(-7,' + (-H / 2) + ')">' +
      '<path d="' + body + '" transform="translate(1.5,2)" fill="#3B2A1E" fill-opacity=".18"/><path class="r-tagfill" d="' + body + '"/>' +
      '<path d="M5,0 H' + (W - P) + ' L' + f(W - P + P * 4 / H) + ',2 H1.5 Q2.5,.4 5,0 Z" style="fill:' + esc(col) + '"/>' +
      '<path class="r-tagpt" d="M' + (W - P) + ' 0 L' + W + ' ' + H / 2 + ' L' + (W - P) + ' ' + H + '"/>' +
      '<circle class="r-hole" cx="7" cy="' + H / 2 + '" r="2.2"/><circle class="r-lip" cx="7.4" cy="' + (H / 2 + .6) + '" r="2.2"/>' +
      '<circle cx="14" cy="' + H / 2 + '" r="3" style="fill:' + esc(col) + '"/>' +
      '<text x="' + f((18 + W - 5) / 2) + '" y="' + f(H / 2 + .36 * fs) + '" text-anchor="middle" style="font-size:' + fs + 'px">' + esc(code) + '</text></g></g>';
  }
  var ACC = ['#D9653B', '#3E7CB1', '#8A5CB8', '#2F8F6B', '#C9A227', '#C2476E', '#5B6F2E', '#7A4E2D'];
  function hsl(hex) { var r = parseInt(hex.substr(1, 2), 16) / 255, g = parseInt(hex.substr(3, 2), 16) / 255, b = parseInt(hex.substr(5, 2), 16) / 255,
    mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn; return { s: d ? d / (1 - Math.abs(2 * l - 1)) : 0, l: l, rgb: [r, g, b] }; }
  function accents(br) { /*v4*/  // one accent per course, shared by branch chip, root dot and root tint
    var ok = /^#[0-9a-f]{6}$/i, cols = br.map(function (b) { return ok.test(b.color || '') ? hsl(b.color) : null; }), weak = cols.some(function (c) { return !c || c.s < .45 || c.l > .75; });
    for (var i = 0; !weak && i < cols.length; i++) for (var j = i + 1; j < cols.length; j++) { var a = cols[i].rgb, b = cols[j].rgb; if (Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < .25) weak = true; }
    var ids = br.map(function (b) { return b.course_id; }).sort(function (a, b) { return a - b; }), m = {};
    br.forEach(function (b) { m[b.course_id] = (/^#[0-9a-f]{6}$/i.test(b.dot || '') && b.dot) || (weak ? ACC[ids.indexOf(b.course_id) % ACC.length] : b.color); });
    return m;
  }
  function sweep(el) {  // nudge overlapping root-label pills apart vertically
    var ps = [].slice.call(el.querySelectorAll('.r-under .r-pill')), placed = [];
    ps.map(function (g) { var b = g.getBBox(); return { g: g, x: b.x, y: b.y, w: b.width, h: b.height }; })
      .sort(function (a, b) { return a.y - b.y; }).forEach(function (q) {
        var dy = 0, moved = true;
        for (var guard = 0; moved && guard < 12; guard++) { moved = false;
          placed.forEach(function (o) { if (q.x < o.x + o.w && o.x < q.x + q.w && q.y + dy < o.y + o.h + 3 && o.y < q.y + dy + q.h + 3) { dy = o.y + o.h + 3 - q.y; moved = true; } }); }
        if (dy) q.g.setAttribute('transform', 'translate(0,' + f(dy) + ')');
        placed.push({ x: q.x, y: q.y + dy, w: q.w, h: q.h });
      });
  }
  function shade(hex, dh, dl) {
    var r = parseInt(hex.substr(1, 2), 16) / 255, g = parseInt(hex.substr(3, 2), 16) / 255, b = parseInt(hex.substr(5, 2), 16) / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn, hh = 0, ss = d ? d / (1 - Math.abs(2 * l - 1)) : 0;
    if (d) hh = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return 'hsl(' + f((hh * 60 + dh + 360) % 360) + ',' + f(ss * 100) + '%,' + f(Math.max(5, Math.min(90, l * 100 + dl))) + '%)';
  }
  function wrap2(s, n) { /*v33 Design patch*/ // <=2 lines of ~n chars at word breaks; clip only past 2 lines
    var w = String(s || '').split(/\s+/), L = [''], i;
    for (i = 0; i < w.length; i++) { var c = L[L.length - 1], t = c ? c + ' ' + w[i] : w[i];
      if (t.length <= n || !c) L[L.length - 1] = t; else if (L.length < 2) L.push(w[i]); else { L[1] = clip(L[1] + ' ' + w.slice(i).join(' '), n + 2); break; } }
    return L;
  }
  function clip(s, n) { s = String(s || ''); return s.length > n ? s.slice(0, n - 1).replace(/\s+$/, '') + '…' : s; }

  // ---- render ----
  function render(el, data, opt) { /*v5*/
    opt = opt || {}; if (opt.popN) { el._popN = opt.popN; el._popT = Date.now(); } else if (el._popN && Date.now() - el._popT < 4000 && opt.pop == null) opt.popN = el._popN; /*v20d*/ var G = opt.intro === 'grow', NEW = opt.newIds || {}; /*v5b*/
    var SP = species(el, data); var GD = garden(el, data), LP = GD.leaves && GD.leaves.leaf_pairs; PAD = GD.pot ? 64 : 12;
    ensureDefs();
    var narrow = el.clientWidth && el.clientWidth < CFG.narrowBelow, W = narrow ? CFG.Wnarrow : CFG.W, Y = narrow && !opt.mini ? 540 : CFG.ground,  /*v33 phone: tree ~60% / pot ~40%*/ H = CFG.H, tx = W / 2;
    var br = (data.branches || []).slice(0, 8), rt = (data.roots || []).slice(0, CFG.root.maxN);
    var o = [], items = {}, AC = accents((data.branches || []).slice(0, 8)), FS = Math.max(12, 12.5 / ((el.clientWidth || W) / W));
    o.push('<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Your semester tree: ' + br.length + ' courses above ground, ' + rt.length + ' upcoming deadlines below">');
    // above ground
    o.push('<g class="r-above">'); var canIdx = o.length; o.push(''); var crownTop = Y, lowJ = 0;
    var top = Y - CFG.trunk.top - 40 - Math.max(0, br.length - 4) * 18 - (narrow && !opt.mini ? 60 : 0);
    var trunk = br.length ? curve([tx, Y + 6], [tx - 8, Y - 70], [tx + 10, Y - 150], [tx, top], 50, CFG.trunk.wob, 9, 3) : null;
    var budAt = null;
    if (trunk) { o.push('<path class="r-trunk r-rise" d="' + taper(trunk, CFG.trunk.w0, CFG.trunk.w1, CFG.trunk.bumps) + '"/>');
      if (G) o.push('<g class="r-seed" transform="translate(' + f(tx) + ',' + f(Y + 2) + ')"><g class="r-seed-in"><ellipse rx="9" ry="6" fill="#8A6242"/><path d="M0,-4 C-2,-12 -10,-16 -14,-12 C-10,-10 -5,-8 0,-4 Z M0,-4 C2,-12 10,-16 14,-12 C10,-10 5,-8 0,-4 Z" fill="var(--r-bud)"/></g></g>');
      var tt = trunk[trunk.length - 1], ta = angAt(trunk, 1) * 180 / Math.PI; budAt = [tt[0], tt[1] + 2];
    }
    var trunkTop = top, trunkLen = (Y + 6) - top;
    var dark = function () { return document.documentElement.getAttribute('data-theme') === 'dark'; }, hiTip = Y, loTip = 0;
    var reachMax = narrow ? W / 2 - 40 : 300, hiJ = Y, KIT = window.prodyBranchKit || null;  // 3d design 1's branch_kit (barkFromPoints, flowerSlots) when loaded; stub art otherwise
    /*v33 branch len = school-term progress. Term dates aren't stored: start = earliest deadline - 14d, end = latest deadline (data.roots + data.later),
      default Aug 19 - Dec 12 of this year when fewer than 2 dates. len = clamp((today - start) / (end - start), .15, 1) */
    var TF = (function () { var now = new Date(), ds = (data.roots || []).concat(data.later || []).map(function (d) { return d.due ? new Date(d.due + 'T12:00:00') : null; }).filter(function (d) { return d && !isNaN(d); }).sort(function (x, y) { return x - y; });
      var s0, e0; if (data.term && data.term.start && data.term.end) { s0 = new Date(data.term.start + 'T00:00:00'); e0 = new Date(data.term.end + 'T23:59:59'); }
      else if (ds.length >= 2 && ds[ds.length - 1] - ds[0] > 7 * 864e5) { s0 = new Date(+ds[0] - 14 * 864e5); e0 = ds[ds.length - 1]; }
      else { s0 = new Date(now.getFullYear(), 7, 19); e0 = new Date(now.getFullYear(), 11, 12); }
      return Math.max(.15, Math.min(1, (now - s0) / (e0 - s0))); })();
    el.dataset.termFrac = TF.toFixed(3);
    var JT = br.map(function (b, i) { var q = rng(b.course_id * 53 + 11); return (narrow ? .58 : .42) + (narrow ? .34 : .44) * (br.length > 1 ? i / (br.length - 1) : .5) + (q() - .5) * .04; });  // v35 phone: joints in the upper ~45% of the trunk; staggered, never level pairs
    br.forEach(function (b, ci) {
      var side = ci % 2 ? 1 : -1, h = (b.minutes || 0) / 60, r = rng(b.course_id * 7 + 1);
      var g = Math.min(1, Math.log(1 + h) / Math.log(1 + CFG.branch.fullHours));
      var reach = reachMax * (CFG.branch.minReach + (1 - CFG.branch.minReach) * g);
      var jt = JT[ci];
      var a = at(trunk, jt), ay = a[1]; lowJ = Math.max(lowJ, ay); hiJ = Math.min(hiJ, ay);
      reach = reachMax * TF * (.9 + .2 * r()) * (1 - .3 * jt);  // v33: length = term progress; higher joints a bit shorter
      var angD = 20 + 15 * r(), ang = angD * Math.PI / 180, e = [a[0] + side * reach * Math.cos(ang), ay - reach * Math.sin(ang)];  // 20-35deg upward
      var BR = { x: a[0], y: ay, angle: angD, len: TF, side: side < 0 ? 'l' : 'r', seed: b.course_id };  // kit data shape
      var push = (6 + 8 * r()) * (r() < .5 ? -1 : 1), dx = e[0] - a[0], dy = e[1] - a[1], L = Math.hypot(dx, dy) || 1, nx = -dy / L * push, ny = dx / L * push;
      var p1 = [a[0] + dx / 3 + nx, a[1] + dy / 3 + ny], p2 = [a[0] + 2 * dx / 3 - nx, a[1] + 2 * dy / 3 - ny];
      var c = curve(a, p1, p2, e, 60, CFG.branch.wob, ci + 3, CFG.branch.freq), KB = null, hsd = 0;
      for (var hi2 = 0, hs = String(b.course_id); hi2 < hs.length; hi2++) hsd = (hsd * 31 + hs.charCodeAt(hi2)) >>> 0;  // stable seed from class id
      if (KIT && KIT.branchPath) { KB = KIT.branchPath({ x: a[0], y: ay, angle: angD, len: TF, side: side < 0 ? 'l' : 'r', seed: hsd || 1, baseWidth: 10, maxLen: reachMax * (1 - .3 * jt) * Math.max(1, .55 / TF) });  // branches stay visibly long early in term (min ~55% reach)  // kit: +angle = rises on screen
        c = KB.points; e = [KB.tip.x, KB.tip.y]; }
      hiTip = Math.min(hiTip, e[1]); loTip = Math.max(loTip, e[1]);
      var w0 = Math.max(CFG.branch.wMin, CFG.branch.w0 - ci * CFG.branch.dec);
      var la = mix(CFG.leaf.young[0], CFG.leaf.mature[0], g), lb = mix(CFG.leaf.young[1], CFG.leaf.mature[1], g);
      if (SP.leaf_color) { la = mix(SP.leaf_color, '#1F3A22', .2 * g); lb = SP.leaf_tip || mix(SP.leaf_color, '#FFFFFF', .22 * (1 - g)); }
      if (LP && LP.length) { la = LP[ci % LP.length].upper || la; lb = LP[ci % LP.length].lower || lb; }
      var dl = G ? .3 + .9 * Math.max(0, Math.min(1, (Y + 6 - ay) / trunkLen)) : 0, isNew = !!NEW[b.course_id] && budAt;
      o.push('<g class="r-item r-sway" tabindex="0" role="button" data-type="branch" data-id="' + b.course_id + '" aria-label="' + esc(b.name) + '" style="--la:' + la + ';--lb:' + lb +
        ';transform-origin:' + f(a[0]) + 'px ' + f(a[1]) + 'px;animation-delay:' + f(-ci * CFG.motion.swayPhase) + 's">' + (isNew ? '<g class="r-newbr" style="--bx:' + f(budAt[0] - a[0]) + 'px;--by:' + f(budAt[1] - a[1]) + 'px;--d:' + (G ? 2.4 : .3) + 's;transform-origin:' + f(a[0]) + 'px ' + f(a[1]) + 'px">' : '<g>'));
      o.push('<path class="r-hitp" d="' + line(c) + '"/>');
      if (KB) { var BP = dark() ? KIT.dark : KIT.light; o.push('<g class="r-branch-kit r-grow" style="--d:' + f(dl) + 's;transform-origin:' + (side < 0 ? '100%' : '0%') + ' 100%"><path fill="' + BP.bark + '" d="' + KB.base + '"/><path fill="' + BP.barkShadow + '" d="' + KB.shadow + '"/><path fill="' + BP.barkHi + '" d="' + KB.highlight + '"/>' +
        KB.ridges.map(function (rd) { return '<path fill="none" stroke="' + (rd.knot ? BP.knot : BP.ridge) + '" stroke-width="' + rd.width + '" stroke-linecap="round" d="' + rd.d + '"/>'; }).join('') + '</g>'); }
      else o.push('<path class="r-branch r-grow" style="--d:' + f(dl) + 's;transform-origin:' + (side < 0 ? '100%' : '0%') + ' 100%" d="' + taper(c, 10, 2, []) + '"/>');  // stub: 10px -> 2px taper (swap for kit)
      // leaves: 3d design 1 rules /*v2-pills*/
      var lr = rng(b.course_id * 131 + 7), nL = 0;  // v33: branches carry flowers/buds only; foliage is the canopy
      if (!(b.leaves > 0) && !(h > 0)) nL = 0;
      if (nL && SP.leafDensity !== 1) nL = Math.max(2, Math.min(14, Math.round(nL * SP.leafDensity)));
      if (!opt.mini && nL > 2) nL = Math.max(2, Math.round(nL * (narrow ? .6 : .75)));  /*v33: thinner foliage everywhere*/  /*v30 phone: fewer leaf clusters so tags breathe*/
      if (opt.mini && nL) nL = Math.max(2, Math.round(nL * (+SP.mini.leaf_density_mult || .7)));  // STYLE.md Mini render: count x0.7, min 2
      var popLast = opt.pop === b.course_id, pm = opt.popN && opt.popN[b.course_id], popN = pm ? Math.max(0, nL - (pm.m > 0 ? Math.min(14, 3 + Math.round(4 * Math.log2(1 + pm.m / 60))) : 0)) : 0, slots = [], /*v20*/ tt0 = .15, gap = .8 / Math.max(nL, 1);
      for (var k = 0; k < nL; k++) { var tk0 = tt0 + gap * (k + .5) + gap * (lr() - .5) * .6; slots.push({ t: Math.max(.15, Math.min(.95, tk0)), empty: lr() < .2 }); }
      var drawn = []; slots.forEach(function (sl, k) { if (!sl.empty) drawn.push(k); }); var popFrom = popN ? drawn[Math.max(0, drawn.length - popN)] : 1e9; /*v20c*/
      var lsd = -1, flowerSlots = [];
      slots.forEach(function (sl, k) {
        if (k > 0) flowerSlots.push((slots[k - 1].t + sl.t) / 2);
        lsd = lr() < .15 ? lsd : -lsd; if (sl.empty) return;
        var t = sl.t, p = at(c, t), tipL = t > .85, ang = 35 + lr() * 20 + (lr() - .5) * 16 - (tipL ? 10 : 0);
        var rot = angAt(c, t) * 180 / Math.PI + lsd * ang + (lr() < .25 ? (lr() < .5 ? -6 : 6) : 0);
        var sc = .9 * (1 - .45 * t) * (.8 + lr() * .35) * (opt.mini ? +SP.mini.leaf_scale_mult || 1.3 : 1) * (SP.sym ? SP.leafScale * 1.6 : 1), u = lr(), v = u < .5 ? 0 : u < .8 ? 1 : 2;
        var dh = (lr() - .5) * 12, dL = (lr() - .5) * 10 + (tipL ? 8 : 0);
        var pop = G ? ' class="r-pop" style="--d:' + f(dl + .3 + k * .03) + 's"' : (k >= popFrom ? ' class="r-pop" style="--d:' + f(.25 + (drawn.indexOf(k) - drawn.indexOf(popFrom)) * .3) + 's"' : popLast && k === nL - 1 ? ' class="r-pop"' : '');
        o.push('<g style="--la:' + shade(la, dh, dL) + ';--lb:' + shade(lb, dh, dL) + '" transform="translate(' + f(p[0]) + ',' + f(p[1]) + ') rotate(' + f(rot) + ') scale(' + f(sc) + ',' + f(sc * lsd) + ')"><use href="#' + (SP.sym || 'rl' + v) + '"' + pop + '/></g>');
      });
      crownTop = Math.min(crownTop, c.reduce(function (m, q) { return Math.min(m, q[1]); }, Y) - 30);
      var tip = c[c.length - 1], tipAng = angAt(c, 1) * 180 / Math.PI;

      // flowers at nodes between leaves: open = done, half = this course has something due within 3 days
      var fl = b.done_deadlines != null ? b.done_deadlines | 0 : Math.max(0, (b.flowers | 0) - (b.focus_flowers | 0)), soon = (data.roots || []).filter(function (d) { return d.course_id === b.course_id && d.days_left <= 3; }).length;  // v33: one flower per completed deadline (done_deadlines when present)
      if (!flowerSlots.length) flowerSlots = [.5, .65, .8, .4, .9];
      var p, fls = []; for (k = 0; k < fl; k++) fls.push('open'); for (k = 0; k < soon; k++) fls.push('half');
      var gaps = flowerSlots.filter(function (t) { return t >= .3 && t <= .9; }); if (!gaps.length) gaps = [.45, .6, .75, .35, .85];
      fls = fls.filter(function (x) { return x === 'open'; });
      var fn = Math.min(CFG.flower.max, fls.length), order = [], ks = KIT && KIT.flowerSlots ? KIT.flowerSlots(BR) : null;
      for (k = 0; k < fn; k++) { var fq = rng(b.course_id * 1009 + k * 31 + 3), kt = ks && ks[k] && ks[k].t;  // outer 2/3, seeded per assignment
        order.push([kt != null ? kt : .34 + .58 * (fn > 1 ? k / (fn - 1) : .5) + (fq() - .5) * .08, .75 + .5 * fq(), fq() * 360]); }
      var upN = (data.roots || []).concat(data.later || []).filter(function (d) { return d.course_id == b.course_id; }).length;
      if (KB && KIT.flowers) { var FP = dark() ? KIT.flowers.dark : KIT.flowers.light; KIT.flowerSlots(c, Math.min(CFG.flower.max, fl), hsd || 1).forEach(function (sl) { o.push(KIT.flowers.flowerSVG(sl, FP)); });
        KIT.budSlots(c, Math.min(2, upN), hsd || 1).forEach(function (sl) { o.push(KIT.flowers.budSVG(sl, FP)); }); fn = 0; upN = 0; fls = []; }
      for (k = 0; k < Math.min(3, upN); k++) { var bq = rng(b.course_id * 389 + k * 7), tb = Math.min(.99, .86 + .12 * (k + bq()) / 3); p = at(c, tb);
        o.push('<g class="r-fbud" transform="translate(' + f(p[0]) + ',' + f(p[1] - 2) + ') rotate(' + f(angAt(c, tb) * 180 / Math.PI + (bq() - .5) * 40) + ') scale(' + f(.45 + .15 * bq()) + ')"><use href="#rbud"/></g>'); }  // buds = upcoming deadlines, last 15%
      for (k = 0; k < fn; k++) {
        p = at(c, Math.max(.34, Math.min(.95, order[k][0]))); var stt = 'open';
        var col = SP.flower_color ? ((ci + k) % 2 ? mix(SP.flower_color, '#FFFFFF', .18) : SP.flower_color) : (ci + k) % 2 ? 'var(--r-butter)' : 'var(--r-coral)', cc = SP.flower_center || (SP.flower_color ? 'var(--r-butter)' : (ci + k) % 2 ? '#8A6242' : 'var(--r-butter)');
        var fpop = !G && stt === 'open' && opt.popN && opt.popN[b.course_id] && opt.popN[b.course_id].f != null && k >= opt.popN[b.course_id].f;
        o.push('<g transform="translate(' + f(p[0]) + ',' + f(p[1]) + ') rotate(' + f(order[k][2]) + ') scale(' + f(CFG.flower.scale * order[k][1]) + ')" style="--fc:' + col + ';--fcc:' + cc + '"><use href="#' + (stt === 'open' && SP.fsym ? SP.fsym : 'rf-' + stt) + '"' + (G ? ' class="r-pop" style="--d:' + f(2 + k * .05) + 's"' : fpop ? ' class="r-pop" style="--d:.4s"' : '') + '/></g>');
      }
      if (fls.length > fn) { p = at(c, .97); o.push('<g class="r-badge" transform="translate(' + f(p[0] + 9) + ',' + f(p[1] - 16) + ')"><circle r="8"/><text y="3">+' + (fls.length - fn) + '</text></g>'); }
      var lbl = b.code || b.name;
      var ctext = clip(lbl, narrow ? 10 : 18), cx0 = clampX(e[0] + side * (h >= CFG.leaf.clusterHours ? 30 : 14), side, ctext.length * (FS + 1) * .55, W);
      var chx = cx0 - side * FS * .6;
      o.push('<circle class="r-chip" cx="' + f(chx) + '" cy="' + f(e[1] + 4 - FS * .35) + '" r="' + f(FS * .38) + '" style="fill:' + esc(AC[b.course_id] || 'transparent') + '"/>');
      var tp = at(c, .35), tk = Math.max(1, FS / 12.5) * (narrow ? .75 : 1) /*v34 phone tags 25% smaller*/, tcand = [.97, .9, .84, .78, .7, .6, .5].map(function (t) { var q = at(c, t); return f(q[0]) + ',' + f(q[1]); }).join(' '), tc = AC[b.course_id] || '#6B4A2F'; o.push(tag(tp[0], tp[1], clip(b.code || b.name, 12), tc /*v12c*/, tk, ci % 4 > 1 ? 50 : 34, side, tcand));
      o.push('<text class="r-lbl r-course" style="font-size:' + f(FS + 1) + 'px" x="' + f(cx0) + '" y="' + f(e[1] + 4) + '" text-anchor="' + (side > 0 ? 'start' : 'end') + '">' + esc(ctext) + '</text>');
      if (G) o.push('</g>');
      o.push('</g></g>');
      items['branch:' + b.course_id] = { tip: '<b>' + esc(lbl) + '</b> · ' + hrs(b.minutes) + ' this term · ' + fl + ' done', url: b.url, x: e[0], y: e[1] - 10, W: W, H: H };
    });
    if (trunk) { crownTop = Math.min(crownTop, top - 20); o[canIdx] = CFG.canopy ? canopy(SP, br.length, tx, narrow ? Math.max(hiTip + 30, loTip - 12) : Math.min(hiJ, hiTip) + 30, Math.max(12, Math.min(top - 40, hiTip - (narrow ? 230 : 260))), W) : '';  // v33: crown sits low so the top branches tuck under its lower edge  // canopy v1 on hold (v2 art pending): set roots.config.canopy = true to preview
      // v26 stubs: 1 (phone) / 2 (desktop) cut-branch stubs with a sprout at the next empty branch slots (Design styles .stub)
      var nS = 0 /*v33: branches = classes only*/, sid = String(SP.id || 'default').replace(/^species_/, '').replace(/[^a-z0-9_]/gi, '');
      for (var si = 0; si < nS; si++) { var ni = br.length + si, nn = br.length + nS, sjt = nn === 1 ? .5 : .2 + .62 * ni / (nn - 1), sa = at(trunk, Math.min(.86, sjt)), sside = ni % 2 ? 1 : -1;
        var th = sside * (90 - 32), stX = sa[0], stY = sa[1]; if (!si) budAt = [stX, stY];
        var slots = []; for (var sj = Math.min(.86, sjt); sj <= .985; sj += .05) { var sq = at(trunk, sj); slots.push(f(sq[0]) + ',' + f(sq[1])); }  // this slot, then one step up at a time
        var lows = []; for (var lj = .04; lj < Math.min(.3, sjt); lj += .04) { var lq = at(trunk, lj); lows.push(f(lq[0]) + ',' + f(lq[1])); }  // v28: low slots just above the soil
        o.push('<g class="r-item stub" tabindex="0" role="button" aria-label="Add a class" data-type="add" data-id="' + si + '" data-th="' + f(th) + '" data-slots="' + slots.join(' ') + '" data-lows="' + lows.join(' ') + '" transform="translate(' + f(stX) + ',' + f(stY) + ') rotate(' + f(th) + ')">' +
          '<rect class="r-stubhit" x="-22" y="-32" width="44" height="44" rx="10" fill="transparent"/><g transform="translate(0,-10)">' +
          '<image class="r-stub-l" href="/static/species/' + sid + '_stub.svg?v=2" x="-12" y="-12" width="24" height="24"/><image class="r-stub-d" href="/static/species/' + sid + '_stub_dark.svg?v=2" x="-12" y="-12" width="24" height="24"/></g></g>');
        items['add:' + si] = { tip: 'Add a class', url: el.dataset.addUrl || CFG.addUrl, x: stX, y: stY - 36, W: W, H: H }; } }
    o.push('</g>');
    // soil + horizon + pebbles
    var sp = []; for (var x = 0; x <= W; x += 30) sp.push([x, Y + 3 * Math.sin(x / 53 + 1) + 2 * Math.sin(x / 23)]);
    var topLine = smooth(sp, false), pr = rng(3), peb = '', k;
    for (k = 0; k < 9; k++) { var px = 20 + pr() * (W - 40), py = Y + 8 + pr() * 32, s = 2.5 + pr() * 3.5, bl = [];
      for (var q = 0; q < 8; q++) { var tt = q * Math.PI / 4; bl.push([px + Math.cos(tt) * s * (1 + .18 * Math.sin(3 * tt + k)), py + Math.sin(tt) * s * .7 * (1 + .15 * Math.cos(2 * tt))]); }
      peb += smooth(bl, true) + ' '; }
    if (GD.pot) { var pc = GD.pot.color || '#C9805A', ps = GD.pot.shade || mix(pc, '#000000', .2);  // pot frame: rim at the soil line, walls down the sides
      var POT = ('<g class="r-pot"><path d="M0,' + (Y - 6) + ' H' + W + ' V' + (Y + 12) + ' H0Z" fill="' + esc(pc) + '"/><path d="M0,' + (Y + 12) + ' H' + W + '" stroke="' + esc(ps) + '" stroke-width="3"/>' +
        '<path d="M0,' + (Y + 12) + ' L14,' + (Y + 12) + ' L26,' + H + ' L0,' + H + 'Z M' + W + ',' + (Y + 12) + ' L' + (W - 14) + ',' + (Y + 12) + ' L' + (W - 26) + ',' + H + ' L' + W + ',' + H + 'Z" fill="' + esc(ps) + '"/></g>'); }
    o.push('<path class="r-soil" d="' + topLine + ' L' + W + ',' + H + ' L0,' + H + ' Z"/><path class="r-horizon" d="' + topLine + '"/><path class="r-pebble" d="' + peb + '"/>');
    
    // roots
    var HZ = CFG.root.horizon, dTop = CFG.root.top, dSpan = H - Y - dTop - CFG.root.bottomPad; /*v6*/
    if (GD.pot) dSpan = H - 48 - 40 - Y - dTop;  // deepest (21 d) root ends 40px above the inner bottom  // deepest root ~19 days, clears the bottom wall
    rt = rt.filter(function (d) { return (d.days_left || 0) <= HZ; });
    var later = (data.later || []).concat((data.roots || []).filter(function (d) { return (d.days_left || 0) > HZ; }));
    [[0, 'today'], [7, '1 wk'], [14, '2 wk'], [21, '3 wk']].forEach(function (tk) { var ty = Y + dTop + dSpan * tk[0] / HZ;
      o.push('<g class="r-tick"><path d="M8,' + f(ty) + ' h10"/><text x="22" y="' + f(ty + 4) + '">' + tk[1] + '</text></g>'); });
    var spreadMax = narrow ? W / 2 - 70 : 330;
    o.push('<g class="r-under">');
    rt.forEach(function (d, k) {
      var sd = k % 2 ? 1 : -1, depth = dTop + dSpan * Math.max(0, Math.min(HZ, d.days_left || 0)) / HZ;
      var dx = Math.min(spreadMax, CFG.root.spread0 + Math.floor(k / 2) * CFG.root.spreadStep) * (k === rt.length - 1 && k % 2 === 0 && rt.length > 4 ? .35 : 1);
      var w0 = d.weight == null ? CFG.root.wDefault : CFG.root.wMin + (CFG.root.wMax - CFG.root.wMin) * Math.min(1, Math.max(0, d.weight) / CFG.root.fullWeight);
      var rk = narrow ? W / (el.clientWidth || W) : 1; w0 *= rk;  // phone: widths in screen px
      var ex = tx + sd * dx, p0 = [tx + sd * 4, Y + 4], c = curve(p0, [tx + sd * dx * .15, Y + depth * .45], [ex - sd * dx * .1, Y + depth * .55], [ex, Y + depth], 70, CFG.root.wob, k + 11, CFG.root.freq);
      var rr = rng(k + 11), body = '', hair = '', rcol = AC[d.course_id] || '';
      if (d.dashed) { var n = c.length, i = 0;
        while (i < n - 3) { var j = Math.min(i + CFG.root.dashOn, n - 1), t0 = i / (n - 1), t1 = j / (n - 1);
          body += capsule(c.slice(i, j + 1), w0 + (CFG.root.w1 * rk - w0) * Math.pow(t0, .8), w0 + (CFG.root.w1 * rk - w0) * Math.pow(t1, .8)) + ' '; i = j + CFG.root.dashOff; }
      } else body = taper(c, w0, CFG.root.w1 * rk);
      for (var h2 = 0; h2 < Math.floor(4 + w0 / 2); h2++) {
        var ii = 8 + Math.floor(rr() * (c.length - 14)), hx = c[ii][0], hy = c[ii][1], ang = Math.atan2(c[ii + 1][1] - c[ii - 1][1], c[ii + 1][0] - c[ii - 1][0]);
        var a2 = ang + (h2 % 2 ? 1 : -1) * (.6 + rr() * .5), ln = (6 + rr() * 8) * (1 + w0 / 12), qq = [];
        for (var st = 0; st <= 6; st++) { var tq = st / 6; qq.push([hx + Math.cos(a2) * ln * tq + Math.cos(ang) * ln * .3 * tq * tq, hy + Math.sin(a2) * ln * tq + Math.sin(ang) * ln * .3 * tq * tq]); }
        hair += smooth(qq, false) + ' ';
      }
      var dlx = (d.days_left | 0) < 0 ? 'overdue' : (d.days_left | 0) === 0 ? 'today' : (d.days_left | 0) + 'd';
      var nl = narrow ? wrap2(d.name, 14) : null; if (nl) nl[nl.length - 1] += ' · ' + dlx;
      var lab = narrow ? nl.reduce(function (m, s2) { return s2.length > m.length ? s2 : m; }, '') : clip(d.name, 26) + ' · ' + short(d.due) + (d.days_left <= 7 ? ' (' + days(d.days_left) + ')' : '');
      var lw = lab.length * FS * (narrow ? .5 : .58) + 6, wl = GD.pot ? 58 : PAD, wr = GD.pot ? W - 58 : W - PAD;  // inside the pot walls (wallOut inner wall max 26+26+6)
      var lx = narrow ? (sd > 0 ? Math.min(ex + 8, wr - lw) : Math.max(ex - 8, wl + lw)) : clampX(ex + sd * (sd > 0 ? 25 : 14), sd, lw, W);
      o.push('<g class="r-item r-draw" tabindex="0" role="button" data-type="root" data-id="' + d.deadline_id + '" aria-label="' + esc(d.name + ', due ' + days(d.days_left)) + '" style="--d:' + f(Math.min(.25, .04 * k)) + 's' + (rcol ? ';--rc:' + esc(rcol) : '') + '">' +
        '<path class="r-hitp" d="' + line(c) + '"/><path class="r-root' + (d.dashed ? ' dashed' : '') + '" d="' + body + '"/><path class="r-hair' + (d.dashed ? ' dashed' : '') + '" d="' + hair + '"/>' +
        rtext(lx, lblY(Y + depth - (narrow ? 4 : 0), Y + depth, FS / 12, GD.pot ? H - 48 : H), narrow ? (sd > 0 ? 'start' : 'end') : sd > 0 ? 'start' : 'end', narrow ? nl : clip(d.name, 26) + ' · ' + short(d.due), narrow ? '' : days(d.days_left), FS / 12, narrow ? short(d.due) : '') /*v14*/ + '</g>');
      items['root:' + d.deadline_id] = { tip: d.dashed ? '<b>' + esc(d.name) + '</b><br>No study logged yet — start a session?' :
        '<b>' + esc(d.name) + '</b> · due ' + short(d.due) + '<br>' + (d.weight == null ? '' : Math.round(d.weight) + '% of grade · ') + hrs(d.studied_minutes) + ' studied',
        url: d.url, x: ex, y: Y + depth - 8, W: W, H: H };
    });
    if (later.length) o.push(pill(W - 14, H - 12 - FS / 2, 'end', '+' + later.length + ' later', FS, ' r-later'));
    if (!rt.length && br.length) o.push(pill(tx, Y + 140, 'middle', 'No deadlines coming up. Enjoy the sunshine.', FS, ''));

    [].forEach(function (dk, i) { var dx = [.16, .84, .3, .7][i] * W, dc = GD.dcol[dk] || {};
      o.push('<g class="r-decor" data-key="' + esc(dk) + '" transform="translate(' + f(dx) + ',' + (Y + 2) + ')">' + (/lantern/.test(dk) ? '<path d="M0,0 V-22" stroke="#3B2A1E" stroke-width="2"/><rect x="-6" y="-34" width="12" height="14" rx="3" fill="' + (dc.glow || '#F4C95D') + '"/>' :
        /fence/.test(dk) ? '<path d="M-24,0 V-16 M-8,0 V-18 M8,0 V-18 M24,0 V-16 M-28,-10 H28" stroke="#8A6242" stroke-width="3" stroke-linecap="round"/>' :
        '<ellipse cx="-8" cy="-3" rx="10" ry="6" fill="#9A9184"/><ellipse cx="7" cy="-2" rx="7" ry="4.5" fill="#B5AC9E"/>') + '</g>'); });
    o.push('</g></svg><div class="r-tip" role="tooltip"></div>');
    if (!br.length && !opt.mini) o.push('<div class="r-empty"><p>Your semester starts with one seed.</p><a class="btn" href="' + esc(el.dataset.addUrl || CFG.addUrl) + '">Plant your first class</a></div>');
    el.classList.toggle('r-narrow', !!narrow);
    if (narrow) { var nb = 0; [].forEach.call(document.querySelectorAll('nav,footer,[class*=nav],[class*=tab]'), function (n) { var cs = getComputedStyle(n), r = n.getBoundingClientRect();
      if (cs.position === 'fixed' && r.height > 0 && r.bottom >= innerHeight - 40 && r.width > innerWidth * .5) nb = Math.max(nb, innerHeight - r.top); });
      el.style.scrollMarginBottom = nb ? Math.ceil(nb + 8) + 'px' : ''; } else el.style.scrollMarginBottom = ''; /*v16*/  // keep the pot clear of the phone tab bar
    var rm = reduce && reduce.matches; el.classList.toggle('intro', G && !rm); el.classList.toggle('r-fadein', opt.intro === 'fade' && !rm);
    if (el._pv) { el.dataset.previewKind = el._pv.kind; el.dataset.previewKey = el._pv.key; } else { delete el.dataset.previewKind; delete el.dataset.previewKey; }
    el.innerHTML = o.join('');
    try { el._gdKey = JSON.stringify(GD) + (SP.sym || '') + (SP.fsym || ''); } catch (e) {}
    el._roots = { data: data, items: items, narrow: narrow, W: W, H: H, Y: Y, pot: !!GD.pot }; /*v19*/ /*v19b*/
    try { decorate(el, GD, data, W, H, Y); } catch (e) { console.error('[roots] decorate error', e); }
    try { sweep(el); } catch (e) {}
    (function () { var sv = el.querySelector('svg'); if (!sv) return; var L = sv.querySelector('.r-labels') || sv.appendChild(svgEl('g', { class: 'r-labels' }));  // v19: labels render after the pot ring
      if (!(el._roots.data.branches || []).length && !sv.querySelector('.r-seedbed')) { var st = el._roots, sb = svgEl('g', { class: 'r-seedbed', transform: 'translate(' + (st.W / 2) + ',' + (st.Y - 11) + ') scale(1.7)' }); /*v21*/  // empty state: a seed sprouting from the pot's soil line
        sb.innerHTML = '<ellipse cx="0" cy="1" rx="10" ry="3" fill="#3B2A1E" fill-opacity=".22"/><ellipse rx="7" ry="5" fill="#8A6242"/><ellipse cx="-2" cy="-1.6" rx="3" ry="1.6" fill="#FFF1D6" fill-opacity=".35"/><path d="M0,-3 C-.6,-8 -.4,-11 0,-14" stroke="#4E9A4F" stroke-width="1.6" fill="none" stroke-linecap="round"/><path d="M0,-13 C-3,-19 -9,-20 -12,-16 C-8,-14 -4,-13 0,-13 Z" fill="#4E9A4F"/><path d="M0,-13 C3,-19 9,-20 12,-16 C8,-14 4,-13 0,-13 Z" fill="#8CC56B"/>';
        sv.appendChild(sb); }
      el.querySelectorAll('.r-item[data-type=root]').forEach(function (it) { var t = it.querySelector('.r-rtext'); if (!t) return; var w = svgEl('g', { class: 'r-rlbl', 'data-id': it.dataset.id }); w.appendChild(t); L.appendChild(w); });
      L.onclick = function (e) { var w = e.target.closest('.r-rlbl'), it = w && el.querySelector('.r-item[data-type=root][data-id="' + w.dataset.id + '"]'); if (it) { e.stopPropagation(); it.dispatchEvent(new MouseEvent('click', { bubbles: true })); } }; /*v19d*/ })();
    if (opt.mini) { miniFinish(el, data); return; }
    var doTags = function () { if (el._roots !== myState) return; try { placeTags(el); } catch (e) { console.error('[roots] tag placement', e); } try { placeStubs(el); } catch (e) {} },
      doLabels = function () { if (el._roots !== myState) return; try { placeLabels(el, GD.pot ? H - 48 - 36 : H - 8); } catch (e) { console.error('[roots] label placement', e); } }, myState = el._roots;
    if (opt.intro && window.requestAnimationFrame) { requestAnimationFrame(function () { doTags(); requestAnimationFrame(doLabels); }); }  // perf: split the first build into 3 frames (tags/labels fade in later anyway)
    else { doTags(); doLabels(); }
    var sv = el.querySelector('svg'); el.style.cssText = el.style.cssText.replace(/--r-(soil|horizon|root|sky|coral|butter|bud):[^;]*;?/g, '');
    if (GD.soil) { el.style.setProperty('--r-soil', GD.soil.fill || ''); el.style.setProperty('--r-horizon', GD.soil.horizon || GD.soil.mark || ''); GD.soil.root && el.style.setProperty('--r-root', GD.soil.root); }
    var grad = function (k) { return 'linear-gradient(' + k.stops.map(function (s) { return s.color + ' ' + Math.round(s.offset * 100) + '%'; }).join(',') + ')'; };
    ['--r-skybg-d', '--r-skybg-n', '--r-sky-d', '--r-sky-n'].forEach(function (v) { el.style.removeProperty(v); });
    var SCN = !!el._scene;  // v36: scene sky/props only when a host opts in (banner); Home/Store/Profile = plain default sky
    if (SCN && GD.sky && GD.sky.stops) { el.style.setProperty('--r-sky-d', GD.sky.stops[0].color); el.style.setProperty('--r-skybg-d', grad(GD.sky)); }
    if (SCN && GD.skyN && GD.skyN.stops) { el.style.setProperty('--r-sky-n', GD.skyN.stops[0].color); el.style.setProperty('--r-skybg-n', grad(GD.skyN)); }  // theme switch = CSS only, no rebuild
    if (GD.flowers) { GD.flowers.petal && el.style.setProperty('--r-coral', GD.flowers.petal); GD.flowers.center && el.style.setProperty('--r-butter', GD.flowers.center); }
    if (GD.leaves && GD.leaves.bud) el.style.setProperty('--r-bud', GD.leaves.bud);
    var ph = el.parentElement && el.parentElement.clientHeight, need = el.clientWidth * H / W;  // short container (Store preview): fit the whole map
    el.classList.toggle('r-fit', !!(ph && ph < need - 4 && /px/.test(getComputedStyle(el.parentElement).height) && el.parentElement.style.height !== 'auto' && ph < 600));
    clearTimeout(el._introT); if (opt.intro) el._introT = setTimeout(function () { el.classList.remove('intro', 'r-fadein'); if (el._reRender) { el._reRender = false; render(el, el._roots.data, {}); } }, G ? 2700 : 500);
  }

  // ---- interaction (delegated, bound once) ----
  function bind(el) {
    if (el._rootsBound) return; el._rootsBound = true;
    var tipEl = function () { return el.querySelector('.r-tip'); };
    function show(g) {
      var st = el._roots, it = st && st.items[g.dataset.type + ':' + g.dataset.id]; if (!it) return;
      el.querySelectorAll('.r-item.on').forEach(function (n) { n.classList.remove('on'); });
      g.classList.add('on'); el.classList.add('is-hover');
      var t = tipEl(), r = el.clientWidth / it.W; t.innerHTML = it.tip;
      var tw2 = t.offsetWidth / 2 + 6; t.style.left = Math.max(tw2, Math.min(el.clientWidth - tw2, it.x * r)) + 'px'; t.style.top = (it.y * r) + 'px'; t.classList.add('show');  // v33: clamp inside the frame
    }
    function hide() { el.classList.remove('is-hover'); el.querySelectorAll('.r-item.on').forEach(function (n) { n.classList.remove('on'); }); var t = tipEl(); t && t.classList.remove('show'); }
    function pick(g) {
      var type = g.dataset.type, id = +g.dataset.id, it = el._roots.items[type + ':' + id];
      var ev = new CustomEvent('roots:select', { bubbles: true, cancelable: true, detail: { type: type, id: id } });
      if (!el.dispatchEvent(ev)) return;
      var tpl = type === 'branch' ? el.dataset.branchUrl : el.dataset.rootUrl, url = (it && it.url) || (tpl && tpl.replace('{id}', id));
      if (url) location.href = url;
    }
    el.addEventListener('pointerover', function (e) { var g = e.target.closest('.r-item'); g ? show(g) : hide(); });
    el.addEventListener('pointerleave', hide);
    el.addEventListener('focusin', function (e) { var g = e.target.closest('.r-item'); g && show(g); });
    el.addEventListener('focusout', hide);
    el.addEventListener('click', function (e) { var g = e.target.closest('.r-item'); g && pick(g); });
    el.addEventListener('keydown', function (e) { var g = e.target.closest('.r-item'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick(g); } });
    if (window.ResizeObserver) { var rT = 0, lastW = -1; new ResizeObserver(function (en) {  // perf: no rebuild on resize unless the narrow/wide layout flips; 150ms debounce
      var w = en[0] && en[0].contentRect ? Math.round(en[0].contentRect.width) : el.clientWidth; if (w === lastW) return; lastW = w;
      clearTimeout(rT); rT = setTimeout(function () { var st = el._roots; if (st && (w < CFG.narrowBelow) !== st.narrow) render(el, st.data, {}); }, 150);
    }).observe(el); }
    motionWatch(el);
  }

  // grow-in plays on every mount (no one-time seen flag)
  var SHOP = { colors: {}, svg: {}, loaded: false };
  function shopLoad() { if (SHOP.loaded) return; SHOP.loaded = true;
    fetch('/static/shop/items.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { if (!d) return;
      var L = d.items || d; if (!Array.isArray(L)) L = Object.keys(L).map(function (k) { return Object.assign({ id: k }, L[k]); });
      L.forEach(function (it) { var k = it.id || it.key; if (!k) return; if (it.colors) SHOP.colors[k] = it.colors; if (it.svg) SHOP.svg[k] = '/static/' + it.svg.replace(/^\/?(static\/)?/, ''); if (it.store_key) { SHOP.colors[it.store_key] = it.colors; SHOP.svg[it.store_key] = SHOP.svg[k]; } });
      document.querySelectorAll('.roots').forEach(function (el) { if (!el._roots || el.classList.contains('r-mini')) return; var k; try { k = JSON.stringify(garden(el, el._roots.data)) + ((el._sp && el._sp.sym) || '') + ((el._sp && el._sp.fsym) || ''); } catch (e) {} if (k && k === el._gdKey) return;  // perf: skip the full rebuild when the Store catalogue changes nothing on this plant
        if (el.classList.contains('intro')) el._reRender = true; else render(el, el._roots.data, {}); });  // never cut the intro short
    }).catch(function () {});
  }
  // perf: sway only while the map is on screen and the tab is visible (.r-still pauses every CSS animation loop)
  var VIS = typeof IntersectionObserver === 'function' ? new IntersectionObserver(function (es) { es.forEach(function (e) { e.target._onscreen = e.isIntersecting; still(e.target); }); }, { rootMargin: '80px' }) : null;
  function still(el) { el.classList.toggle('r-still', document.hidden || el._onscreen === false); }
  function motionWatch(el) { if (VIS) VIS.observe(el); }
  document.addEventListener('visibilitychange', function () { document.querySelectorAll('.roots').forEach(still); });
  function svgEl(tag, at) { var e = document.createElementNS(NS, tag); for (var k in at) e.setAttribute(k, at[k]); return e; }
  function potRing(W, Y, B) {  // STYLE v3 9-slice: rim_h 30, rim_over 8, wall 18, taper 26, radius 40, rim_above 12
    var rb = Y + 18, o = 8, t = 26, r = 40;
    function shape(i) { var x0 = o + i, x1 = W - o - i, y0 = rb, y1 = B - i, tt = t, rr = Math.max(r - i * .6, 8);
      return 'M' + x0 + ',' + y0 + ' L' + (x0 + tt) + ',' + (y1 - rr) + ' Q' + (x0 + tt) + ',' + y1 + ' ' + (x0 + tt + rr) + ',' + y1 + ' L' + (x1 - tt - rr) + ',' + y1 + ' Q' + (x1 - tt) + ',' + y1 + ' ' + (x1 - tt) + ',' + (y1 - rr) + ' L' + x1 + ',' + y0 + ' Z'; }
    return { outer: shape(0), inner: shape(18), rb: rb };
  }
  function decorate(el, GD, data, W, H, Y) {
    var sv = el.querySelector('svg'); if (!sv) return; shopLoad();
    var sf = (GD.soil && GD.soil.fill) || getComputedStyle(el).getPropertyValue('--r-soil').trim();
    if (/^#[0-9a-f]{6}$/i.test(sf)) { var lum = [1, 3, 5].map(function (i) { var v = parseInt(sf.substr(i, 2), 16) / 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); });
      el.classList.toggle('r-lightsoil', .2126 * lum[0] + .7152 * lum[1] + .0722 * lum[2] > .18); }  // incl. peat
    var defs = svgEl('defs', {}); sv.insertBefore(defs, sv.firstChild); var uid = 'r' + Math.random().toString(36).slice(2, 7);
    var g = data.garden || {}, pv = el._pv, pick = function (k) { return pv && (pv.kind === k || (pv.key || '').indexOf(k.replace(/s$/, '') + '_') === 0) ? pv.key : (k === 'flowers' ? g.flowers || g.flower : g[k]); };
    var SCN = !!el._scene, skyK = SCN ? pick('sky') : null, soilK = pick('soil');
    var skyNK = SCN ? (GD.skyNK || skyK) : null; if (pv && skyK !== (g.sky)) skyNK = skyK;
    el.classList.toggle('r-hassky', !!((skyK && SHOP.svg[skyK]) || (skyNK && SHOP.svg[skyNK])));
    [[skyNK, 'r-night'], [skyK, 'r-day']].forEach(function (q) { if (q[0] && SHOP.svg[q[0]]) sv.insertBefore(svgEl('image', { href: SHOP.svg[q[0]], x: -W, y: -H, width: 3 * W, height: H + Y + 6, preserveAspectRatio: 'xMidYMax slice', class: 'r-skyimg ' + (skyNK === skyK ? '' : q[1]) }), defs.nextSibling); });
    ['--r-ink-d', '--r-halo-d'].forEach(function (v) { el.style.removeProperty(v); }); if (SCN && GD.sky) { GD.sky.label && el.style.setProperty('--r-ink-d', GD.sky.label); GD.sky.label_halo && el.style.setProperty('--r-halo-d', GD.sky.label_halo); }
    if (SCN && GD.skyN && GD.skyN !== GD.sky) { el.style.setProperty('--r-ink-n', GD.skyN.label || ''); el.style.setProperty('--r-halo-n', GD.skyN.label_halo || ''); } else { el.style.removeProperty('--r-ink-n'); el.style.removeProperty('--r-halo-n'); }
    var soil = sv.querySelector('.r-soil');
    if (soilK && SHOP.svg[soilK] && soil) { var pt = svgEl('pattern', { id: uid + 'soil', patternUnits: 'userSpaceOnUse', width: 300, height: 430, x: 0, y: Y - 20 });
      pt.appendChild(svgEl('image', { href: SHOP.svg[soilK], width: 300, height: 430 })); defs.appendChild(pt); soil.style.fill = 'url(#' + uid + 'soil)'; }
    sv.querySelectorAll('.r-trunk,.r-branch,.r-root').forEach(function (n) {
      var cl = n.cloneNode(false); cl.setAttribute('class', n.getAttribute('class') + ' r-shade'); cl.style.fill = n.classList.contains('r-root') ? 'url(#pd-litw)' : 'url(#pd-lit)'; n.parentNode.insertBefore(cl, n.nextSibling); });
    if (soil) { var ss = soil.cloneNode(false); ss.setAttribute('class', 'r-soilshade'); ss.style.fill = 'url(#pd-soil)'; soil.parentNode.insertBefore(ss, soil.nextSibling); }
    var under = sv.querySelector('.r-under');
    if (GD.pot) { var B = H - 30, ring = potRing(W, Y, B), body = GD.pot.color || GD.pot.body || '#C9805A', rim = GD.pot.shade || GD.pot.rim || body;
      var cp = svgEl('clipPath', { id: uid + 'in' }); cp.appendChild(svgEl('path', { d: ring.inner + ' M0,0 H' + W + ' V' + ring.rb + ' H0 Z' })); defs.appendChild(cp);
      [soil, under].concat([].slice.call(sv.querySelectorAll('.r-horizon,.r-pebble,.r-later'))).forEach(function (n) { n && n.setAttribute('clip-path', 'url(#' + uid + 'in)'); });
      sv.querySelectorAll('.r-tick').forEach(function (n) { n.setAttribute('transform', 'translate(56,0)'); });
      var pg = svgEl('g', { class: 'r-potring' });
      pg.appendChild(svgEl('path', { d: ring.outer + ' ' + ring.inner.replace(/^M([\d.]+),([\d.]+)/, 'M$1,$2'), fill: body, 'fill-rule': 'evenodd' }));
      pg.appendChild(svgEl('rect', { x: 0, y: Y - 12, width: W, height: 30, rx: 6, fill: rim }));
      pg.appendChild(svgEl('path', { d: 'M8,' + (Y - 8) + ' H' + (W - 8), stroke: '#FBF6EC', 'stroke-opacity': .55, 'stroke-width': 2, 'stroke-linecap': 'round' }));
      var pk = GD.pot.key || GD.pot.store_key, purl = pk && (SHOP.svg[pk] || '/static/shop/pot/' + pk.replace(/^pot_/, '') + '.svg');
      if (W === 900 && purl) { /*v30: solid pot body + soil behind the pot art so it never reads hollow*/ var fill = svgEl('g', { class: 'r-potfill', 'pointer-events': 'none' });
        fill.appendChild(svgEl('path', { d: ring.outer, fill: body })); var sfp = svgEl('path', { d: ring.inner }); sfp.style.fill = 'var(--r-soil,#5a3d2b)'; fill.appendChild(sfp);
        var s0 = soil || under; if (s0 && s0.parentNode) s0.parentNode.insertBefore(fill, s0); else sv.insertBefore(fill, sv.firstChild);
        pg = svgEl('image', { class: 'r-potring', href: purl, x: 0, y: Y - 420, width: 900, height: 900 }); }  // 3d design 1's art incl. pattern seams; geometry is fixed at 900 wide
      if (under) sv.insertBefore(pg, under.nextSibling); else sv.appendChild(pg);
      var tier = String(data.tier || GD.pot.rarity || '').toLowerCase(); el.classList.remove('tier-rare', 'tier-epic', 'tier-legendary');
      if (/^(rare|epic|legendary)$/.test(tier)) { el.classList.add('tier-' + tier);  // STYLE.md "Pot tier effects": no filters
        if (tier === 'legendary') { var gl = svgEl('g', { class: 'tier-glow' }); [[60, .12], [36, .18], [16, .28]].forEach(function (q) { gl.appendChild(svgEl('path', { d: ring.outer, fill: 'none', stroke: '#F2D48A', 'stroke-width': q[0], 'stroke-opacity': q[1], 'stroke-linejoin': 'round' })); }); sv.insertBefore(gl, pg); }
        else { var tc = svgEl('clipPath', { id: uid + 'wall' }); tc.appendChild(svgEl('path', { d: ring.outer })); defs.appendChild(tc);
          var tw = svgEl('g', { 'clip-path': 'url(#' + uid + 'wall)', class: 'tier-wrap' }), sh = svgEl('g', { class: 'tier-shimmer' });
          var lg = svgEl('linearGradient', { id: uid + 'shim', x1: 0, x2: 1, y1: 0, y2: 0 }); [[0, 0], [.5, .35], [1, 0]].forEach(function (q) { lg.appendChild(svgEl('stop', { offset: q[0], 'stop-color': '#fff', 'stop-opacity': q[1] })); }); defs.appendChild(lg);
          sh.appendChild(svgEl('rect', { x: 0, y: Y - 400, width: 180, height: H + 400, fill: 'url(#' + uid + 'shim)', transform: 'rotate(20 90 ' + (Y + 200) + ')' })); tw.appendChild(sh); sv.insertBefore(tw, pg.nextSibling); } }
      var sd0 = sv.querySelector('.r-seed'); if (sd0) { sd0.setAttribute('transform', sd0.getAttribute('transform').replace(/,([\d.]+)\)$/, function (m, y) { return ',' + (+y - 27) + ')'; })); sv.appendChild(sd0); }
      var ss2 = sv.querySelector('.r-soilshade'); ss2 && ss2.setAttribute('clip-path', 'url(#' + uid + 'in)');
      el.querySelectorAll('.r-addbud').forEach(function () {}); }
    (SCN ? GD.decor || [] : []).slice(0, 4).forEach(function (dk, i) { var c = GD.dcol[dk] || {}, vb = c.viewBox, url = SHOP.svg[dk]; if (!vb || !url) return;
      var sc = 1.4 * (W < 700 ? .8 : 1), xs = W < 700 ? [.12, .88, .22, .78] : [.14, .86, .27, .73], x = xs[i] * W, y = /fireflies/.test(dk) ? Y - 150 : Y + 4;
      sv.insertBefore(svgEl('image', { class: 'r-decor', href: url, x: x + vb[0] * sc, y: y + vb[1] * sc, width: vb[2] * sc, height: vb[3] * sc }), sv.querySelector('.r-above')); });
  }
  function garden(el, data) {  // equipped garden + live Store preview -> {soil, sky, flowers, leaves, decor[], pot, dcol}
    var g = data.garden || {}, C = Object.assign({}, SHOP.colors, g.colors || {}), pv = el._pv, I = window.ITEMS || [];
    function col(k) { if (!k) return null; if (C[k]) return C[k]; var it = Array.isArray(I) ? I.filter(function (x) { return x.key === k || x.id === k; })[0] : null; return it && it.colors || null; }
    var sel = { soil: g.soil, sky: g.sky, flowers: g.flowers || g.flower, leaves: g.leaves, decor: (g.decor || []).slice(), pot: data.pot || null };
    if (pv) { var kind = pv.kind; if (!/^(soil|sky|flowers|leaves|decor|pot)$/.test(kind)) kind = (pv.key.split('_')[0] || '').replace(/^flower$/, 'flowers');
      if (kind === 'decor') sel.decor = [pv.key].concat(sel.decor.filter(function (k) { return k !== pv.key; })).slice(0, 4);
      else if (kind === 'pot') sel.pot = col(pv.key) ? Object.assign({ key: pv.key }, col(pv.key)) : { key: pv.key };
      else if (sel.hasOwnProperty(kind)) sel[kind] = pv.key; }
    var out = { decor: sel.decor, dcol: {}, pot: sel.pot && (sel.pot.color || sel.pot.key) ? sel.pot : null };
    ['soil', 'sky', 'flowers', 'leaves'].forEach(function (k) { out[k] = col(sel[k]); });
    out.skyK = sel.sky; out.skyNK = sel.sky !== g.sky ? sel.sky : (g.sky_night || sel.sky); out.skyN = col(out.skyNK) || out.sky;  // v25: day + night sky; previewed sky shows in both themes
    sel.decor.forEach(function (k) { out.dcol[k] = col(k) || {}; });
    return out;
  }
  // ---- species hook: data.species = {id, leaf_color, flower_color, bark_color, leaf_shape, blooms, bloom_color}; absent = current tree ----
  // species: flat data.species (primary) or a species item's .colors; leaf/flower art = shop SVG files turned into one <symbol> each (fetched once)
  var SPSYM = {};
  function spSymbol(url, kind, el) {
    var id = 'rsp-' + kind + '-' + url.replace(/[^a-z0-9]/gi, '_'); if (SPSYM[id] === true) return id; if (SPSYM[id]) return null;
    SPSYM[id] = 'loading'; fetch('/static/' + url.replace(/^\/?(static\/)?/, '')).then(function (r) { return r.ok ? r.text() : null; }).then(function (t) { if (!t) return;
      var d = new DOMParser().parseFromString(t, 'image/svg+xml').documentElement; if (!d || d.nodeName !== 'svg') return; ensureDefs();
      var sy = document.createElementNS(NS, 'symbol'); sy.id = id; sy.setAttribute('overflow', 'visible');
      var g = document.createElementNS(NS, 'g'); g.setAttribute('transform', kind === 'leaf' ? 'translate(-8,-20)' : 'translate(-20,-21)');  // STYLE.md anchors: leaf base (8,20), flower centre (20,21)
      [].slice.call(d.childNodes).forEach(function (n) { if (n.nodeType === 1 && !/script|foreignObject/i.test(n.nodeName)) g.appendChild(document.importNode(n, true)); });
      sy.appendChild(g); document.querySelector('#roots-defs defs').appendChild(sy); SPSYM[id] = true;
      document.querySelectorAll('.roots').forEach(function (e) { if (e._roots && e._sp && (e._sp.sym === null || e._sp.fsym === null)) { if (e.classList.contains('intro')) e._reRender = true; else if (e.classList.contains('r-mini')) api.mini(e, e._roots.data); else render(e, e._roots.data, {}); } });
    }).catch(function () {}); return null;
  }
  function species(el, data) {
    var raw = data.species || {}, sp = Object.assign({}, raw.colors || {}, raw), hx = function (v) { return /^#[0-9a-f]{6}$/i.test(v || '') ? v : null; };
    var lf = sp.leaf || {}, fl = sp.flower || {}, bk = sp.bark || {};
    var o = { id: sp.id || 'default', leaf_color: hx(lf.base) || hx(sp.leaf_color), leaf_tip: hx(lf.tip), flower_color: hx(fl.petal) || hx(sp.flower_color), flower_center: hx(fl.center),
      leafDensity: +sp.leafDensity > 0 ? +sp.leafDensity : 1, flowerDensity: fl.density != null && +fl.density >= 0 ? +fl.density : 1, leafScale: +lf.scale > 0 ? +lf.scale : 1, flowerScale: +fl.scale > 0 ? +fl.scale : 1,
      mini: sp.mini || {}, sym: undefined, fsym: undefined };
    var isDef = o.id === 'default' || o.id === 'species_default';
    if (isDef) { o.leaf_color = o.leaf_tip = o.flower_color = o.flower_center = null; }  // default species = the hand-tuned current tree
    var bark = !isDef && (hx(bk.base) || hx(sp.bark_color)); if (bark) el.style.setProperty('--r-bark', bark); else el.style.removeProperty('--r-bark');
    el.setAttribute('data-species', o.id);
    var ls = !isDef && (lf.path || sp.leaf_shape), fs = !isDef && (fl.path || sp.flower_shape);
    if (ls && /\.svg$/i.test(ls)) o.sym = spSymbol(ls, 'leaf', el);
    if (fs && /\.svg$/i.test(fs)) o.fsym = spSymbol(fs, 'flower', el);
    el._sp = o; return o;
  }
  function newLeaves(data) {  // v20: leaves gained per course since this browser last saw the plant (first visit: none)
    var now = {}, old = null, out = {}; (data.branches || []).forEach(function (b) { now[b.course_id] = Math.round(b.minutes || 0); }); /*v20b*/
    try { old = JSON.parse(localStorage.getItem('prody_roots_minutes') || 'null'); localStorage.setItem('prody_roots_minutes', JSON.stringify(now)); } catch (e) {}
    if (old && typeof old === 'object') Object.keys(now).forEach(function (k) { if (old[k] != null && now[k] > old[k]) out[k] = { m: old[k] }; });
    var nf = {}, of = null; (data.branches || []).forEach(function (b) { nf[b.course_id] = (b.flowers | 0) + (b.focus_flowers | 0); });
    try { of = JSON.parse(localStorage.getItem('prody_roots_flowers') || 'null'); localStorage.setItem('prody_roots_flowers', JSON.stringify(nf)); } catch (e) {}
    if (of && typeof of === 'object') Object.keys(nf).forEach(function (k) { if (of[k] != null && nf[k] > of[k]) { out[k] = out[k] || {}; out[k].f = of[k]; } });
    return out;
  }
  function newIds(data) {  // course_ids not seen on the last visit -> grow from the bud
    var ids = (data.branches || []).map(function (b) { return b.course_id; }), out = {}, old = null;
    try { old = JSON.parse(localStorage.getItem('prody_roots_known') || 'null'); localStorage.setItem('prody_roots_known', JSON.stringify(ids)); } catch (e) {}
    if (Array.isArray(old)) ids.forEach(function (i) { if (old.indexOf(i) < 0) out[i] = 1; });
    return out;
  }
  window.addEventListener('prody:preview-item', function (e) {  // Store live preview: temporarily override one slot
    var d = e.detail || {}; document.querySelectorAll('.roots').forEach(function (el) {
      el._pv = d.key == null ? null : { kind: String(d.kind || ''), key: String(d.key) };
      if (el._roots) render(el, el._roots.data, {});
    });
  });
  // v26 canopy: soft crown behind trunk + branches (STYLE.md "Canopy"); lobes from species/<id>_canopy.json, placeholder oval until loaded
  var CAN = {}, CANDEF = { aspect: 1.35, opacity: .46, opacity_dark: .4, colors: { gradient: { stops: [[0, '#83B884'], [.45, '#60A461'], [.75, '#4E9A4F'], [1, '#3D783E']] }, offset_shadow: '#234524' },
    offset_shadow: { dx: .025, dy: .035, opacity: .18, opacity_dark: .38 }, lobes: [{ cx: .5, cy: .2, r: .24 }, { cx: .32, cy: .38, r: .22 }, { cx: .68, cy: .38, r: .22 }, { cx: .3, cy: .6, r: .22 }, { cx: .7, cy: .6, r: .22 }, { cx: .5, cy: .5, r: .27 }, { cx: .5, cy: .76, r: .2 }] };
  function canopyData(id) { if (CAN[id]) return CAN[id] === 'loading' ? null : CAN[id]; CAN[id] = 'loading';
    fetch('/static/species/' + id + '_canopy.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { CAN[id] = d || CANDEF;
      if (d) document.querySelectorAll('.roots').forEach(function (e) { if (!e._roots || !e._sp || String(e._sp.id).replace(/^species_/, '') !== id) return; if (e.classList.contains('intro')) e._reRender = true; else if (e.classList.contains('r-mini')) api.mini(e, e._roots.data); else render(e, e._roots.data, {}); }); }).catch(function () { CAN[id] = CANDEF; });
    return null; }
  function canopy(SP, n, ax, ay, topY, GW) {  // v2: one self-contained <image> per theme (STYLE.md "Canopy"); aspect from <id>_canopy.json viewBox
    var id = String(SP.id || 'default').replace(/^species_/, '').replace(/[^a-z0-9_]/gi, ''), d = canopyData(id) || {}, vb = d.viewBox || d.viewbox;
    if (typeof vb === 'string') vb = vb.split(/[ ,]+/).map(Number); var asp = Array.isArray(vb) && vb[2] ? vb[3] / vb[2] : +d.aspect || 1; if (!(asp > 0)) asp = 1;
    var w = Math.min(GW - 16, Math.max(.7 * GW, 300 * (.62 + .06 * Math.max(1, Math.min(8, n))))), h = w * asp, hc = CFG.ground * .62; if (h > hc) { h = hc; w = h / asp; }  /*v53: true canopy aspect, shrink evenly if too tall (was .72 squash + aspect none)*/ ay = Math.max(ay, 8 + h); var x0 = ax - w / 2, y0 = ay - h;  // v34: full-height crown; drops lower so the top branches tuck under it  // v34: ~70% wide, flattened organic crown
    var P = function (u, dflt) { return '/static/' + String(u || dflt).replace(/^\/?(static\/)?/, ''); }, src = P(d.svg, 'species/' + id + '_canopy.svg'), srcD = P(d.svg_dark, 'species/' + id + '_canopy_dark.svg');
    var at = ' x="' + f(x0) + '" y="' + f(y0) + '" width="' + f(w) + '" height="' + f(h) + '" preserveAspectRatio="xMidYMax meet"';
    return '<g class="r-canopy" aria-hidden="true" pointer-events="none"><image class="r-can-l" href="' + src + '"' + at + '/><image class="r-can-d" href="' + srcD + '"' + at + '/></g>';
  }
  function miniFinish(el, data) {  // static profile card: strip text/tags/labels/hit targets, crop to the STYLE.md mini viewBox, keep only the top of the roots
    var sv = el.querySelector('svg'); if (!sv) return; var st = el._roots;
    sv.querySelectorAll('.r-tag,.r-rtext,.r-labels,.r-pill,.r-badge,.r-addbud,.stub,.r-tick,.r-later,.r-hitp,.r-seed,text').forEach(function (n) { n.remove(); });
    sv.querySelectorAll('.r-sway,.r-pop,.r-rise,.r-grow,.r-draw,.r-fade,.r-newbr').forEach(function (n) { n.classList.remove('r-sway', 'r-pop', 'r-rise', 'r-grow', 'r-draw', 'r-fade', 'r-newbr'); });
    sv.querySelectorAll('[tabindex]').forEach(function (n) { n.removeAttribute('tabindex'); n.removeAttribute('role'); });
    var cp = svgEl('clipPath', { id: 'rmini' + Math.random().toString(36).slice(2, 6) }); cp.appendChild(svgEl('rect', { x: -2000, y: -2000, width: 5000, height: 2000 + st.Y + 110 }));
    (sv.querySelector('defs') || sv.insertBefore(svgEl('defs', {}), sv.firstChild)).appendChild(cp);
    sv.querySelectorAll('.r-item[data-type=root]').forEach(function (n) { n.setAttribute('clip-path', 'url(#' + cp.id + ')'); });
    var w = st.W === 900 ? '172 -80 556 980' : '-18 -80 556 980';  // v27: 80 units of headroom for the crown + legendary ring
    var hasPot = !!sv.querySelector('.r-potring'), fit = null;
    if (el._banner) { bannerFinish(el, sv, st); return; }  /*v41: park-planted tree, no pot*/
    if (hasPot) { /*v34 Profile: whole pot exterior, no soil cross-section, no roots (those stay on Home)*/
      sv.querySelectorAll('.r-soil,.r-soilshade,.r-horizon,.r-pebble,.r-under,.r-item[data-type=root],.r-potfill path:last-child').forEach(function (n) { n.remove(); });
      sv.querySelectorAll('[clip-path]').forEach(function (n) { if (n.closest('.r-potring,.r-potfill')) n.removeAttribute('clip-path'); }); }
    if (hasPot) try {  // v32: crop tightly to tree + pot (both walls), small padding, centered
      var bb = null, add = function (b) { if (!b || !(b.width > 0 || b.height > 0)) return; bb = bb ? [Math.min(bb[0], b.x), Math.min(bb[1], b.y), Math.max(bb[2], b.x + b.width), Math.max(bb[3], b.y + b.height)] : [b.x, b.y, b.x + b.width, b.y + b.height]; };
      sv.querySelectorAll('.r-trunk,.r-canopy,.r-seedbed,.r-item[data-type=branch],use[href^="#rl"],use[href^="#rf"]').forEach(function (n) { try { var b = n.getBBox(), m = n.getCTM && n.getCTM(), r = sv.getCTM(); if (m && r) { var k = r.inverse().multiply(m), pt = function (x, y) { var q = sv.createSVGPoint(); q.x = x; q.y = y; return q.matrixTransform(k); }, p1 = pt(b.x, b.y), p2 = pt(b.x + b.width, b.y + b.height); add({ x: Math.min(p1.x, p2.x), y: Math.min(p1.y, p2.y), width: Math.abs(p2.x - p1.x), height: Math.abs(p2.y - p1.y) }); } else add(b); } catch (e) {} });
      var cnB = null; try { var cnE = sv.querySelector('.r-canopy'); cnB = cnE && cnE.getBBox(); } catch (e) {}
      var cw = cnB && cnB.width > 0 ? cnB.width : (bb ? bb[2] - bb[0] : st.W), pk = Math.max(.12, Math.min(1, .28 * cw / st.W)), pky = Math.min(1.2, pk * 1.2) /*v41 Design: pot top ~28% of canopy width, 1.2x taller*/, tr = sv.querySelector('.r-trunk'), pcx = st.W / 2, py0 = st.Y - 12;
      try { if (tr) { var tb = tr.getBBox(); pcx = tb.x + tb.width / 2; } } catch (e) {}  // centred under the trunk
      if (pk < 1) { var ptf = 'translate(' + f(pcx) + ',' + f(py0) + ') scale(' + pk.toFixed(3) + ',' + pky.toFixed(3) + ') translate(' + f(-st.W / 2) + ',' + f(-py0) + ')';
        sv.querySelectorAll('.r-potfill,.r-potring,.r-soil,.r-soilshade,.r-horizon,.r-pebble,.r-under,.tier-glow,.tier-wrap,.r-item[data-type=root]').forEach(function (n) {
          var g = svgEl('g', { transform: ptf, class: 'r-potscale' }); n.parentNode.insertBefore(g, n); g.appendChild(n); }); }
      add({ x: pcx - st.W / 2 * pk, y: py0, width: st.W * pk, height: ((st.H - 30) - py0 + 4) * pky });  // pot: rim top .. base, both walls
      if (bb) { var pad = 10; fit = f(bb[0] - pad) + ' ' + f(bb[1] - pad) + ' ' + f(bb[2] - bb[0] + 2 * pad) + ' ' + f(bb[3] - bb[1] + 2 * pad); }
    } catch (e) {}
    sv.setAttribute('viewBox', fit || w); sv.setAttribute('preserveAspectRatio', 'xMidYMin meet');  // v37: never slice (phone cap cut the tree)
    if (!fit && !el._miniRetry) { el._miniRetry = 1; requestAnimationFrame(function () { api.mini(el, data); }); }  // v34: canopy at the card top  /*v30: crop was commented out by accident*/
    sv.setAttribute('aria-label', 'Your plant'); sv.style.width = '100%'; sv.style.height = '100%';
    if (fit) { var fv = fit.split(' ').map(Number); el.style.aspectRatio = f(fv[2]) + ' / ' + f(fv[3]); el.style.height = 'auto'; el.style.maxHeight = 'none'; el.style.width = 'min(100%, 340px, ' + f(Math.round((innerWidth < 560 ? 260 : 560) * fv[2] / fv[3])) + 'px)'; sv.setAttribute('preserveAspectRatio', 'xMidYMid meet'); }  // v38: card takes the fitted art's shape (no blank band), <=560px tall
    var t = String(data.tier || (st.pot && el.className.match(/tier-(\w+)/) || [])[1] || '').toLowerCase(); el.classList.remove('tier-rare', 'tier-epic', 'tier-legendary'); if (/^(rare|epic|legendary)$/.test(t)) el.classList.add('tier-' + t);
    var gl = sv.querySelector('.tier-glow'); if (gl) {  // v27 (3d design 1): opaque gold ring OVER the pot, no filters
      var rd = gl.firstChild && gl.firstChild.getAttribute('d'); gl.remove();
      if (rd) { var rg = svgEl('g', { class: 'tier-glow tier-ring', fill: 'none', 'stroke-linejoin': 'round' });
        [['#2A1E14', 22], ['#E8B23A', 12], ['#FFF1C2', 3]].forEach(function (q) { rg.appendChild(svgEl('path', { d: rd, stroke: q[0], 'stroke-width': q[1] })); });
        var pr = sv.querySelector('.r-potring'); if (pr && pr.parentNode) pr.parentNode.insertBefore(rg, pr.nextSibling); else sv.appendChild(rg); } }
  }
  function bannerFinish(el, sv, st) {  // v41: tree planted in the park grass; trunk foot = bottom anchor (banner canvas x=780, ground y=210)
    sv.querySelectorAll('.r-pot,.r-potfill,.r-potring,.r-potscale,.r-soil,.r-soilshade,.r-horizon,.r-pebble,.r-under,.tier-glow,.tier-wrap,.r-item[data-type=root],.r-root,.r-ground').forEach(function (n) { n.remove(); });
    var bb = null; sv.querySelectorAll('.r-trunk,.r-canopy,.r-item[data-type=branch],.r-seedbed,use[href^="#rl"],use[href^="#rf"]').forEach(function (n) { try { var b = n.getBBox(), m = n.getCTM(), r = sv.getCTM(); if (m && r) { var k = r.inverse().multiply(m), q = function (x, y) { var p = sv.createSVGPoint(); p.x = x; p.y = y; return p.matrixTransform(k); }, a = q(b.x, b.y), c = q(b.x + b.width, b.y + b.height); b = { x: Math.min(a.x, c.x), y: Math.min(a.y, c.y), width: Math.abs(c.x - a.x), height: Math.abs(c.y - a.y) }; }
      if (b.width > 0 || b.height > 0) bb = bb ? [Math.min(bb[0], b.x), Math.min(bb[1], b.y), Math.max(bb[2], b.x + b.width), Math.max(bb[3], b.y + b.height)] : [b.x, b.y, b.x + b.width, b.y + b.height]; } catch (e) {} });
    var gx = st.W / 2, gy = st.Y, tr = sv.querySelector('.r-trunk'); try { if (tr) { var tb = tr.getBBox(); gx = tb.x + tb.width / 2; gy = tb.y + tb.height; } } catch (e) {}
    if (!bb) { el._miniRetry || (el._miniRetry = 1, requestAnimationFrame(function () { api.mini(el, el._roots.data); })); bb = [gx - 60, gy - 120, gx + 60, gy]; }
    var A = 650 / 536, FB = .121, pad = 6, half = Math.max(gx - bb[0], bb[2] - gx) + pad, top = bb[1] - pad, vh = Math.max((gy - top) / (1 - FB), 340) /*v41: a seedling stays small in the park*/, vw = vh * A; if (2 * half > vw) { vw = 2 * half; vh = vw / A; }  // foot at 12.1% up the slot = canvas y 210
    var bnr = el.closest('.fp-banner'), big = bnr && bnr.querySelector('img[data-park="v_under_tree"]'), mid = bnr && bnr.querySelector('img[data-park="tree_base"]');  // v46 Leader: full-size park tree (stage 4+: canopy ~240 canvas wide, crown top ~y 25)
    if (big || mid) { var BIGH = 260 /*v53 crop: tree height in canvas units, foot at y210 (Design tunes)*/, cw = big ? 265 : 200, ch = big ? 184 : 140, H = gy - top, Wd = 2 * half, L = 0 /*v52 Leader: card proportions, no added trunk; shorter if width-capped*/;  // v49: lift the whole crown on a longer bare trunk (stage, not branch count)
      if (L > 2 && tr) { var lg = svgEl('g', { class: 'r-lift', transform: 'translate(0,' + f(-L) + ')' }); [].slice.call(tr.parentNode.childNodes).forEach(function (n) { if (n.nodeName !== 'defs') lg.appendChild(n); }); tr.parentNode.appendChild(lg);
        var w0 = CFG.trunk.w0 / 2, w1 = w0 * .82; var ext = svgEl('path', { class: 'r-trunk r-trunk-ext', d: 'M' + f(gx - w0) + ',' + f(gy) + ' C' + f(gx - w0 * .9) + ',' + f(gy - L * .5) + ' ' + f(gx - w1) + ',' + f(gy - L * .8) + ' ' + f(gx - w1) + ',' + f(gy - L - 2) + ' L' + f(gx + w1) + ',' + f(gy - L - 2) + ' C' + f(gx + w1) + ',' + f(gy - L * .8) + ' ' + f(gx + w0 * .9) + ',' + f(gy - L * .5) + ' ' + f(gx + w0) + ',' + f(gy) + 'Z' });
        lg.parentNode.insertBefore(ext, lg); top -= L; H += L; }
      var lowY = null; sv.querySelectorAll('.r-canopy image,use[href^="#rl"],use[href^="#rf"]').forEach(function (nd) { try { if (nd.closest('.r-can-d') || (nd.getClientRects && !nd.getClientRects().length && nd.tagName === 'image')) {} var b = nd.getBBox(), m = nd.getCTM(), r0 = sv.getCTM(); if (!m || !r0 || !b.height) return; var kk = r0.inverse().multiply(m), p = sv.createSVGPoint(); p.x = b.x + b.width / 2; p.y = b.y + b.height; var yb = p.matrixTransform(kk).y; if (lowY === null || yb > lowY) lowY = yb; } catch (e) {} });
      var cL = null; sv.querySelectorAll('.r-canopy image').forEach(function (nd) { try { var b = nd.getBBox(), m = nd.getCTM(), r0 = sv.getCTM(); if (!m || !r0 || !b.width) return; var p = sv.createSVGPoint(); p.x = b.x; p.y = b.y + b.height / 2; var xl = p.matrixTransform(r0.inverse().multiply(m)).x; if (cL === null || xl < cL) cL = xl; } catch (e) {} });
      var cB = null; sv.querySelectorAll('.r-canopy image').forEach(function (nd) { try { var b = nd.getBBox(), m = nd.getCTM(), r0 = sv.getCTM(); if (!m || !r0 || !b.height) return; var p = sv.createSVGPoint(); p.x = b.x + b.width / 2; p.y = b.y + b.height; var yb = p.matrixTransform(r0.inverse().multiply(m)).y; if (cB === null || yb > cB) cB = yb; } catch (e) {} });
      var k = big ? (cB !== null && gy - cB > 5 ? 91 / (gy - cB) /*v56: crown (canopy art) bottom at canvas y 119; blossoms may hang lower*/ : cL !== null && gx - cL > 5 ? 220 / (gx - cL) /*v55 Leader+Design: crown left edge at canvas x 560; low blossoms may hang below 125*/ : BIGH / H) /*v53 Leader: true size, no width cap*/ : Math.min(cw / Wd, ch / H); vw = 156 / k; vh = vw / A; }
    sv.setAttribute('viewBox', f(gx - vw / 2) + ' ' + f(gy - vh * (1 - FB)) + ' ' + f(vw) + ' ' + f(vh)); sv.setAttribute('preserveAspectRatio', 'xMidYMax meet'); sv.setAttribute('overflow', 'visible');
    if (big) { var KH = [[739.9, 170], [516.5, 160], [546.7, 161.5]]; document.querySelectorAll('.fp-park [data-head],.fp-park [data-head-man],.fp-park [data-head-woman],.fp-park [data-head-girl],.fp-park [data-head-boy]').forEach(function (e) { [].forEach.call(e.attributes, function (a) { if (/^data-head/.test(a.name)) { var v = a.value.split(/[ ,]+/).map(Number); if (isFinite(v[0])) KH.push(v); } }); });
      var kk2 = 156 / vw; sv.querySelectorAll('use[href^="#rl"],use[href^="#rf"],use[href^="#rb"]').forEach(function (nd) { try { var b = nd.getBBox(), m = nd.getCTM(), r0 = sv.getCTM(); if (!m || !r0) return; var T = r0.inverse().multiply(m), p1 = sv.createSVGPoint(), p2 = sv.createSVGPoint(); p1.x = b.x; p1.y = b.y; p2.x = b.x + b.width; p2.y = b.y + b.height; p1 = p1.matrixTransform(T); p2 = p2.matrixTransform(T);
        var X0 = 780 + (Math.min(p1.x, p2.x) - gx) * kk2, X1 = 780 + (Math.max(p1.x, p2.x) - gx) * kk2, Yb = 210 - (gy - Math.max(p1.y, p2.y)) * kk2, lift = 0;
        KH.forEach(function (hh) { if (X1 > hh[0] - 12 && X0 < hh[0] + 12 && Yb > hh[1] - 18) lift = Math.max(lift, Yb - (hh[1] - 18)); });  /*v55: >=6 units clear above every head (head ~12 tall): shorten that droop only*/
        if (lift > 0) { var t0 = nd.getAttribute('transform') || ''; nd.setAttribute('transform', 'translate(0,' + f(-lift / kk2) + ') ' + t0); } } catch (e) {} }); }
    if (big && innerWidth < 600) sv.querySelectorAll('.r-canopy').forEach(function (cg) { try { var b = cg.getBBox(); if (!b.width) return; var ox = b.x + b.width / 2, oy = b.y + b.height; cg.setAttribute('transform', 'translate(' + f(ox) + ',' + f(oy) + ') scale(1.3) translate(' + f(-ox) + ',' + f(-oy) + ') ' + (cg.getAttribute('transform') || '')); } catch (e) {} });  /*v57 Design: phone crown bigger, bottom edge fixed so it crops at the top*/
    var u = vw / 156, P = function (a) { return a.map(function (v) { return f(v); }).join(','); };  // u = tree units per banner-canvas px (slot is 156 canvas px wide)
    if (tr && !(big && el.closest(".fp-banner") && el.closest(".fp-banner").querySelector("img[data-park=tree_base]"))) { var t0 = CFG.trunk.w0 / 2, sk = (el.closest('.fp-banner') && el.closest('.fp-banner').querySelector('img[data-park="tree_base"]')) ? 70 / 42 /*v49: match 3d design 1's 70-wide tree_base flare*/ : .45 /*v42: no tree_base (below Leafy) = small flare*/; u = u * sk; var w18 = 9 * u, w42 = 21 * u, hv = sk >= 1 ? 2 / 3 : 1 /*v44 Design: flare 2/3 height at Leafy+*/, y196 = gy - 14 * u * hv, yT = gy - 22 * u * hv, xl = gx - 21 * u, xr = gx + 21 * u;  // Design: 18px at y~196 -> 42px at y=210, organic curve, blends up into the trunk
      var fp = svgEl('path', { class: 'r-flare', 'data-layer': 'flare', d: 'M' + P([gx - t0, yT]) + ' C' + P([gx - t0, yT + 4 * u]) + " " + P([gx - w18, y196 - 4 * u]) + ' ' + P([gx - w18, y196]) + ' C' + P([gx - w18 - 1 * u, gy - 6 * u * hv]) + ' ' + P([xl + 4 * u, gy - 1.5 * u]) + ' ' + P([xl, gy]) +
        ' Q' + P([gx, gy + 1.6 * u]) + ' ' + P([xr, gy]) + ' C' + P([xr - 4 * u, gy - 1.5 * u]) + ' ' + P([gx + w18 + 1 * u, gy - 6 * u * hv]) + ' ' + P([gx + w18, y196]) + ' C' + P([gx + w18, y196 - 4 * u]) + ' ' + P([gx + t0, yT + 4 * u]) + ' ' + P([gx + t0, yT]) + ' Z' });
      var ex0 = sv.querySelector('.r-trunk-ext'); if (ex0) ex0.parentNode.insertBefore(fp, ex0.nextSibling); else tr.parentNode.insertBefore(fp, tr.nextSibling); u = u / sk; }
    var g = svgEl('g', { class: 'r-ground', 'data-layer': 'ground', 'aria-hidden': 'true', 'pointer-events': 'none' });
    g.appendChild(svgEl('ellipse', { class: 'r-gshadow', cx: f(gx - 6 * u), cy: f(gy + 1 * u), rx: f(40 * u), ry: f(5 * u) }));
    if (tr) [[1, 34, 2], [1, 27, -1], [-1, 22, 1.5]].forEach(function (r) {  // short surface roots, mostly right: the man under the tree sits left of the trunk (canvas x 735-772)
      var x0 = gx + r[0] * 16 * u, x1 = gx + r[0] * r[1] * u; g.appendChild(svgEl('path', { class: 'r-sroot', d: 'M' + P([x0, gy - .5 * u]) + ' Q' + P([(x0 + x1) / 2, gy + (r[2] - 1.5) * u]) + ' ' + P([x1, gy + r[2] * .6 * u]), 'stroke-width': f(2.2 * u) })); });
    [[40, 1], [30, .8], [-46, .7], [52, .6]].forEach(function (t) { var x = gx + t[0] * u, s2 = 7 * t[1] * u;
      g.appendChild(svgEl('path', { class: 'r-tuft', d: 'M' + P([x - s2 * .5, gy + u]) + ' Q' + P([x - s2 * .4, gy - s2 * .6]) + ' ' + P([x - s2 * .7, gy - s2]) + ' Q' + P([x - s2 * .1, gy - s2 * .5]) + ' ' + P([x, gy - s2 * 1.2]) + ' Q' + P([x + s2 * .15, gy - s2 * .5]) + ' ' + P([x + s2 * .7, gy - s2 * .9]) + ' Q' + P([x + s2 * .4, gy - s2 * .4]) + ' ' + P([x + s2 * .5, gy + u]) + ' Z' })); });
    g.querySelectorAll(".r-sroot,.r-tuft").forEach(function (n) { n.remove(); });  /*v52 Leader: no roots or grass tufts; shadow only*/
    var ban = el.closest('.fp-banner'), tbi = ban && ban.querySelector('img[data-park="tree_base"]'), tbOn = tbi && tbi.getClientRects().length && getComputedStyle(tbi).visibility !== 'hidden';  // 3d design 1's park_tree_base art replaces the placeholder
    if (!tbOn) { var fl0 = sv.querySelector('.r-flare'); if (fl0) fl0.parentNode.insertBefore(g, fl0); else sv.appendChild(g); }
    sv.setAttribute('aria-label', 'Your tree'); sv.style.width = '100%'; sv.style.height = '100%'; el.classList.add('r-planted');
  }
  var api = {
    /* roots.mini(el, data): one static render for the Profile "My plant" card (~170x300). No listeners, labels, tags, sway or intro.
       data = same shape as GET /roots/data (branches, roots, garden, pot, species) + optional tier:'rare'|'epic'|'legendary' (adds .tier-* on el).
       Usage: roots.mini(document.querySelector('#myPlant'), data)  — call again with new data to redraw. */
    mini: function (el, data) { data = data || { branches: [], roots: [] }; el.classList.add('roots', 'r-mini');
      var hid = !el.getClientRects().length, ost = hid && el.getAttribute('style');  // v38: measure even while the card is still display:none (Profile reveals it after mini returns)
      if (hid) { el.style.display = 'block'; el.style.visibility = 'hidden'; el.style.position = 'absolute'; el.style.width = '300px'; el.style.height = '530px'; }
      var cw = el.clientWidth; Object.defineProperty(el, 'clientWidth', { configurable: true, get: function () { return 900; } });  // always the wide 900 geometry, cropped by viewBox
      try { render(el, data, { mini: true }); } finally { delete el.clientWidth; if (hid) { var ar = el.style.aspectRatio, wd = el.style.width; if (ost) el.setAttribute('style', ost); else el.removeAttribute('style'); if (ar) { el.style.aspectRatio = ar; el.style.height = 'auto'; el.style.maxHeight = 'none'; el.style.width = wd; } } } void cw; return el; },
    config: CFG,
    mount: function (el, data) { el.classList.add('roots'); bind(el); data = data || { branches: [], roots: [] };
      var intro = (reduce && reduce.matches) ? 'fade' : 'grow';
      render(el, data, { intro: intro, newIds: newIds(data), popN: newLeaves(data) }); el.dataset.rootsMounted = '1';
      setTimeout(function () {  // leaves earned on other pages (session_moment.js queue) grow once the intro has played
        var q = []; try { q = window.prodyTakePendingLeaves ? window.prodyTakePendingLeaves() || [] : JSON.parse(localStorage.getItem('prody_pending_leaves') || '[]'); localStorage.removeItem('prody_pending_leaves'); } catch (e) {}
        void q;  // v20: leaves already counted by /roots/data and animated via popN
      }, reduce && reduce.matches ? 0 : 2600);
      return el; },
    update: function (el, data) { if (!el._roots) return api.mount(el, data); render(el, data, { newIds: newIds(data), popN: newLeaves(data) }); return el; },
    growLeaf: function (el, courseId) {
      var st = el && el._roots; if (!st) return;
      var d = JSON.parse(JSON.stringify(st.data)), b = (d.branches || []).filter(function (x) { return x.course_id == courseId; })[0]; if (!b) return;
      b.leaves = (b.leaves | 0) + 1; b.minutes = Math.max(b.minutes || 0, b.leaves * 60);
      render(el, d, { pop: b.course_id });
    },
    refresh: function (el) { var src = el.dataset.rootsSrc; if (src) return load(el, src, true); }
  };
  function load(el, src, upd) {
    return fetch(src, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        if (r.redirected && /\/login/.test(r.url)) { location.href = r.url; throw new Error('signed out'); }
        if (!r.ok) throw new Error('HTTP ' + r.status + ' ' + src);
        if (!/json/.test(r.headers.get('content-type') || '')) throw new Error('not JSON from ' + src);
        return r.json();
      })
      .then(function (d) {
        d = d && typeof d === 'object' ? d : {};
        ['branches', 'roots', 'later'].forEach(function (k) { if (!Array.isArray(d[k])) d[k] = []; });
        try { upd ? api.update(el, d) : api.mount(el, d); } catch (e) { nap('render', e); }
      }, function (e) { nap('fetch', e); });
    function nap(kind, err) { console.error('[roots] ' + kind + ' error', err);
      el.innerHTML = '<p style="padding:24px;margin:0;font:500 14px Inter,sans-serif">Your plant is taking a nap. Refresh to try again.</p>'; }
  }
  function auto(root) {
    (root.querySelectorAll ? root : document).querySelectorAll('.roots:not([data-roots-mounted])').forEach(function (el) {
      if (el.dataset.roots) { el.dataset.rootsMounted = '1'; var d; try { d = JSON.parse(el.dataset.roots); } catch (e) { d = null; } api.mount(el, d); }
      else if (el.dataset.rootsSrc) { el.dataset.rootsMounted = '1'; bind(el); load(el, el.dataset.rootsSrc); }
    });
  }
  window.roots = api;
  var BAN = null;  // v35 banner mode: [data-roots-mode=banner] gets the real grown tree (canopy, branches+flowers, full pot), no soil/roots/tags/interaction
  function banners() {
    var els = [].slice.call(document.querySelectorAll('[data-roots-mode="banner"]:not([data-banner-done])')); if (!els.length) return;
    BAN = BAN || fetch('/roots/data', { credentials: 'same-origin', headers: { Accept: 'application/json' } }).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    els.forEach(function (slot) { slot.dataset.bannerDone = '1'; BAN.then(function (d) { if (!d) return;  // keep the fallback thumbs if data fails
      var host = document.createElement('div'); host.className = 'r-banner'; host.setAttribute('aria-hidden', 'true'); slot.innerHTML = ''; slot.appendChild(host);
      host._banner = 1; try { api.mini(host, d); } catch (e) { return; }
      var tidy = function () { var sv = host.querySelector('svg'); if (!sv) return; sv.querySelectorAll('.r-tagtop,.r-tag,.r-chip,text,.r-hitp').forEach(function (n) { n.remove(); });
      sv.removeAttribute('role'); sv.setAttribute('focusable', 'false'); sv.style.width = 'auto'; sv.style.height = '100%';
      var cn = sv.querySelector('.r-canopy'); cn && cn.setAttribute('data-layer', 'canopy');
      sv.querySelectorAll('.r-branch,.r-branch-kit').forEach(function (n) { n.setAttribute('data-layer', 'branch'); });
      };
      tidy(); setTimeout(tidy, 900); setTimeout(tidy, 2500); }); });  // canopy art loads async and re-renders
  }
  function start() {
    auto(document); banners();
    new MutationObserver(function (ms) { ms.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 1) { if (n.matches('.roots')) auto(n.parentNode); else if (n.querySelector('.roots')) auto(n); if (n.matches('[data-roots-mode="banner"]') || n.querySelector('[data-roots-mode="banner"]')) banners(); } }); }); })
      .observe(document.body, { childList: true, subtree: true });
  }
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', start) : start();
})();

/* v6 click cards: root + branch, Mark done / Undo / Edit (Coder) */
(function () {
  'use strict';
  if (!window.roots) return;
  var RC = window.roots.config.root; RC.wMin = 7; RC.wDefault = 7; RC.w1 = 3.5; RC.wMax = Math.max(RC.wMax, 15);  // v10: >=3.5px tip, ~7px at trunk, + grade weight
  function esc(x) { return String(x == null ? '' : x).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function hrs(m) { var h = (m || 0) / 60; return h < 1 ? Math.round(m || 0) + ' min' : (Math.round(h * 10) / 10) + ' h'; }
  function days(n) { return n < 0 ? Math.abs(n) + (n === -1 ? ' day' : ' days') + ' overdue' : n === 0 ? 'due today' : n === 1 ? 'due tomorrow' : n + ' days left'; }
  function nice(d) { try { return new Date(d + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' }); } catch (e) { return d; } }
  var tok = null;
  function csrf() {
    var m = document.querySelector('meta[name=csrf-token]') || document.querySelector('input[name=csrf_token]');
    if (m) return Promise.resolve(m.content || m.value);
    if (tok) return Promise.resolve(tok);
    return fetch('/add_courses', { credentials: 'same-origin' }).then(function (r) { return r.text(); }).then(function (h) {
      var x = /name=["']csrf_token["'][^>]*value=["']([^"']+)/.exec(h) || /value=["']([^"']+)["'][^>]*name=["']csrf_token/.exec(h) || /csrf-token["'] content=["']([^"']+)/.exec(h); tok = x && x[1]; return tok; });
  }
  function post(url, body) {
    return csrf().then(function (t) { return fetch(url, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': t || '', Accept: 'application/json' }, body: JSON.stringify(body) }); })
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || j.ok === false) throw new Error(j.error || (r.status === 404 ? 'That deadline no longer exists.' : r.status === 400 ? 'Check the name and date.' : 'Something went wrong (' + r.status + ').')); return j; }); });
  }
  function course(st, id) { return (st.data.branches || []).filter(function (b) { return b.course_id == id; })[0] || {}; }
  function dotOf(el, id) { var c = el.querySelector('.r-item[data-type=branch][data-id="' + id + '"] .r-chip'); return c ? c.style.fill : 'var(--r-accent)'; }
  function close(el) { /*v9*/ var c = el.querySelector('.r-card'); c && c.remove(); el.querySelectorAll('.r-scrim').forEach(function (n) { n.remove(); }); el.querySelectorAll('.r-tagon').forEach(function (n) { n.classList.remove('r-tagon'); }); el.classList.remove('has-card'); if (el._esc) { document.removeEventListener('keydown', el._esc); el._esc = null; } el.querySelectorAll('.r-item.glow').forEach(function (n) { n.classList.remove('glow'); }); }
  function refresh(el) { var t = el.querySelector('.r-toast'); return el.dataset.rootsSrc ? Promise.resolve(window.roots.refresh(el)).then(function () { if (t && t.isConnected === false && t._live) el.appendChild(t); }) : null; }
  function toast(el, msg, undo) {
    var t = el.querySelector('.r-toast'); t && t.remove(); t = document.createElement('div'); t.className = 'r-toast'; t.setAttribute('role', 'status');
    t.innerHTML = '<span>' + esc(msg) + '</span>' + (undo ? '<button type="button" class="r-btn r-link">Undo</button>' : ''); el.appendChild(t);
    t._live = true; var tm = setTimeout(function () { t._live = false; t.remove(); }, 5000);
    if (undo) t.querySelector('button').onclick = function () { clearTimeout(tm); t._live = false; t.remove(); undo(); };
  }
  function tagOf(el, id) { return el.querySelector('.r-tagwrap[data-id="' + id + '"] .r-tagbody') || el.querySelector('.r-item[data-type=branch][data-id="' + id + '"] .r-tagbody'); }
  function place(el, card, x, y, W, tagB) {
    if (tagB) { var w0 = tagB.closest('.r-tagwrap,.r-item'); w0 && w0.classList.add('r-tagon'); }
    if (window.innerWidth < 600) { /*v30 phone: bottom sheet above the tabbar; tree stays visible*/ card.classList.add('r-sheet'); card.style.width = ''; card.style.left = ''; card.style.top = '';
      var tb = 0; document.querySelectorAll('.tabbar').forEach(function (n) { var r = n.getBoundingClientRect(); if (r.height && getComputedStyle(n).position === 'fixed') tb = Math.max(tb, innerHeight - r.top); });
      card.style.setProperty('--r-sheet-b', (tb ? tb + 8 : 0) + 'px'); card.insertAdjacentHTML('afterbegin', '<i class="r-grab" aria-hidden="true"></i>');
      var bd = document.createElement('div'); bd.className = 'r-scrim'; bd.onclick = function (e) { e.stopPropagation(); close(el); }; el.appendChild(bd);
      el.appendChild(card); el.classList.add('has-card'); var t0 = el.querySelector('.r-tip'); t0 && t0.classList.remove('show');
      if (tagB) requestAnimationFrame(function () { var tr = tagB.getBoundingClientRect(), sr = card.getBoundingClientRect(), d = 0;  // pan the tapped tag into view above the sheet
        if (tr.bottom > sr.top - 12) d = tr.bottom - (sr.top - 12); else if (tr.top < 64) d = tr.top - 64;
        if (d) try { window.scrollBy({ top: d, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); } catch (e) { window.scrollBy(0, d); } });
      return; }
    if (tagB) { /*v33 desktop: card beside the tapped tag with an arrow, flipping to stay inside the frame*/
      var er = el.getBoundingClientRect(), ar = tagB.getBoundingClientRect(), cw2 = Math.min(310, el.clientWidth - 16); card.style.width = cw2 + 'px';
      el.appendChild(card); el.classList.add('has-card'); var tq = el.querySelector('.r-tip'); tq && tq.classList.remove('show');
      var ch2 = card.offsetHeight, ax = ar.left - er.left, ay = ar.top - er.top, aw = ar.width, ah = ar.height, G2 = 14, cl2 = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
      var opts = [['right', ax + aw + G2, ay + ah / 2 - ch2 / 2], ['left', ax - G2 - cw2, ay + ah / 2 - ch2 / 2], ['down', ax + aw / 2 - cw2 / 2, ay + ah + G2], ['up', ax + aw / 2 - cw2 / 2, ay - G2 - ch2]];
      var others = [].slice.call(el.querySelectorAll('.r-tagbody')).filter(function (n) { return n !== tagB; }).map(function (n) { var q = n.getBoundingClientRect(); return [q.left - er.left, q.top - er.top, q.right - er.left, q.bottom - er.top]; });
      var cost = function (o) { var L = cl2(o[1], 8, el.clientWidth - cw2 - 8), T = cl2(o[2], 8, Math.max(8, el.clientHeight - ch2 - 8)), c0 = (Math.abs(L - o[1]) + Math.abs(T - o[2])) * 4;  // v35: least overlap with other tags
        others.forEach(function (b) { var w = Math.min(L + cw2, b[2]) - Math.max(L, b[0]), h = Math.min(T + ch2, b[3]) - Math.max(T, b[1]); if (w > 0 && h > 0) c0 += w * h; }); return c0; };
      var pick = opts.map(function (o, i) { return [cost(o) + i, o]; }).sort(function (a, b) { return a[0] - b[0]; })[0][1];
      var L2 = cl2(pick[1], 8, el.clientWidth - cw2 - 8), T2 = cl2(pick[2], 8, Math.max(8, el.clientHeight - ch2 - 8)); card.style.left = L2 + 'px'; card.style.top = T2 + 'px';
      var arw = document.createElement('i'); arw.className = 'r-arrow'; arw.dataset.side = pick[0];
      if (pick[0] === 'right' || pick[0] === 'left') arw.style.top = cl2(ay + ah / 2 - T2, 14, ch2 - 14) + 'px'; else arw.style.left = cl2(ax + aw / 2 - L2, 14, cw2 - 14) + 'px';
      card.appendChild(arw); return; }
    var r = el.clientWidth / W, px = x * r, py = y * r, cw = Math.min(310, el.clientWidth - 16);
    card.style.width = cw + 'px'; card.style.left = Math.max(8, Math.min(el.clientWidth - cw - 8, px - cw / 2)) + 'px';
    el.appendChild(card); el.classList.add('has-card'); var t = el.querySelector('.r-tip'); t && t.classList.remove('show'); var ch = card.offsetHeight; card.style.top = Math.max(8, Math.min(el.clientHeight - ch - 8, py + 14)) + 'px';
  }
  function rootCard(el, id) {
    var st = el._roots, d = (st.data.roots || []).filter(function (x) { return x.deadline_id == id; })[0]; if (!d) return;
    var b = course(st, d.course_id), it = st.items['root:' + id] || {}, a = d.actions || {};
    var doneUrl = a.done_url || '/api/deadlines/' + id + '/done', editUrl = a.edit_url || '/api/deadlines/' + id;
    var c = document.createElement('div'); c.className = 'r-card'; c.setAttribute('role', 'dialog'); c.setAttribute('aria-label', d.name);
    c.innerHTML = '<button type="button" class="r-x" aria-label="Close">×</button><h4><i class="r-cdot" style="background:' + esc(dotOf(el, d.course_id)) + '"></i>' + esc(d.name) + '</h4>' +
      '<dl><dt>Class</dt><dd>' + esc(b.code || b.name || '—') + '</dd><dt>Due</dt><dd>' + esc(nice(d.due)) + ' · ' + days(d.days_left | 0) + '</dd>' +
      (d.weight != null ? '<dt>Weight</dt><dd>' + Math.round(d.weight) + '% of grade</dd>' : '') + (d.studied_minutes ? '<dt>Studied</dt><dd>' + hrs(d.studied_minutes) + '</dd>' : '') + '</dl>' +
      '<div class="r-acts"><a class="r-btn r-primary" href="/study?course_id=' + encodeURIComponent(d.course_id) + '">Start a focus session</a><button type="button" class="r-btn" data-a="done">Mark done</button><button type="button" class="r-btn" data-a="edit">Edit</button></div><p class="r-err" role="alert" hidden></p>';
    place(el, c, it.x || 0, it.y || 0, it.W || 900);
    var err = c.querySelector('.r-err'); function fail(e) { err.textContent = e.message; err.hidden = false; }
    c.querySelector('[data-a=done]').onclick = function () {
      post(doneUrl, { done: true }).then(function () {
        var g = el.querySelector('.r-item[data-type=root][data-id="' + id + '"]'); close(el); g && g.classList.add('r-gone');
        toast(el, 'Marked “' + d.name + '” done', function () { post(doneUrl, { done: false }).then(function () { refresh(el); }, function (e) { toast(el, e.message); }); });
        setTimeout(function () { refresh(el); }, 600);
      }, fail); };
    c.querySelector('[data-a=edit]').onclick = function () {
      var f = document.createElement('form'); f.className = 'r-edit';
      f.innerHTML = '<label>Name<input name="name" required maxlength="120" value="' + esc(d.name) + '"></label><label>Due<input name="date" type="date" required value="' + esc(d.due) + '"></label><div class="r-acts"><button class="r-btn r-primary">Save</button><button type="button" class="r-btn" data-a="cancel">Cancel</button></div>';
      c.querySelector('.r-acts').replaceWith(f); f.name.focus();
      f.querySelector('[data-a=cancel]').onclick = function () { close(el); };
      f.onsubmit = function (e) { e.preventDefault(); err.hidden = true;
        post(editUrl, { name: f.name.value.trim(), date: f.date.value }).then(function () { close(el); toast(el, 'Saved'); refresh(el); }, fail); };
    };
    wire(el, c);
  }
  function branchCard(el, id) {
    var st = el._roots, b = course(st, id), it = st.items['branch:' + id] || {}; if (!b.course_id) return;
    var next = (st.data.roots || []).concat(st.data.later || []).filter(function (d) { return d.course_id == id; }).sort(function (x, y) { return (x.days_left | 0) - (y.days_left | 0); }).slice(0, 3);
    var c = document.createElement('div'); c.className = 'r-card'; c.setAttribute('role', 'dialog'); c.setAttribute('aria-label', b.name || b.code);
    c.innerHTML = '<button type="button" class="r-x" aria-label="Close">×</button><h4><i class="r-cdot" style="background:' + esc(dotOf(el, id)) + '"></i>' + esc(b.code || b.name) + '</h4>' +
      (b.code && b.name && b.name !== b.code ? '<p class="r-sub">' + esc(b.name) + '</p>' : '') +
      '<dl><dt>Studied</dt><dd>' + hrs(b.minutes) + ' this term</dd><dt>Done</dt><dd>' + (b.flowers | 0) + ' tasks</dd></dl>' +
      '<p class="r-h">Next up</p><ul>' + (next.length ? next.map(function (d) { return '<li><span>' + esc(d.name) + '</span><em>' + esc(nice(d.due)) + '</em></li>'; }).join('') : '<li><span>Nothing due. Nice.</span></li>') + '</ul>' +
      '<div class="r-acts"><a class="r-btn r-primary" href="/study?course_id=' + encodeURIComponent(id) + '">Start a focus session</a></div>';
    place(el, c, it.x || 0, it.y || 0, it.W || 900, tagOf(el, id)); wire(el, c);
  }
  function wire(el, c) {
    if (!el._esc) { el._esc = function (e) { if (e.key === 'Escape') close(el); }; document.addEventListener('keydown', el._esc); }
    try { c.querySelector('.r-x').focus({ preventScroll: true }); } catch (e) {}
    try { var rm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches; if (!c.classList.contains('r-sheet')) requestAnimationFrame(function () { c.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: rm ? 'auto' : 'smooth' }); }); } catch (e) {}
    c.querySelector('.r-x').onclick = function () { close(el); };
    c.addEventListener('click', function (e) { e.stopPropagation(); }); c.addEventListener('pointerover', function (e) { e.stopPropagation(); });
    c.addEventListener('keydown', function (e) { e.stopPropagation(); if (e.key === 'Escape') close(el); });
  }
  document.addEventListener('roots:select', function (e) {
    var el = e.target.closest('.roots'); if (!el || !el._roots || el.dataset.rootsCards === 'off') return;
    var t = e.detail.type; if (t !== 'root' && t !== 'branch') return; e.preventDefault(); close(el);
    if (t === 'root') { var d = (el._roots.data.roots || []).filter(function (x) { return x.deadline_id == e.detail.id; })[0];
      d && el.querySelectorAll('.r-item[data-type=branch][data-id="' + d.course_id + '"]').forEach(function (n) { n.classList.add('glow'); }); rootCard(el, e.detail.id); }
    else branchCard(el, e.detail.id);
  });
  document.addEventListener('pointerover', function (e) {  // root hover -> its branch glows
    var g = e.target.closest && e.target.closest('.roots .r-item[data-type=root]'), el = g && g.closest('.roots');
    document.querySelectorAll('.r-item.hglow').forEach(function (n) { n.classList.remove('hglow'); }); if (!g || !el._roots) return;
    var d = (el._roots.data.roots || []).filter(function (x) { return x.deadline_id == g.dataset.id; })[0];
    d && el.querySelectorAll('.r-item[data-type=branch][data-id="' + d.course_id + '"]').forEach(function (n) { n.classList.add('hglow'); });
  });
  document.addEventListener('click', function (e) { if (!e.target.closest('.r-card,.r-item,.r-toast')) document.querySelectorAll('.roots').forEach(close); });
})();
