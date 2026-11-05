/* Prody home: the clay tree, in one of two modes.
 *   clean  (default) the tree carries nothing; one soft badge floats above it when something needs you.
 *   garden           tasks grow on the tree as acorns (oak), blossoms (cherry) or cones (pine).
 * Both open the Branches view: class chips, the branch, and a calm list.
 * Reads the existing GET /api/tree; harvests through the existing task / deadline routes. No backend changes.
 * Calm rules: no red, no counters that nag, no pulsing. Motion respects prefers-reduced-motion.
 */
(function () {
  'use strict';
  var root = document.querySelector('[data-garden]');
  if (!root || !window.TreeScene) return;

  var reduced = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var stage = root.querySelector('.g-stage');
  var layer = root.querySelector('.g-items');
  var badge = root.querySelector('.g-badge');
  var summary = root.querySelector('[data-g-summary]');
  var srList = root.querySelector('.g-sr');
  var ASSETS = root.dataset.assets;
  var ITEM_PX = 84;               // element height in artwork px (~44pt on a 390pt phone)
  var DUE_SOON_DAYS = 2, GROWING_DAYS = 7;

  var SLOTS = {   // branch anchors per artwork (720x1280): even slots left, odd right, lower slot = lower
    oak:    [[185, 600], [545, 600], [145, 480], [590, 470], [215, 370], [520, 360], [300, 265], [440, 255]],
    cherry: [[175, 650], [565, 655], [145, 535], [595, 525], [215, 420], [530, 410], [300, 320], [445, 310]],
    pine:   [[185, 800], [575, 800], [215, 680], [545, 680], [250, 560], [510, 560], [290, 440], [470, 440]]
  };
  var CROWN = { oak: [552, 350], cherry: [566, 420], pine: [500, 470] };   // badge rests on the crown's upper shoulder, clear of the sky text
  var CLUSTER = [[0, 0], [-62, 30], [58, 42]];
  var PER_BRANCH = 3;
  var SPECIES_SCENE = { cherry_blossom: 'cherry', cherry: 'cherry', pine: 'pine' };
  var ELEMENT = { oak: 'acorn', cherry: 'blossom', pine: 'cone' };
  // where each sprite attaches (fraction of its height from the top): acorns and cones hang from a stem,
  // cherry buds and blossoms sit on the wood
  var PIVOT = { acorn: 0.15, cone: 0.15, blossom: 0.89 };
  // the six twig nodes on each clay branch (1200x400 render), x/y as fractions of the image
  var NODES = [[175, 243], [352, 230], [530, 227], [707, 235], [885, 247], [1062, 258]];
  var NODES_CHERRY = [[175, 125], [352, 122], [530, 129], [707, 146], [885, 168], [1062, 188]];
  var WORDS = { new: 'Just planted', growing: 'Growing', due_soon: 'Ripening', done: 'Harvested', overdue: 'Needs a little care' };
  var ORDER = ['overdue', 'due_soon', 'growing', 'new', 'done'];
  var GROUP = { overdue: 'Needs care', due_soon: 'Coming up', growing: 'Growing', new: 'Later', done: 'Harvested' };

  var scene = null, data = null, nodes = [], firstPaint = true, quietPress = false;
  var mode = 'clean';
  try { mode = localStorage.getItem('prody-home-mode') === 'garden' ? 'garden' : 'clean'; } catch (e) {}
  var forcedMode = (location.search.match(/[?&]home=(clean|garden)\b/) || [])[1];
  if (forcedMode) mode = forcedMode;

  // ---------------------------------------------------------------- helpers
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function sprite(state) { return ASSETS + 'items/' + data.element + '_' + state + '.webp'; }
  function plural(n, one, many) { return n + ' ' + (n === 1 ? one : many); }
  function day(s) { var p = (s || '').slice(0, 10).split('-'); return p.length === 3 ? Date.UTC(+p[0], p[1] - 1, +p[2]) : null; }
  function daysFrom(today, due) { var a = day(today), b = day(due); return a == null || b == null ? null : Math.round((b - a) / 864e5); }
  function stateOf(done, due, today) {
    if (done) return 'done';
    var d = daysFrom(today, due);
    if (d == null) return 'new';
    if (d < 0) return 'overdue';
    if (d <= DUE_SOON_DAYS) return 'due_soon';
    if (d <= GROWING_DAYS) return 'growing';
    return 'new';
  }
  var DOW = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function when(due, today, done) {
    if (done) return 'Done';
    var d = daysFrom(today, due); if (d == null) return 'No date';
    var t = new Date(day(due));
    if (d === -1) return 'Was due yesterday';
    if (d < -1) return 'Was due ' + DOW[t.getUTCDay()].slice(0, 3) + ', ' + MON[t.getUTCMonth()] + ' ' + t.getUTCDate();
    if (d === 0) return 'Today';
    if (d === 1) return 'Tomorrow';
    if (d < 7) return DOW[t.getUTCDay()];
    return MON[t.getUTCMonth()] + ' ' + t.getUTCDate();
  }

  // branch order: overdue first, then soonest due; finished work last, newest finished first
  var BRANCH_MAX = 6, DONE_KEEP_DAYS = 7;
  function byBranchOrder(a, c) {
    if (a.done !== c.done) return a.done ? 1 : -1;
    if (a.done) return (c.done_at || '').localeCompare(a.done_at || '');
    return ORDER.indexOf(a.state) - ORDER.indexOf(c.state) || (a.due || '9').localeCompare(c.due || '9');
  }
  // at most 6 on a branch; when anything is finished, one spot is kept for the newest finished item
  function pickShown(items) {
    var open = items.filter(function (i) { return !i.done; }), done = items.filter(function (i) { return i.done; });
    var nOpen = Math.min(open.length, done.length ? BRANCH_MAX - 1 : BRANCH_MAX);
    return open.slice(0, nOpen).concat(done.slice(0, BRANCH_MAX - nOpen));
  }

  // /api/tree -> branches with items and states (open tasks = buds, open class deadlines = roots, finished = flowers)
  function normalize(t, forced) {
    var species = t.species || null;   // the user's equipped tree wins; first task's species is only a fallback
    if (!species) (t.branches || []).some(function (b) { var x = (b.buds || [])[0] || (b.flowers || [])[0]; if (x && x.species) { species = x.species; return true; } return false; });
    var sc = forced || SPECIES_SCENE[species] || 'oak';
    var byCourse = {};
    function push(cid, it) { (byCourse[cid] = byCourse[cid] || []).push(it); }
    (t.branches || []).forEach(function (b) {
      (b.buds || []).forEach(function (x) {
        push(b.course_id, { id: 'task:' + x.task_id, kind: 'task', ref: x.task_id, title: x.title, due: x.due, done: false });
      });
      (b.flowers || []).forEach(function (f) {
        if (f.kind === 'focus' || f.status !== 'done') return;
        var ref = f.kind === 'task' ? f.task_id : (f.deadline_id || (f.id || '').split(':')[1]);
        push(b.course_id, { id: f.kind + ':' + ref, kind: f.kind, ref: ref, title: f.title || f.label, due: null, done: true, done_at: f.done_at || null });
      });
    });
    (t.roots || []).forEach(function (r) {
      if (r.kind === 'task' || !(r.deadline_id > 0)) return;          // dated tasks already arrived as buds
      push(r.course_id, { id: 'deadline:' + r.deadline_id, kind: 'deadline', ref: r.deadline_id, title: r.name, due: r.due, done: false });
    });
    // classless tasks arrive as trunk_buds / trunk_flowers: give them their own "No class" branch so Home, Branches and counts see them
    var TRUNK = 'none';
    (t.trunk_buds || []).forEach(function (x) {
      push(TRUNK, { id: 'task:' + x.task_id, kind: 'task', ref: x.task_id, title: x.title, due: x.due, done: false });
    });
    (t.trunk_flowers || []).forEach(function (f) {
      push(TRUNK, { id: 'task:' + f.task_id, kind: 'task', ref: f.task_id, title: f.title || f.label, due: null, done: true, done_at: f.done_at || null });
    });
    var srcBranches = (t.branches || []).slice();
    if (byCourse[TRUNK]) srcBranches.push({ course_id: TRUNK, name: 'No class', code: '', color: '#9aa39a', slot: srcBranches.length, class_url: null });
    var counts = { overdue: 0, due_soon: 0, growing: 0, new: 0, done: 0 };
    var branches = srcBranches.map(function (b) {
      var items = (byCourse[b.course_id] || []).filter(function (it) {
        // finished work drops off the branch 7 days after it was finished
        var age = it.done && it.done_at ? daysFrom(it.done_at, t.today) : null;
        return !(age != null && age > DONE_KEEP_DAYS);
      }).map(function (it) {
        it.state = stateOf(it.done, it.due, t.today); it.when = when(it.due, t.today, it.done); counts[it.state]++; return it;
      }).sort(byBranchOrder);
      var shown = pickShown(items);
      return { course_id: b.course_id, name: b.name, code: b.code, color: b.dot || b.color, slot: b.slot, url: b.class_url, items: items,
               shown: shown, more: items.length - shown.length,
               care: items.some(function (i) { return i.state === 'overdue'; }), soon: items.some(function (i) { return i.state === 'due_soon'; }) };
    });
    return { today: t.today, scene: sc, element: ELEMENT[sc], branches: branches, counts: counts };
  }

  function summaryLine(c) {
    var open = c.overdue + c.due_soon + c.growing + c.new;
    if (!data.branches.length) return 'Add a class and your tree grows its first branch.';
    if (!open) return 'All quiet on your tree.';
    var parts = [];
    if (c.overdue) parts.push(plural(c.overdue, 'needs care', 'need care'));
    if (c.due_soon) parts.push(c.due_soon + ' coming up');
    if (!parts.length) parts.push(plural(open, 'thing', 'things') + ' growing');
    return parts.join(' · ');
  }

  // ---------------------------------------------------------------- tree: badge (clean) or elements (garden)
  function size() { return Math.round(ITEM_PX * scene.pxPerImagePx()); }
  var badgeY = 0;
  function place() {
    if (!scene || !data) return;
    var s = size(), W = stage.clientWidth;
    root.style.setProperty('--g-el', s + 'px');
    nodes.forEach(function (n) {
      var p = scene.toScreen(n.ix, n.iy);
      p[0] = Math.max(s * 0.7, Math.min(W - s * 0.7, p[0]));
      var top = n.it ? p[1] - s * PIVOT[data.element] : p[1];
      n.node.style.transform = 'translate(' + (p[0] - s / 2).toFixed(1) + 'px,' + top.toFixed(1) + 'px)';
    });
    if (!badge.hidden) {
      var c = scene.toScreen.apply(null, CROWN[data.scene]);
      badgeY = c[1] - badge.offsetHeight / 2;
      badge.style.transform = 'translate(' + (c[0] - badge.offsetWidth / 2).toFixed(1) + 'px,' + badgeY.toFixed(1) + 'px)';
    }
  }

  function buildGarden() {
    layer.textContent = ''; nodes = [];
    if (mode !== 'garden') return;
    var slots = SLOTS[data.scene], delay = 0;
    data.branches.forEach(function (b) {
      var a = slots[b.slot] || slots[0], dir = b.slot % 2 === 0 ? 1 : -1;
      // open work first; finished work fills spare spots so the tree shows what you've grown
      b.items.slice(0, PER_BRANCH).forEach(function (it, i) {
        var o = CLUSTER[i], n = elementNode(it, b);
        nodes.push({ node: n, ix: a[0] + o[0] * dir, iy: a[1] + o[1], it: it, br: b });
        layer.appendChild(n);
        if (firstPaint && !reduced) { n.style.setProperty('--d', (delay += 70) + 'ms'); n.classList.add('g-appear'); }
      });
      var more = b.items.length - Math.min(PER_BRANCH, b.items.length);
      if (more > 0) {
        var bundle = el('button', 'g-bundle'); bundle.type = 'button';
        bundle.setAttribute('aria-label', plural(more, 'more task', 'more tasks') + ' on ' + b.name);
        bundle.appendChild(el('span', 'g-bundle-dots')); bundle.appendChild(el('span', 'g-bundle-n', '+' + more));
        bundle.addEventListener('click', function () { openBranches(b.course_id); });
        nodes.push({ node: bundle, ix: a[0] - 4 * dir, iy: a[1] + 96, br: b });
        layer.appendChild(bundle);
      }
    });
    firstPaint = false;
  }

  function elementNode(it, b) {
    var n = el('button', 'g-el g-' + it.state); n.type = 'button';
    n.setAttribute('aria-label', it.title + ', ' + b.name + ', ' + it.when + ', ' + WORDS[it.state]);
    n.dataset.gid = it.id; n.dataset.lbl = it.title + ', ' + b.name;
    var sway = el('span', 'g-sway');
    sway.style.setProperty('--sw', (3.6 + Math.random() * 2.2).toFixed(2) + 's');
    sway.style.setProperty('--sd', (-Math.random() * 4).toFixed(2) + 's');
    var img = el('img'); img.src = sprite(it.state); img.alt = ''; img.decoding = 'async'; img.draggable = false;
    sway.appendChild(img); n.appendChild(sway);
    n.addEventListener('click', function (e) { e.stopPropagation(); openItem(it, b, n); });
    return n;
  }

  // one badge, one meaning, hidden at zero: care (overdue) wins over coming up
  function buildBadge() {
    var c = data.counts, kind = c.overdue ? 'overdue' : c.due_soon ? 'due_soon' : null;
    if (mode === 'garden' || !kind) { badge.hidden = true; return; }
    var n = c[kind];
    badge.className = 'g-badge g-badge-' + kind;
    badge.querySelector('img').src = sprite(kind);
    badge.querySelector('.g-badge-n').textContent = n > 1 ? n : '';
    badge.setAttribute('aria-label', (kind === 'overdue' ? plural(n, 'task needs care', 'tasks need care') : plural(n, 'task coming up', 'tasks coming up')) + '. Open Branches');
    badge.hidden = false;
    var target = data.branches.filter(function (b) { return kind === 'overdue' ? b.care : b.soon; })[0];
    badge.onclick = function () { openBranches(target && target.course_id); };
  }

  function buildSr() {
    srList.textContent = '';
    data.branches.forEach(function (b) {
      b.items.forEach(function (it) {
        var li = el('li'), btn = el('button', null, it.title + ', ' + b.name + ', ' + it.when + ', ' + WORDS[it.state]);
        btn.type = 'button'; btn.addEventListener('click', function () { openItem(it, b, null); });
        li.appendChild(btn); srList.appendChild(li);
      });
    });
  }

  function follow() {          // elements and badge ride the squash
    if (scene) {
      var s = scene.squash();
      if (Math.abs(s) > 0.001) {
        var a = scene.toScreen.apply(null, scene.anchor());
        layer.style.transformOrigin = a[0].toFixed(1) + 'px ' + a[1].toFixed(1) + 'px';
        layer.style.transform = 'scale(' + (1 + 0.028 * s).toFixed(4) + ',' + (1 - 0.05 * s).toFixed(4) + ')';
        badge.style.marginTop = (s * 0.05 * (a[1] - badgeY)).toFixed(1) + 'px';
      } else if (layer.style.transform) { layer.style.transform = ''; badge.style.marginTop = ''; }
    }
    requestAnimationFrame(follow);
  }

  // ---------------------------------------------------------------- sheet (item card, Today)
  var sheet = document.querySelector('[data-g-sheet]'), sheetBody = sheet.querySelector('.g-sheet-body'), lastFocus = null;
  function openSheet(fill) {
    lastFocus = document.activeElement; sheetBody.textContent = ''; fill(sheetBody); sheet.hidden = false;
    requestAnimationFrame(function () { sheet.classList.add('on'); });
    var f = sheet.querySelector('.g-sheet-body button, .g-sheet-body a'); if (f) f.focus({ preventScroll: true });
  }
  function closeSheet() {
    sheet.classList.remove('on');
    setTimeout(function () { sheet.hidden = true; }, reduced ? 0 : 320);
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  window.prodyOpenSheet = openSheet;
  sheet.addEventListener('click', function (e) { if (e.target === sheet) closeSheet(); });
  sheet.querySelector('[data-g-close]').addEventListener('click', closeSheet);
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (!sheet.hidden) closeSheet(); else if (!view.hidden) closeBranches(false);
  });
  (function () {   // swipe down to dismiss
    var card = sheet.querySelector('.g-sheet-card'), y0 = null, dy = 0;
    card.addEventListener('touchstart', function (e) { if (card.scrollTop <= 0) { y0 = e.touches[0].clientY; dy = 0; } }, { passive: true });
    card.addEventListener('touchmove', function (e) { if (y0 == null) return; dy = Math.max(0, e.touches[0].clientY - y0); card.style.transform = 'translateY(' + dy + 'px)'; }, { passive: true });
    card.addEventListener('touchend', function () { if (y0 == null) return; card.style.transform = ''; y0 = null; if (dy > 90) closeSheet(); });
  })();

  function itemCard(box, it, br) {
    var head = el('div', 'g-card-head');
    var pic = el('img', 'g-card-pic'); pic.src = sprite(it.state); pic.alt = '';
    var tx = el('div', 'g-card-tx');
    tx.appendChild(el('div', 'g-card-state g-s-' + it.state, WORDS[it.state]));
    tx.appendChild(el('h2', 'g-card-title', it.title));
    var meta = el('div', 'g-card-meta'), dot = el('span', 'g-dot'); dot.style.background = br.color;
    meta.appendChild(dot); meta.appendChild(document.createTextNode(br.name + ' · ' + it.when)); tx.appendChild(meta);
    head.appendChild(pic); head.appendChild(tx); box.appendChild(head);
    if (it.state === 'overdue') box.appendChild(el('p', 'g-card-note', 'It’s okay. Finish it when you can, or give it a new date in To-Do.'));
    var acts = el('div', 'g-card-acts');
    if (!it.done) {
      var h = el('button', 'g-btn g-btn-main', 'Harvest'); h.type = 'button';
      h.addEventListener('click', function () { harvest(it); }); acts.appendChild(h);
    }
    var e = el('a', 'g-btn', it.kind === 'task' ? 'Open in To-Do' : 'Open class');
    e.href = it.kind === 'task' ? root.dataset.tasksUrl : (br.url || root.dataset.classesUrl); acts.appendChild(e);
    box.appendChild(acts);
  }
  function openItem(it, br, node) {
    if (node && !reduced) { node.classList.remove('g-nudge'); void node.offsetWidth; node.classList.add('g-nudge'); }
    openSheet(function (box) { itemCard(box, it, br); });
  }

  // ---------------------------------------------------------------- Branches view
  // Opening is a short cutscene on every tap: the tree gives under your finger, the camera pushes into the
  // canopy (a cross-fade to a pre-blurred copy of the same art makes it read as a focus pull), a few leaves rush
  // past, then the class's branch grows in from the left and its work sprouts from the nodes as the growth reaches
  // them. Switching classes keeps the branch: only what grows on it changes. Everything animates transform and
  // opacity only, so it stays on the compositor on an iPhone; reduced motion gets a plain cross-fade.
  var view = document.querySelector('[data-g-branches]');
  var hero = view.querySelector('.g-hero'), chips = view.querySelector('.g-chips'), twig = view.querySelector('.g-twig');
  var twigBody = view.querySelector('.g-twig-body'), nodesEl = view.querySelector('.g-nodes'), list = view.querySelector('.g-list');
  var meta = view.querySelector('.g-meta'), harvested = view.querySelector('.g-harvested');
  var grows = view.querySelectorAll('.g-grow'), blur = root.querySelector('.g-blur'), fly = root.querySelector('.g-fly');
  var html = document.documentElement;
  // where items attach on the clay branch (Blender export, fractions of the 1170x1080 render); ang = branch slope
  var HANG_NODES = [[.0934, .4508, -3.6], [.2065, .4699, -25.1], [.3496, .5331, -27], [.4958, .582, -14.1], [.6442, .5662, 17.8], [.7557, .5017, 26.5]];
  var SIT_NODES = [[.1153, .36, -10.9], [.2506, .4137, -15.5], [.3766, .4677, -15.2], [.5064, .5052, -5], [.6218, .5093, 11.5], [.7394, .4834, 17.7]];
  var CANOPY = { oak: [360, 400], cherry: [360, 420], pine: [360, 520] };   // artwork px the camera aims for
  var PUSH = 'cubic-bezier(.66,0,.24,1)', OUT = 'cubic-bezier(.22,.8,.24,1)', GROW = 'cubic-bezier(.3,.05,.18,1)';
  var current = null, busy = false, dive = null, artFor = null;
  // cutscene plays on every open (no one-time seen flag); reverse on back at ~70% forward duration
  var cutTimer = 0, cutSkip = null, cutDir = 0;   // cutDir: 1 opening, -1 closing, 0 idle
  function clearCutHooks() {
    clearTimeout(cutTimer); cutTimer = 0;
    if (cutSkip) {
      view.removeEventListener('pointerdown', cutSkip, true);
      stage.removeEventListener('pointerdown', cutSkip, true);
      cutSkip = null;
    }
  }
  function finishFinite(nodes) {
    (nodes || []).forEach(function (n) {
      if (!n || !n.getAnimations) return;
      n.getAnimations({ subtree: true }).forEach(function (a) {
        try { if (isFinite(a.effect.getComputedTiming().endTime)) a.finish(); } catch (e) {}
      });
    });
  }
  function cancelFinite(nodes) {
    (nodes || []).forEach(function (n) {
      if (!n || !n.getAnimations) return;
      n.getAnimations({ subtree: true }).forEach(function (a) {
        try { if (isFinite(a.effect.getComputedTiming().endTime)) a.cancel(); } catch (e) {}
      });
    });
  }

  function play(node, frames, opt) { return node && node.animate ? node.animate(frames, opt) : null; }
  function stopAll(node) { if (node && node.getAnimations) node.getAnimations().forEach(function (x) { x.cancel(); }); }
  // branch art and the fly-through sprite load (and decode) as soon as we know the tree, so the first open is instant
  function setArt() {
    if (artFor === data.scene) return; artFor = data.scene;
    view.dataset.scene = data.scene;
    var arts = view.querySelectorAll('.g-twig-art');
    arts[0].src = ASSETS + 'branch/' + data.scene + '_wood.webp';
    arts[1].src = ASSETS + 'branch/' + data.scene + '_leaf.webp';
    if (data.scene !== 'pine') { var f = new Image(); f.src = flySrc(); if (f.decode) f.decode().catch(function () {}); }
  }
  function flySrc() { return ASSETS + 'branch/fly_' + (data.scene === 'cherry' ? 'cherry' : 'oak') + '.webp'; }
  function pick(courseId) {
    return data.branches.filter(function (x) { return x.course_id === courseId; })[0] ||
           data.branches.filter(function (x) { return x.care; })[0] || data.branches[0];
  }

  function openBranches(courseId, fromPop, origin) {
    // second tap during the zoom-in cutscene skips straight to the branch end state
    if (busy && cutDir === 1 && cutSkip) { cutSkip(); return; }
    if (!data || !data.branches.length || busy || !view.hidden) return;
    clearCutHooks(); cutDir = 1;
    current = pick(courseId).course_id;
    setArt(); drawBranches();
    if (!fromPop && location.hash !== '#branches') history.pushState({ branches: current }, '', '#branches');
    else if (!fromPop && location.hash === '#branches') history.replaceState({ branches: current }, '', '#branches');
    var on = chips.querySelector('.g-chip[aria-pressed="true"]');
    if (on && on.scrollIntoView) on.scrollIntoView({ inline: 'center', block: 'nearest' });
    view.scrollTop = 0;
    if (reduced || !blur.animate) {
      busy = true;
      blur.style.opacity = 1; html.classList.add('g-diving', 'g-branches-open'); view.hidden = false;
      var fo = view.animate ? view.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 180, easing: 'linear' }) : null;
      function doneRm() { busy = false; cutDir = 0; view.querySelector('.g-bh-title').focus({ preventScroll: true }); }
      if (fo) { fo.onfinish = doneRm; fo.oncancel = doneRm; } else doneRm();
      return;
    }
    busy = true;
    var t = diveIn(origin);
    view.hidden = false; html.classList.add('g-branches-open');
    [view.querySelector('.g-bh'), chips].forEach(function (n) {
      play(n, [{ opacity: 0, transform: 'translateY(-8px)' }, { opacity: 1, transform: 'none' }], { duration: 340, delay: t.ui, easing: OUT, fill: 'backwards' });
    });
    play(list, [{ transform: 'translateY(62vh)' }, { transform: 'none' }], { duration: 560, delay: t.ui, easing: OUT, fill: 'backwards' });
    play(meta, [{ opacity: 0 }, { opacity: 1 }], { duration: 300, delay: t.grow + 520, fill: 'backwards' });
    growBranch(t.grow);
    var done = false;
    function finish() {
      if (done || cutDir !== 1) return; done = true; clearCutHooks();
      busy = false; cutDir = 0; view.querySelector('.g-bh-title').focus({ preventScroll: true });
    }
    cutSkip = function () {
      if (cutDir !== 1) return;
      // cancel in-flight, then finish so transform lands on the end keyframe
      cancelFinite([view, stage, blur, fly]);
      finishFinite([view, stage, blur, fly]);
      if (dive && dive.to) {
        [stage, blur].forEach(function (n) {
          if (!n) return;
          stopAll(n);
          n.style.transform = dive.to;
        });
        blur.style.opacity = 1;
      }
      if (scene && scene.sleep) scene.sleep(true);
      fly.textContent = ''; finish();
    };
    view.addEventListener('pointerdown', cutSkip, true);
    stage.addEventListener('pointerdown', cutSkip, true);  // second tap on the tree also skips
    cutTimer = setTimeout(finish, t.grow + 900);
  }

  // camera push: the live scene and its blurred twin scale together about the canopy point, the twin fades up
  function diveIn(origin) {
    var fr = stage.getBoundingClientRect(), vr = view.getBoundingClientRect();
    var c = scene ? scene.toScreen.apply(null, CANOPY[data.scene]) : [fr.width / 2, fr.height * 0.4];
    var p = origin ? [(origin[0] + c[0]) / 2, (origin[1] + c[1]) / 2] : c;
    var k = 2.5, twigH = twig.offsetHeight || fr.width;
    var target = [vr.left + vr.width / 2 - fr.left, vr.top + twigH * 0.52 - fr.top];
    var to = 'translate(' + (target[0] - p[0] * k).toFixed(1) + 'px,' + (target[1] - p[1] * k).toFixed(1) + 'px) scale(' + k + ')';
    dive = { to: to };
    html.classList.add('g-diving');
    [stage, blur].forEach(function (n) { stopAll(n); play(n, [{ transform: 'none' }, { transform: to }], { duration: 720, delay: 120, easing: PUSH, fill: 'forwards' }); });
    play(blur, [{ opacity: 0 }, { opacity: 1 }], { duration: 420, delay: 300, easing: 'linear', fill: 'forwards' });
    rushLeaves(p);
    var mine = dive;   // only sleep the scene if this same visit is still open when the camera lands
    setTimeout(function () { if (dive === mine && !mine.closing && scene && scene.sleep) scene.sleep(true); }, 900);
    return { ui: 480, grow: 560 };
  }

  // a handful of leaves (or petals) rush past the camera on the way in; pines stay still, their needles don't fly
  function rushLeaves(p) {
    if (data.scene === 'pine') return;   // pine has no flying leaves (no request) until its own art is cleared
    fly.textContent = '';
    var src = flySrc();
    for (var i = 0; i < 5; i++) {
      var im = el('img'); im.src = src; im.alt = ''; fly.appendChild(im);
      // they start just in front of the canopy and swell past the lens, so they read as foreground, not texture
      var a = -Math.PI / 2 + (i - 2) * 1.05 + (Math.random() - 0.5) * 0.5, d = 300 + Math.random() * 200, r0 = Math.random() * 360;
      var x0 = p[0] + Math.cos(a) * 40 - 28, y0 = p[1] + Math.sin(a) * 30 - 20, sc = 1.1 + Math.random() * 0.5;
      play(im, [
        { transform: 'translate(' + x0 + 'px,' + y0 + 'px) rotate(' + r0 + 'deg) scale(' + sc.toFixed(2) + ')', opacity: 0 },
        { opacity: 1, offset: 0.14 }, { opacity: 1, offset: 0.72 },
        { transform: 'translate(' + (x0 + Math.cos(a) * d) + 'px,' + (y0 + Math.sin(a) * d * 0.7 + 140) + 'px) rotate(' + (r0 + 140 * (i % 2 ? 1 : -1)) + 'deg) scale(' + (sc * 4.4).toFixed(2) + ')', opacity: 0 }
      ], { duration: 640 + Math.random() * 140, delay: 160 + i * 55, easing: 'cubic-bezier(.42,0,.8,.65)', fill: 'both' });
    }
    setTimeout(function () { fly.textContent = ''; }, 1300);
  }

  // the branch grows from the trunk side: a clip window slides right while the art inside slides back left,
  // so the art stays put and only its visible edge (feathered) travels. Leaves follow a beat later.
  function growBranch(delay) {
    var w = twig.offsetWidth + 64;
    Array.prototype.forEach.call(grows, function (g, i) {
      var d = delay + (i ? 170 : 0), dur = i ? 600 : 640;
      play(g, [{ transform: 'translateX(' + -w + 'px)' }, { transform: 'none' }], { duration: dur, delay: d, easing: GROW, fill: 'backwards' });
      play(g.firstElementChild, [{ transform: 'translateX(' + w + 'px)' }, { transform: 'none' }], { duration: dur, delay: d, easing: GROW, fill: 'backwards' });
      if (i) play(g, [{ opacity: 0.2 }, { opacity: 1 }], { duration: dur, delay: d, fill: 'backwards' });
    });
    // it springs into place as it finishes reaching out
    play(twigBody, [{ transform: 'rotate(-2.4deg)' }, { transform: 'rotate(.7deg)', offset: 0.72 }, { transform: 'rotate(-.2deg)', offset: 0.88 }, { transform: 'none' }],
         { duration: 1150, delay: delay, easing: 'ease-out', fill: 'backwards' });
    Array.prototype.forEach.call(nodesEl.children, function (n) {
      sprout(n, delay + 90 + parseFloat(n.dataset.x) * 560);
    });
  }

  function sprout(n, delay) {
    var hang = data.element !== 'blossom';
    var frames = hang
      ? [{ transform: 'scale(.15)', opacity: 0 }, { transform: 'scale(1.06) rotate(10deg)', opacity: 1, offset: 0.42 },
         { transform: 'scale(.98) rotate(-6deg)', offset: 0.64 }, { transform: 'rotate(2.5deg)', offset: 0.82 }, { transform: 'none' }]
      : [{ transform: 'scale(.05) rotate(-14deg)', opacity: 0 }, { transform: 'scale(1.12) rotate(3deg)', opacity: 1, offset: 0.5 },
         { transform: 'scale(.96) rotate(-1deg)', offset: 0.72 }, { transform: 'none' }];
    play(n.firstElementChild, frames, { duration: hang ? 780 : 640, delay: delay, easing: 'ease-out', fill: 'backwards' });
  }

  function closeBranches(fromPop) {
    if (view.hidden && cutDir !== 1) return;
    if (!fromPop && location.hash === '#branches') { history.back(); return; }   // popstate brings us back here
    // abort any in-flight open cutscene, then reverse (or fade) out
    clearCutHooks(); cancelFinite([view, stage, blur, fly]); fly.textContent = '';
    cutDir = -1; busy = true;
    html.classList.remove('g-branches-open');
    if (scene && scene.sleep) scene.sleep(false);
    if (reduced || !dive || !blur.animate) {
      var doneRm = function () {
        view.hidden = true; blur.style.opacity = ''; [stage, blur].forEach(stopAll);
        html.classList.remove('g-diving'); dive = null; busy = false; cutDir = 0;
      };
      if (reduced && view.animate) {
        var fo = view.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 180, easing: 'linear' });
        fo.onfinish = doneRm; fo.oncancel = doneRm; return;
      }
      doneRm(); return;
    }
    dive.closing = true;
    // reverse ≈ 70% of forward: camera 720→504, blur 420→294, UI sheet 560→392, fades 200→140
    var cam = Math.round(720 * 0.7), camDelay = Math.round(120 * 0.7);
    var blurOut = Math.round(420 * 0.7), blurDelay = Math.round(300 * 0.7);
    var sheet = Math.round(560 * 0.7), fade = Math.round(200 * 0.7);
    var total = camDelay + cam + 40;
    play(list, [{ transform: 'none' }, { transform: 'translateY(70vh)' }], { duration: sheet, easing: 'cubic-bezier(.5,0,.75,0)', fill: 'forwards' });
    [view.querySelector('.g-bh'), chips, twig, meta].forEach(function (n) {
      play(n, [{ opacity: 1 }, { opacity: 0 }], { duration: fade, easing: 'ease-in', fill: 'forwards' });
    });
    var to = dive.to;
    [stage, blur].forEach(function (n) {
      stopAll(n); play(n, [{ transform: to }, { transform: 'none' }], { duration: cam, delay: camDelay, easing: PUSH, fill: 'both' });
    });
    play(blur, [{ opacity: 1 }, { opacity: 0 }], { duration: blurOut, delay: blurDelay, easing: 'linear', fill: 'both' });
    var done = false;
    function finishClose() {
      if (done || cutDir !== -1) return; done = true; clearCutHooks();
      html.classList.remove('g-diving');
      view.hidden = true; [list, view.querySelector('.g-bh'), chips, twig, meta, stage, blur].forEach(stopAll);
      blur.style.opacity = ''; dive = null; busy = false; cutDir = 0;
    }
    cutSkip = function () {
      if (cutDir !== -1) return;
      finishFinite([view, stage, blur, fly]); finishClose();
    };
    view.addEventListener('pointerdown', cutSkip, true);
    stage.addEventListener('pointerdown', cutSkip, true);  // skip while zooming out onto the tree
    cutTimer = setTimeout(finishClose, total);
  }
  view.querySelector('.g-back').addEventListener('click', function () { closeBranches(false); });
  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.branches) {
      if (view.hidden && !busy) openBranches(e.state.branches, true);
    } else {
      closeBranches(true);
    }
  });
  window.addEventListener('resize', function () {
    if (!dive) return;     // keep the backdrop locked to the new size without replaying anything
    [stage, blur].forEach(stopAll); dive = null; blur.style.opacity = view.hidden ? '' : 1;
  });
  window.prodyOpenBranches = function () { openBranches(null); };

  // switching classes: what's on the branch goes back into the wood, the branch nods, the new work sprouts
  function switchTo(id) {
    if (id === current || busy) return;
    if (reduced || !nodesEl.animate) { current = id; drawBranches(); return; }
    busy = true;
    var old = Array.prototype.slice.call(nodesEl.children), gap = 0;
    old.forEach(function (n, i) {
      gap = (old.length - 1 - i) * 30;
      play(n.firstElementChild, [{ opacity: 1 }, { opacity: 0 }], { duration: 200, delay: gap, easing: 'ease-in', fill: 'forwards' });
    });   // the wood stays put and visible; only the items trade places
    // the paper stays put; only the words on it trade places
    Array.prototype.slice.call(list.children).concat(meta).forEach(function (n) { play(n, [{ opacity: 1 }, { opacity: 0, transform: 'translateY(6px)' }], { duration: 160, easing: 'ease-in', fill: 'forwards' }); });
    var wait = old.length ? 200 + old.length * 30 : 160;
    current = id; drawChips();
    setTimeout(function () {
      stopAll(meta);
      drawBranch(); drawList();
      Array.prototype.forEach.call(nodesEl.children, function (n, i) { play(n.firstElementChild, [{ opacity: 0 }, { opacity: 1 }], { duration: 260, delay: 40 + i * 50, easing: 'ease-out', fill: 'backwards' }); });
      play(meta, [{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: OUT });
      Array.prototype.forEach.call(list.querySelectorAll('.g-group'), function (g, i) {
        play(g, [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }], { duration: 320, delay: 60 + i * 50, easing: OUT, fill: 'backwards' });
      });
      setTimeout(function () { busy = false; }, 300);
    }, wait);
  }

  function drawBranches() { drawChips(); drawBranch(); drawList(); }
  function drawChips() {
    chips.textContent = '';
    data.branches.forEach(function (b) {
      var c = el('button', 'g-chip'); c.type = 'button'; c.setAttribute('aria-pressed', b.course_id === current ? 'true' : 'false');
      var dot = el('span', 'g-dot'); dot.style.background = b.color; c.appendChild(dot);
      c.appendChild(el('span', 'g-chip-t', b.code || b.name));
      if (b.care || b.soon) {
        var m = el('span', 'g-chip-mark ' + (b.care ? 'is-care' : 'is-soon'));
        m.setAttribute('role', 'img'); m.setAttribute('aria-label', b.care ? 'needs care' : 'something coming up'); c.appendChild(m);
      }
      c.addEventListener('click', function () { switchTo(b.course_id); });
      chips.appendChild(c);
    });
  }
  function currentBranch() { return data.branches.filter(function (x) { return x.course_id === current; })[0] || data.branches[0]; }
  // open work grows nearest the trunk, most urgent first; finished work after it
  function drawBranch() {
    var b = currentBranch();
    view.querySelector('.g-branch-name').textContent = b.name;
    var done = b.items.filter(function (i) { return i.done; }).length;
    harvested.textContent = b.items.length ? done + '/' + b.items.length + ' harvested' : '';
    nodesEl.textContent = '';
    twig.dataset.element = data.element;
    var open = b.items.filter(function (i) { return !i.done; }), fin = b.items.filter(function (i) { return i.done; });
    var shown = b.shown || open.concat(fin).slice(0, 6), at = data.element === 'blossom' ? SIT_NODES : HANG_NODES;
    shown.forEach(function (it, i) {
      var p = at[i], n = el('button', 'g-node g-' + it.state); n.type = 'button';
      n.style.left = (p[0] * 100) + '%'; n.style.top = (p[1] * 100) + '%'; n.dataset.x = p[0];
      if (data.element === 'blossom') n.style.transform = 'translate(-50%,-89%) rotate(' + (-p[2] * 0.55).toFixed(1) + 'deg)';
      n.style.transformOrigin = data.element === 'blossom' ? '50% 89%' : '50% 15%';
      n.setAttribute('aria-label', it.title + ', ' + it.when + ', ' + WORDS[it.state]);
      n.dataset.gid = it.id; n.dataset.lbl = it.title;
      var sp = el('span', 'g-sprout'), im = el('img'); im.src = sprite(it.state); im.alt = ''; im.draggable = false;
      sp.appendChild(im); n.appendChild(sp);
      n.addEventListener('click', function () { openItem(it, b, null); });
      nodesEl.appendChild(n);
    });
    if (b.more > 0) {   // "+N" opens the full list
      var more = el('button', 'g-twig-more', '+' + b.more); more.type = 'button';
      more.setAttribute('aria-label', 'Show all ' + b.items.length + ' on ' + b.name);
      more.addEventListener('click', function () {
        list.querySelectorAll('details').forEach(function (d) { d.open = true; });
        list.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' });
      });
      nodesEl.appendChild(more);
    }
  }
  // the list: needs care first, then by time; later and finished work folded away
  function drawList() {
    var b = currentBranch();
    list.textContent = '';
    if (!b.items.length) { list.appendChild(el('p', 'g-quiet', 'Nothing on this branch yet. Add a task in To-Do and it grows here.')); return; }
    ORDER.forEach(function (st) {
      var items = b.items.filter(function (i) { return i.state === st; }); if (!items.length) return;
      var g;
      if (st === 'done' || st === 'new') { g = el('details', 'g-group'); g.appendChild(el('summary', 'g-group-h', GROUP[st] + ' · ' + items.length)); }
      else { g = el('section', 'g-group'); g.appendChild(el('h3', 'g-group-h', GROUP[st])); }
      var ul = el('ul', 'g-rows');
      items.forEach(function (it) {
        var li = el('li'), row = el('button', 'g-row'); row.type = 'button';
        var im = el('img'); im.src = sprite(it.state); im.alt = '';
        row.appendChild(im); row.appendChild(el('span', 'g-row-t', it.title)); row.appendChild(el('span', 'g-row-w', it.when));
        row.addEventListener('click', function () { openItem(it, b, null); });
        li.appendChild(row); ul.appendChild(li);
      });
      g.appendChild(ul); list.appendChild(g);
    });
  }

  // ---------------------------------------------------------------- actions (existing routes)
  // explicit state, never a toggle: repeating Harvest or Undo is harmless
  function setDone(it, done) {
    var url = it.kind === 'task' ? '/tasks/done/' + it.ref : '/api/deadlines/' + it.ref + '/done';
    return fetch(url, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ done: done }) })
      .then(function (r) { if (!r.ok) throw new Error(r.status); });
  }
  // flip one item's state + every label/sprite that shows it, right away (refresh() catches up later)
  function markItem(it, done) {
    it.done = done; it.done_at = done ? new Date().toISOString() : null;
    it.state = stateOf(done, it.due, data && data.today); it.when = when(it.due, data && data.today, done);
    document.querySelectorAll('[data-gid]').forEach(function (n) {
      if (n.dataset.gid !== String(it.id)) return;
      n.className = n.className.replace(/\bg-(new|growing|due_soon|done|overdue)\b/, 'g-' + it.state);
      n.setAttribute('aria-label', n.dataset.lbl + ', ' + it.when + ', ' + WORDS[it.state]);
      var im = n.querySelector('img'); if (im) im.src = sprite(it.state);
    });
  }
  function undo(it) {
    setDone(it, false).then(function () { markItem(it, false); }).then(refresh).then(function () { toast('Back on your branch.'); })
      .catch(function () { toast('That didn’t save. Check your connection and try again.'); });
  }
  function harvest(it) {
    var req = setDone(it, true);
    var n = nodes.filter(function (x) { return x.it && x.it.id === it.id; })[0];
    closeSheet();
    req.then(function () {
      markItem(it, true);
      if (n && !reduced) {
        n.node.querySelector('img').src = sprite('done'); n.node.classList.add('g-ripen');
        setTimeout(function () {
          var a = scene.toScreen.apply(null, scene.anchor()), cur = n.node.getBoundingClientRect(), box = stage.getBoundingClientRect();
          var dx = a[0] - (cur.left - box.left) - cur.width / 2 + (Math.random() * 60 - 30), dy = a[1] - (cur.top - box.top) - cur.height;
          n.node.animate([
            { transform: n.node.style.transform, opacity: 1 },
            { transform: n.node.style.transform + ' translate(' + dx * 0.5 + 'px,' + dy * 0.35 + 'px) rotate(25deg)', opacity: 1, offset: 0.5 },
            { transform: n.node.style.transform + ' translate(' + dx + 'px,' + dy + 'px) rotate(70deg)', opacity: 0 }
          ], { duration: 900, easing: 'cubic-bezier(.45,0,.75,.6)', fill: 'forwards' });
          quietPress = true; scene.press(); setTimeout(function () { quietPress = false; }, 600);
        }, 520);
        setTimeout(refresh, 1500);
      } else { refresh(); }
      toast('Harvested. Nice work.', { label: 'Undo', run: function () { undo(it); } }, 5000);
    }).catch(function () { toast('That didn’t save. Check your connection and try again.'); });
  }

  var toastEl = root.querySelector('.g-toast'), toastT = 0;
  // lift the toast out of the scene's stacking context so it sits above the Branches overlay (z 70) and the sheet (z 80)
  if (toastEl && toastEl.parentNode !== document.body) document.body.appendChild(toastEl);
  function toast(msg, action, ms) {
    toastEl.textContent = msg; toastEl.hidden = false;
    if (action) {
      var b = el('button', 'g-toast-act', action.label); b.type = 'button';
      b.addEventListener('click', function () { clearTimeout(toastT); toastEl.classList.remove('on'); toastEl.hidden = true; action.run(); }, { once: true });
      toastEl.appendChild(b);
    } requestAnimationFrame(function () { toastEl.classList.add('on'); });
    clearTimeout(toastT); toastT = setTimeout(function () { toastEl.classList.remove('on'); setTimeout(function () { toastEl.hidden = true; }, 300); }, ms || 2400);
  }

  // ---------------------------------------------------------------- mode switch (lives in the Today sheet)
  window.prodyHomeMode = function (m) {
    if (m) {
      mode = m === 'garden' ? 'garden' : 'clean';
      try { localStorage.setItem('prody-home-mode', mode); } catch (e) {}
      root.dataset.mode = mode; if (data) { buildGarden(); buildBadge(); place(); }
    }
    return mode;
  };

  // ---------------------------------------------------------------- data + boot
  var forced = (location.search.match(/[?&]scene=(oak|cherry|pine)\b/) || [])[1] || null;
  function render(t) {
    data = normalize(t, forced);
    summary.textContent = summaryLine(data.counts);
    root.dataset.mode = mode;
    buildGarden(); buildBadge(); buildSr(); place(); setArt();
    if (!view.hidden && !busy) drawBranches();
  }
  function refresh() {
    return fetch('/api/tree', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(render)
      .catch(function () { summary.textContent = 'Your tree is resting. Refresh in a moment.'; });
  }
  var first = window.__gardenP ? window.__gardenP.then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }) : Promise.reject();
  first.catch(function () { return fetch('/api/tree', { credentials: 'same-origin' }).then(function (r) { return r.json(); }); })
    .then(function (t) {
      var pre = normalize(t, forced);
      root.dataset.scene = pre.scene;
      scene = TreeScene.mount(stage, { scene: pre.scene, assets: ASSETS + 'scenes/', fit: 'cover', focus: [0.5, 0.47],
                                       label: 'Your tree. Press it to open your branches.' });
      stage.addEventListener('treelayout', place);
      stage.addEventListener('treepress', function (e) {
        if (quietPress || !data || !data.branches.length) return;
        var pt = e.detail && e.detail.x != null ? scene.toScreen(e.detail.x, e.detail.y) : null;
        setTimeout(function () { openBranches(null, false, pt); }, reduced ? 0 : 140);
      });
      scene.ready.then(function () {
        root.classList.add('g-ready'); render(t); requestAnimationFrame(follow);
        setTimeout(function () { root.classList.add('g-settled'); }, reduced ? 0 : 4200);
        if (location.hash === '#branches') history.replaceState(null, '', location.pathname + location.search);
      });
    }).catch(function () { summary.textContent = 'Your tree is resting. Refresh in a moment.'; });
  document.addEventListener('visibilitychange', function () { if (!document.hidden && data) refresh(); });
})();
