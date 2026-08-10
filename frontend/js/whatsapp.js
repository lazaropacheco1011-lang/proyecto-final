/* ==========================================================================
   RefriMaster — Integración de WhatsApp
   - Botón flotante global en todas las páginas públicas
   - Helper window.openWhatsApp(message) para botones por producto
   ========================================================================== */

(function () {
  'use strict';

  /* ------------------------------------------------------------------
   * Configuración (número en formato internacional, República Dominicana)
   * ------------------------------------------------------------------ */
  window.REFRI_WHATSAPP = {
    number: '18091234567', // CAMBIAR: 1 + código de área + número (sin espacios ni símbolos)
    defaultMessage: 'Hola, estoy interesado en sus productos y servicios de refrigeración.',
    tooltip: 'Contáctanos por WhatsApp',
  };

  function waUrl(message) {
    var text = (message == null || message === '')
      ? window.REFRI_WHATSAPP.defaultMessage
      : String(message);
    return 'https://wa.me/' + window.REFRI_WHATSAPP.number +
      '?text=' + encodeURIComponent(text);
  }

  window.openWhatsApp = function (message) {
    window.open(waUrl(message), '_blank', 'noopener');
  };

  function svgIcon() {
    return '<svg viewBox="0 0 32 32" fill="currentColor" aria-hidden="true" focusable="false">' +
      '<path d="M16.004 3.2C8.94 3.2 3.2 8.94 3.2 16.004c0 2.257.59 4.463 1.71 6.407L3.2 28.8l6.496-1.692a12.76 12.76 0 0 0 6.308 1.607h.005c7.065 0 12.79-5.74 12.79-12.804A12.72 12.72 0 0 0 16.004 3.2zm0 23.37a10.6 10.6 0 0 1-5.4-1.48l-.387-.23-3.843 1.001 1.026-3.747-.253-.395a10.55 10.55 0 0 1-1.623-5.716c0-5.862 4.77-10.632 10.634-10.632a10.56 10.56 0 0 1 7.5 3.108 10.56 10.56 0 0 1 3.106 7.517c-.002 5.86-4.77 10.632-10.634 10.632z" fill-rule="evenodd"/>' +
      '<path d="M22.87 18.15c-.302-.151-1.785-.881-2.061-.981-.276-.1-.477-.151-.678.151-.201.302-.779.981-.955 1.182-.176.201-.352.227-.653.076-.302-.152-1.274-.47-2.427-1.498-.897-.8-1.503-1.786-1.68-2.087-.176-.302-.018-.465.133-.615.135-.135.302-.352.452-.528.151-.176.201-.302.302-.503.1-.201.05-.377-.025-.529-.076-.151-.678-1.633-.928-2.236-.244-.586-.492-.506-.678-.515l-.577-.01c-.2 0-.528.075-.803.377-.276.302-1.054 1.03-1.054 2.512 0 1.482 1.078 2.914 1.228 3.115.15.201 2.121 3.238 5.139 4.54.718.31 1.279.495 1.716.633.721.23 1.377.197 1.896.12.579-.087 1.785-.73 2.036-1.435.251-.704.251-1.308.176-1.434-.076-.125-.276-.2-.578-.352z"/>' +
      '</svg>';
  }

  function buildButton() {
    var a = document.createElement('a');
    a.href = waUrl(window.REFRI_WHATSAPP.defaultMessage);
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = 'wa-float';
    a.setAttribute('aria-label', window.REFRI_WHATSAPP.tooltip);
    a.setAttribute('title', window.REFRI_WHATSAPP.tooltip);
    a.innerHTML = svgIcon();
    return a;
  }

  function init() {
    if (document.body) {
      document.body.appendChild(buildButton());
    } else {
      document.addEventListener('DOMContentLoaded', function () {
        document.body.appendChild(buildButton());
      });
    }
  }

  init();
})();
