/* Zen growth: seed-drop intro at real-time fps, then remaining frames map to session progress.
   elapsed = banked + (running ? now - startedAt : 0).
   Design: soil contact N=14 (1-based) for tulip+peony; clips are 30fps → intro ≈0.47s. */
(function (root) {
  var FRAMES = 220, INTRO_FPS = 30;
  /* 1-based inclusive last intro frame (seed first touches soil). Per-flower; Design may revise. */
  var SOIL_CONTACT = { tulip: 14, peony: 14 };

  function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
  function create(durationMs, now) { return { duration: Math.max(1, +durationMs || 0), banked: 0, startedAt: now, running: true }; }
  function elapsed(s, now) { return (s.banked || 0) + (s.running ? Math.max(0, now - s.startedAt) : 0); }
  function pause(s, now) { return s.running ? { duration: s.duration, banked: elapsed(s, now), startedAt: null, running: false } : s; }
  function resume(s, now) { return s.running ? s : { duration: s.duration, banked: s.banked, startedAt: now, running: true }; }
  function finish(s) { return { duration: s.duration, banked: s.duration, startedAt: null, running: false }; }
  function progress(s, now) { return clamp(elapsed(s, now) / s.duration, 0, 1); }
  /* Pure progress→index (Functionality tests). Growth-only; no intro. */
  function frameIndex(p, n) { return Math.min(n - 1, Math.max(0, Math.floor(p * n))); }
  function frameUrl(base, name, i, ext) { return base + '/' + name + '_' + String(i + 1).padStart(4, '0') + (ext || '.png'); }
  function soilContact(flower) { return SOIL_CONTACT[flower] || 14; }
  function introMs(flower) { return soilContact(flower) / INTRO_FPS * 1000; }

  /* Full display index: frames 1..N at INTRO_FPS, then N+1..n over time after the drop.
     contact1 = 1-based inclusive last intro frame. reducedMotion → show frame N immediately, no intro play. */
  function displayFrame(elapsedMs, durationMs, n, contact1, reducedMotion) {
    n = n || FRAMES;
    var introN = contact1 == null ? 14 : +contact1;
    if (introN < 1) introN = 1;
    if (introN > n) introN = n;
    var e = Math.max(0, +elapsedMs || 0), d = Math.max(1, +durationMs || 1);
    if (reducedMotion) {
      if (e <= 0) return introN - 1;
      var gp0 = clamp(e / d, 0, 1);
      return Math.min(n - 1, introN + Math.floor(gp0 * (n - introN)));
    }
    var iMs = introN / INTRO_FPS * 1000;
    if (e < iMs) return Math.min(introN - 1, Math.floor((e / 1000) * INTRO_FPS));
    var growth = n - introN;
    if (growth <= 0) return n - 1;
    var gp = clamp((e - iMs) / Math.max(1, d - iMs), 0, 1);
    return Math.min(n - 1, introN + Math.floor(gp * growth));
  }

  function save(key, s) { try { root.localStorage.setItem(key, JSON.stringify(s)); } catch (e) {} }
  function load(key) { try { var s = JSON.parse(root.localStorage.getItem(key)); return s && s.duration > 0 ? s : null; } catch (e) { return null; } }
  function preferReduce() {
    try { return !!(root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }

  /* DOM driver. opts: {flower, base, durationMs, storageKey, onBloom, frames=220, ext='.webp', fadeMs=300, preload=5}
     imgOrWin: the visible <img> or its .zfl-win (two stacked imgs for cross-fade). */
  function mount(imgOrWin, opts) {
    opts = opts || {};
    var n = opts.frames || FRAMES, key = opts.storageKey || 'zenGrowth', ext = opts.ext || '.webp';
    var fadeMs = opts.fadeMs == null ? 300 : opts.fadeMs, ahead = opts.preload == null ? 5 : opts.preload;
    var rm = preferReduce();
    var win = imgOrWin && imgOrWin.classList && imgOrWin.classList.contains('zfl-win') ? imgOrWin
            : (imgOrWin && imgOrWin.parentElement && imgOrWin.parentElement.classList && imgOrWin.parentElement.classList.contains('zfl-win') ? imgOrWin.parentElement : null);
    var a = win ? (win.querySelector('.zfl-a') || win.querySelector('img')) : imgOrWin;
    var b = win ? win.querySelector('.zfl-back') : null;
    if (win && a && !b && root.document) {
      b = a.cloneNode(false); b.className = (a.className || '').replace(/\bzfl-a\b/g, 'zfl-back'); if (!/\bzfl-back\b/.test(b.className)) b.className += ' zfl-back';
      b.removeAttribute('id'); b.alt = ''; b.setAttribute('aria-hidden', 'true'); win.appendChild(b);
    }
    var s = load(key);
    if (!s) s = create(opts.durationMs, Date.now());
    var cur = -1, cache = {}, raf = null, front = a, back = b, fading = false;
    function url(i) { return frameUrl(opts.base, opts.flower, i, ext); }
    function contact() { return soilContact(opts.flower); }
    function pre(i) {
      if (i < 0 || i >= n || cache[i]) return;
      if (typeof Image === 'undefined') return;
      var im = new Image(); im.src = url(i); cache[i] = im;
    }
    function show(i, instant) {
      if (!front) return;
      var src = url(i);
      for (var k = 1; k <= ahead; k++) pre(i + k);
      if (!back || rm || instant || fadeMs <= 0 || !front.src || cur < 0) {
        front.src = src; if (front.classList) { front.classList.add('on'); if (back && back.classList) back.classList.remove('on'); }
        cur = i; return;
      }
      if (fading) { front.src = src; cur = i; return; }
      fading = true;
      var next = cache[i];
      function swap() {
        back.src = src;
        var done = function () {
          if (back.classList) back.classList.add('on');
          if (front.classList) front.classList.remove('on');
          var tmp = front; front = back; back = tmp; fading = false; cur = i;
        };
        if (back.decode) {
          back.decode().then(done).catch(done);
        } else {
          if (back.complete) done(); else back.onload = done;
        }
      }
      if (next && next.complete) { back.src = src; swap(); }
      else {
        var im = new Image();
        im.onload = function () { cache[i] = im; swap(); };
        im.onerror = function () { front.src = src; fading = false; cur = i; };
        im.src = src;
      }
    }
    function tick() {
      var i = displayFrame(elapsed(s, Date.now()), s.duration, n, contact(), rm);
      if (i !== cur) show(i, false);
      if (cur >= n - 1 && opts.onBloom) { var f = opts.onBloom; opts.onBloom = null; f(); }
    }
    function loop() { tick(); if (s.running) raf = root.requestAnimationFrame ? root.requestAnimationFrame(loop) : (raf = setTimeout(loop, 16)); }
    function stop() {
      if (raf != null) {
        if (root.cancelAnimationFrame) root.cancelAnimationFrame(raf);
        else clearTimeout(raf);
        raf = null;
      }
    }
    function start() { stop(); tick(); if (s.running) loop(); }
    if (root.document) root.document.addEventListener('visibilitychange', function () { if (!root.document.hidden) tick(); });
    /* reduced motion: land on contact frame immediately before first paint of growth */
    if (rm) show(contact() - 1, true);
    save(key, s);
    start();
    return {
      pause: function () { s = pause(s, Date.now()); save(key, s); tick(); stop(); },
      resume: function () { s = resume(s, Date.now()); save(key, s); start(); },
      reset: function (ms) { s = create(ms || s.duration, Date.now()); save(key, s); cur = -1; start(); },
      finish: function () { s = finish(s); save(key, s); tick(); stop(); },
      clear: function () { stop(); try { root.localStorage.removeItem(key); } catch (e) {} },
      progress: function () { return progress(s, Date.now()); },
      setFlower: function (f, base) { opts.flower = f; opts.base = base; cur = -1; cache = {}; tick(); },
      running: function () { return !!s.running; },
      frame: function () { return cur; }
    };
  }

  var api = {
    FRAMES: FRAMES, INTRO_FPS: INTRO_FPS, SOIL_CONTACT: SOIL_CONTACT,
    create: create, elapsed: elapsed, pause: pause, resume: resume, finish: finish, progress: progress,
    frameIndex: frameIndex, frameUrl: frameUrl, displayFrame: displayFrame,
    soilContact: soilContact, introMs: introMs, mount: mount
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.ZenGrowth = api;
})(typeof window !== 'undefined' ? window : this);
