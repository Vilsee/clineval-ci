// Lazy <spline-viewer> mounting. Scenes load only when scrolled into view and only if 3D is switched on.
// Click a scene to interact (so it never traps page scrolling); the switch is remembered per browser.
(function () {
  var VIEWER = 'https://cdn.spline.design/@splinetool/viewer@2.0.111/build/spline-viewer.js';
  var KEY = 'clineval-3d';
  function stored() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function save(v) { try { localStorage.setItem(KEY, v); } catch (e) {} }
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var enabled = stored() === null ? !reduce : stored() === 'on';
  var viewerRequested = false;
  var io = ('IntersectionObserver' in window) ? new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { io.unobserve(e.target); mount(e.target); } });
  }, { rootMargin: '200px' }) : null;

  function loadViewer() {
    if (viewerRequested) return; viewerRequested = true;
    var s = document.createElement('script'); s.type = 'module'; s.src = VIEWER; document.head.append(s);
  }
  function mount(slot) {
    if (!enabled || slot.dataset.mounted) return;
    var url = (window.SCENES || {})[slot.dataset.scene];
    if (!url) return;
    loadViewer();
    var v = document.createElement('spline-viewer'); v.setAttribute('url', url);
    slot.prepend(v); slot.dataset.mounted = '1';
  }
  function unmount(slot) {
    var v = slot.querySelector('spline-viewer'); if (v) v.remove();
    delete slot.dataset.mounted; slot.classList.remove('live');
  }
  function decorate(slot) {
    if (slot.dataset.ready) return; slot.dataset.ready = '1';
    var hint = document.createElement('div'); hint.className = 'spline-hint'; hint.textContent = 'Click to interact, move away to scroll';
    var off = document.createElement('div'); off.className = 'spline-off'; off.textContent = '3D is switched off. Use the 3D button to turn it on.';
    slot.append(hint, off);
    slot.addEventListener('click', function () { if (enabled) slot.classList.add('live'); });
    slot.addEventListener('mouseleave', function () { slot.classList.remove('live'); });
  }
  function slots() { return document.querySelectorAll('.spline-slot'); }
  function labels() {
    document.querySelectorAll('[data-3d-toggle]').forEach(function (b) { b.textContent = enabled ? '3D: on' : '3D: off'; b.setAttribute('aria-pressed', String(enabled)); });
  }
  function scan() {
    slots().forEach(function (s) {
      decorate(s); s.classList.toggle('off', !enabled);
      if (enabled && !s.dataset.mounted) { if (io) io.observe(s); else mount(s); }
      if (!enabled) unmount(s);
    });
    labels();
  }
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('[data-3d-toggle]');
    if (!t) return;
    enabled = !enabled; save(enabled ? 'on' : 'off'); scan();
  });
  window.Spline3D = { scan: scan, isEnabled: function () { return enabled; } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan); else scan();
})();
