/* Coder v33: new Recraft bud art (shop/bloom/*_grow), GSAP sway + eased finish open when window.gsap exists; CSS fallback kept.
   Coder v29 · Focus bloom REBUILD: seed -> sprout -> leaves -> bud -> full bloom across the whole session (t = elapsed / duration).
   Driven by `focus:tick` {left,total,isBreak,running,hold} from study.html / zen.html (host: .timer-ring or [data-fbloom-host]).
   Every part is its own <g id> with its own pivot; only transform + opacity change (1s linear CSS transitions per tick), so it is
   compositor-cheap on iPhone. Parts (Design's art, tools/copy_bloom_art.sh): seed, stem, leaf-1..3, bud, petal-1..6, center,
   each <g data-pivot>. Art: /static/shop/bloom/<species>_grow(_dark).svg, falling back to default_grow. Breeze sway + per-stage settle are CSS (rotate/translate). Paused when document.hidden. Reduced motion: no sway,
   no bounce, pose steps through 4 stages with an opacity crossfade only. Old rig/stage version: /tmp/coder_land_bak3/. */
(function () {
  var host = document.querySelector('.timer-ring, [data-fbloom-host]'); if (!host) return;
  var RM = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches, NS = 'http://www.w3.org/2000/svg';
  var box = document.createElement('div'); box.className = 'fbloom fb2' + (RM ? ' rm' : ''); box.setAttribute('aria-hidden', 'true');
  host.insertAdjacentElement('afterend', box);
  if (!document.getElementById('fb2-css')) { var cs = document.createElement('style'); cs.id = 'fb2-css';
    cs.textContent = '.fbloom.fb2{width:min(200px,52vw);height:auto;aspect-ratio:80/92;margin:8px auto 0;position:relative;--fb-dur:1s}.fb2 svg{display:block;width:100%;height:100%;overflow:visible}' +
      '.fb2 .fb-sw{transform-box:view-box;transform-origin:60px 100px}.fb2:not(.rm):not(.gs) .fb-sw{animation:fb-sway 7s ease-in-out infinite}.fb2.fb-still .fb-sw{animation-play-state:paused}' +
      '@keyframes fb-sway{0%,100%{transform:rotate(-1.2deg)}50%{transform:rotate(1.2deg)}}' +
      '.fb2 .fb-bob{transform-box:view-box}.fb2.fb-settle:not(.rm) .fb-bob{animation:fb-settle .7s cubic-bezier(.3,1.5,.5,1)}@keyframes fb-settle{0%{transform:translateY(0)}35%{transform:translateY(1.6px)}100%{transform:translateY(0)}}' +
      '.fb2 [data-p]{transform-box:view-box;transition:transform var(--fb-dur) linear,opacity var(--fb-dur) linear;will-change:transform}' +
      '.fb2.open [data-p]{transition-timing-function:cubic-bezier(.34,1.25,.64,1)}.fb2.rm [data-p]{transition:opacity 1s ease}' +
      '.fb2 [data-p]{backface-visibility:hidden}';
    document.head.appendChild(cs); }
  var sp = { id: 'default', blooms: true, bloom_color: '#F08A6C' }, P = {}, T = 0, ready = false, pending = null, done = false, stage = -1, leafy = false;
  var dark = function () { return document.documentElement.getAttribute('data-theme') === 'dark'; };
  var cl = function (x) { return x < 0 ? 0 : x > 1 ? 1 : x; }, ss = function (x) { x = cl(x); return x * x * (3 - 2 * x); }, lerp = function (a, b, k) { return a + (b - a) * k; };
  var win = function (t, a, w) { return ss((t - a) / w); };
  var sid = function () { return String(sp.id || 'default').replace(/^species_/, '').replace(/[^a-z0-9_]/gi, ''); };
  var LEAF = { 'leaf-1': [.22, .16, 1, 57], 'leaf-2': [.30, .14, -1, 71], 'leaf-3': [.42, .13, 1, 59] }, ORDER = [1, 4, 2, 6, 3, 5];  // Design timing; [start, width, fold side, pivot y]
  function build(text) {  // Design's parts (static/shop/bloom/*_grow.svg via tools/copy_bloom_art.sh): seed, stem, leaf-1..3, bud, petal-1..6, center
    var d = text && new DOMParser().parseFromString(text, 'image/svg+xml').documentElement; box.innerHTML = ''; if (!d || d.nodeName !== 'svg') return;
    d.querySelectorAll('script,foreignObject').forEach(function (n) { n.remove(); }); [].slice.call(d.attributes).forEach(function (x) { if (/^on/i.test(x.name)) d.removeAttribute(x.name); });
    var sv = document.importNode(d, true); sv.setAttribute('viewBox', '25 10 80 92'); sv.removeAttribute('width'); sv.removeAttribute('height');  /*v34: crop to the plant so it fills ~2.5x*/ box.appendChild(sv);
    var w = document.createElementNS(NS, 'g'), w2 = document.createElementNS(NS, 'g'); w.setAttribute('class', 'fb-sw'); w2.setAttribute('class', 'fb-bob');
    [].slice.call(sv.childNodes).forEach(function (n) { if (n.nodeName !== 'defs') w2.appendChild(n); }); w.appendChild(w2); sv.appendChild(w);
    P = {}; sv.querySelectorAll('g[id]').forEach(function (n) { var pv = (n.getAttribute('data-pivot') || '60,100').split(',').map(Number); n.setAttribute('data-p', ''); n.removeAttribute('transform'); n._pv = pv; P[n.id] = n; });
  }
  var GS = window.gsap;
  function set(id, tf, op) { var n = P[id]; if (!n) return;
    if (GS) GS.killTweensOf(n); n.style.transition = ''; n.style.transformOrigin = n._pv[0] + 'px ' + n._pv[1] + 'px'; n.style.transform = tf; if (op != null) n.style.opacity = cl(op).toFixed(3); }
  function pose(t, dur) {  // t 0..1
    box.style.setProperty('--fb-dur', dur + 's');
    if (RM) t = t >= 1 ? 1 : Math.floor(t * 4) / 4;  // reduced motion: 4 calm steps, opacity crossfade only
    var s2 = t >= 1 ? 4 : Math.floor(t * 4); if (stage >= 0 && s2 > stage && !RM) { box.classList.remove('fb-settle'); void box.offsetWidth; box.classList.add('fb-settle'); } stage = s2;
    var g = cl((t - .10) / .35), h = .05 + .95 * (1 - Math.pow(1 - g, 2.2));  // stem .10-.45, ease-out
    var lift = function (y) { return 'translate(0px,' + ((1 - h) * (100 - y)).toFixed(2) + 'px) '; };  // parts ride the growing stem
    set('seed', 'scale(' + lerp(1, .6, win(t, .08, .07)).toFixed(3) + ')', lerp(1, .4, win(t, .08, .07)) * (1 - win(t, .3, .15)));
    set('stem', 'scale(1,' + h.toFixed(4) + ')', 1);
    Object.keys(LEAF).forEach(function (id) { var L = LEAF[id], u = win(t, L[0], L[1]);
      set(id, lift(L[3]) + 'rotate(' + (L[2] * lerp(35, 0, u)).toFixed(2) + 'deg) scale(' + lerp(.4, 1, u).toFixed(3) + ')', u > .01 ? 1 : 0); });
    var bs = lerp(.5, 1, win(t, .5, .12)) * (1 + .15 * win(t, .62, .10));  // bud fades in, swells, then parts
    set('bud', lift(34) + 'scale(' + bs.toFixed(3) + ')', win(t, .5, .1) * (1 - win(t, .74, .06)));
    ORDER.forEach(function (n, k) { var o = win(t, .72 + k * .03, .14);  // petals out of step, overlapping
      set('petal-' + n, lift(34) + 'rotate(' + lerp(k % 2 ? 9 : -9, 0, o).toFixed(2) + 'deg) scale(' + lerp(.15, 1, o).toFixed(3) + ')', o * 2.5); });
    set('center', lift(34) + 'scale(' + lerp(.6, 1, win(t, .9, .1)).toFixed(3) + ')', win(t, .86, .06));
  }
  function apply(t, dur) { T = t; if (!ready) { pending = [t, dur]; return; } pose(t, dur); }
  document.addEventListener('visibilitychange', function () { box.classList.toggle('fb-still', document.hidden); });
  window.addEventListener('focus:tick', function (e) {
    var d = e.detail || {}; if (d.isBreak || !d.total || d.hold) return;  // hold: early stop/finish keeps the current pose
    if (d.left <= 0) { if (done) return; done = true; box.classList.add('open'); if (GS && !RM && ready) { var o = { t: T }; GS.to(o, { t: 1, duration: 1.6, ease: 'power2.inOut', onUpdate: function () { pose(o.t, 0); } }); T = 1; return; } return apply(1, RM ? .6 : 1.2); }
    if (done && !d.running) return; done = false;  // the finished flower stays open until the next session starts
    box.classList.remove('open'); apply(cl(1 - d.left / d.total), d.running ? 1 : .3);
  });
  function start(text) { build(text); ready = true;
    if (GS && !RM) { box.classList.add('gs'); var sw = box.querySelector('.fb-sw'); GS.fromTo(sw, { rotation: -2.5, svgOrigin: '60 100' }, { rotation: 2.5, svgOrigin: '60 100', duration: 5, ease: 'sine.inOut', yoyo: true, repeat: -1 }); document.addEventListener('visibilitychange', function () { document.hidden ? GS.globalTimeline.pause() : GS.globalTimeline.resume(); }); } pose(pending ? pending[0] : T, 0); }
  fetch('/roots/data', { credentials: 'same-origin', headers: { Accept: 'application/json' } }).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.species) sp = Object.assign({}, d.species.colors || {}, d.species); leafy = sp.blooms === false || sp.bloom_color === null;
      var get = function (id) { return fetch('/static/shop/bloom/' + id + '_grow' + (dark() ? '_dark' : '') + '.svg?v=2').then(function (r) { return r.ok ? r.text() : null; }).catch(function () { return null; }); };
      return get(sid()).then(function (x) { return x || get('default'); }); })
    .then(start).catch(function () { fetch('/static/shop/bloom/default_grow' + (dark() ? '_dark' : '') + '.svg?v=2').then(function (r) { return r.text(); }).then(start, function () {}); });
})();
