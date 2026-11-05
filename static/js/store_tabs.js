/* Store tabs: tap a .shop-tabs button to scroll its .shop-panel into view; swiping updates the active tab. */
(function () {
  var tabs = document.querySelector('.shop-tabs'), wrap = document.querySelector('.shop-panels');
  if (!tabs || !wrap) return;
  var btns = [].slice.call(tabs.querySelectorAll('[data-tab]'));
  var panels = [].slice.call(wrap.querySelectorAll('.shop-panel[data-tab]'));
  function mark(id) {
    btns.forEach(function (b) {
      var on = b.getAttribute('data-tab') === id;
      b.classList.toggle('active', on);
      b.classList.toggle('on', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
  }
  btns.forEach(function (b) {
    b.addEventListener('click', function (e) {
      e.preventDefault();
      var id = b.getAttribute('data-tab'), p = wrap.querySelector('.shop-panel[data-tab="' + id + '"]');
      if (!p) return;
      var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      wrap.scrollTo({ left: p.offsetLeft - wrap.offsetLeft, behavior: reduce ? 'auto' : 'smooth' });
      mark(id);
    });
  });
  var start = wrap.querySelector('.shop-panel.active') || panels[0];
  if (start) {
    wrap.scrollLeft = start.offsetLeft - wrap.offsetLeft;
    mark(start.getAttribute('data-tab'));
  }
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.intersectionRatio >= 0.6) mark(en.target.getAttribute('data-tab')); });
    }, { root: wrap, threshold: [0.6] });
    panels.forEach(function (p) { io.observe(p); });
  }
})();
