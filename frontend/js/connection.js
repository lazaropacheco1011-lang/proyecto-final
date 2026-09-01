/**
 * connection.js — Monitor de conexión con el backend Django.
 * Muestra un banner persistente cuando el servidor no responde.
 * Se incluye ANTES de los demás scripts en cada página.
 */
(function () {
  'use strict';

  var PING_INTERVAL = 12000;
  var PING_TIMEOUT  = 5000;
  var FAIL_THRESHOLD = 2;
  var API_BASE = window.REFRI_API || window.location.origin;

  var failCount   = 0;
  var isOffline   = false;
  var timer       = null;
  var banner      = null;
  var abortCtrl   = null;

  /* ---------- Crear banner DOM ---------- */
  function ensureBanner() {
    if (banner) return banner;
    banner = document.createElement('div');
    banner.id = 'connectionBanner';
    banner.className = 'conn-banner';
    banner.setAttribute('role', 'alert');
    banner.setAttribute('aria-live', 'assertive');
    banner.innerHTML =
      '<span class="conn-banner__icon material-symbols-outlined">cloud_off</span>' +
      '<span class="conn-banner__text">' +
        '<strong>Servidor desconectado</strong>' +
        '<span>Algunas funciones no están disponibles. Verifica que el servidor esté iniciado.</span>' +
      '</span>';
    document.body.appendChild(banner);
    return banner;
  }

  /* ---------- Mostrar / ocultar ---------- */
  function showBanner() {
    if (isOffline) return;
    isOffline = true;
    ensureBanner().classList.add('conn-banner--visible');
  }

  function hideBanner() {
    if (!isOffline) return;
    isOffline = false;
    failCount = 0;
    if (banner) banner.classList.remove('conn-banner--visible');
  }

  /* ---------- Ping ---------- */
  function ping() {
    if (abortCtrl) abortCtrl.abort();
    abortCtrl = typeof AbortController !== 'undefined' ? new AbortController() : null;

    var opts = { method: 'HEAD', cache: 'no-store', credentials: 'same-origin' };
    if (abortCtrl) opts.signal = abortCtrl.signal;

    var timeoutId = setTimeout(function () {
      if (abortCtrl) abortCtrl.abort();
      onFail();
    }, PING_TIMEOUT);

    fetch(API_BASE + '/', opts)
      .then(function () { onOK(); })
      .catch(function () { onFail(); })
      .finally(function () { clearTimeout(timeoutId); });
  }

  function onOK() {
    failCount = 0;
    hideBanner();
  }

  function onFail() {
    failCount++;
    if (failCount >= FAIL_THRESHOLD) showBanner();
  }

  /* ---------- Iniciar ---------- */
  function start() {
    if (timer) return;
    ping();
    timer = setInterval(ping, PING_INTERVAL);
  }

  /* ---------- API pública ---------- */
  window.ConnectionMonitor = {
    isOnline: function () { return !isOffline; },
    start: start,
  };

  /* Auto-start cuando el DOM esté listo */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();

/* ==========================================================================
   MODO OSCURO — RefriMaster (compartido por el sitio público y admin)
   - Se aplica en el sitio público y, desde aquí, también en el panel de
     administración (admin-dashboard.html incluye el selector ☀️/🌙).
   - Guarda la preferencia en localStorage; si el usuario no eligió, detecta
     prefers-color-scheme del dispositivo.
   - El atributo data-theme en <html> dispara los overrides de CSS (modo oscuro
     adapta superficies/fondos/bordes/textos sin tocar los colores de marca).
   ========================================================================== */
(function () {
  'use strict';

  var STORAGE_KEY = 'refri_theme';
  var root = document.documentElement;

  function themeFromStorage() {
    try { return localStorage.getItem(STORAGE_KEY); } catch (e) { return null; }
  }

  function storeTheme(theme) {
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (e) { /* ignorar */ }
  }

  function detectSystem() {
    return (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches)
      ? 'dark'
      : 'light';
  }

  function currentTheme() {
    var saved = themeFromStorage();
    return (saved === 'dark' || saved === 'light') ? saved : detectSystem();
  }

  function applyTheme(theme) {
    if (theme === 'dark') root.setAttribute('data-theme', 'dark');
    else root.removeAttribute('data-theme');
    syncIcons(theme);
  }

  function syncIcons(theme) {
    var icons = document.querySelectorAll('[data-theme-icon]');
    var label = theme === 'dark' ? 'dark_mode' : 'light_mode';
    var aria = theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
    for (var i = 0; i < icons.length; i++) {
      icons[i].textContent = label;
      var btn = icons[i].closest('[data-theme-toggle]');
      if (btn) {
        btn.setAttribute('aria-label', aria);
        btn.setAttribute('title', aria);
      }
    }
  }

  function initTheme() {
    applyTheme(currentTheme());

    var toggles = document.querySelectorAll('[data-theme-toggle]');
    for (var i = 0; i < toggles.length; i++) {
      toggles[i].addEventListener('click', function () {
        var next = currentTheme() === 'dark' ? 'light' : 'dark';
        storeTheme(next);
        applyTheme(next);
      });
    }

    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function () {
        if (!themeFromStorage()) applyTheme(detectSystem());
      };
      if (typeof mq.addEventListener === 'function') mq.addEventListener('change', onChange);
      else if (typeof mq.addListener === 'function') mq.addListener(onChange);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }
})();
