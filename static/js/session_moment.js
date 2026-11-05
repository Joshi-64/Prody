// End-of-session moment (Functionality). Call prodySessionDone(courseId, minutes) after a session logs OK.
// The roots live on the dashboard, so we leave a pending leaf that grows the next time the roots render.
(function () {
  const KEY = 'prody_pending_leaves';
  window.prodySessionDone = function (courseId, minutes) {
    try {
      const q = JSON.parse(localStorage.getItem(KEY) || '[]');
      q.push({ courseId: courseId ? Number(courseId) : null, minutes: minutes, at: Date.now() });
      localStorage.setItem(KEY, JSON.stringify(q.slice(-10)));
    } catch (e) {}
    const el = document.querySelector('.roots');
    if (el && window.roots && window.roots.growLeaf && courseId) window.roots.growLeaf(el, Number(courseId));
    else { const p = document.querySelector('[data-plant3d]'); if (p && window.plant3d && window.plant3d.celebrate) window.plant3d.celebrate(p); }
  };
  // For roots.js: returns and clears queued leaves from sessions logged on other pages.
  window.prodyTakePendingLeaves = function () {
    try { const q = JSON.parse(localStorage.getItem(KEY) || '[]'); localStorage.removeItem(KEY); return q.filter(l => l.courseId); }
    catch (e) { return []; }
  };
})();
