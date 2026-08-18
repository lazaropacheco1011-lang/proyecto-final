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
  var API_BASE = window.REFRI_API || 'http://127.0.0.1:8000';

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

    var opts = { method: 'HEAD', mode: 'no-cors' };
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
