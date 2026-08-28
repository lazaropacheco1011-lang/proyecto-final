/* ==========================================================================
   RefriMaster — Mis compras del cliente
   Muestra el historial de órdenes del cliente autenticado usando la API
   /api/tienda/mis-compras/ (que filtra por el usuario autenticado, por lo
   que cada cliente solo ve sus propias compras).
   ========================================================================== */
(function () {
  'use strict';

  var API_BASE = window.REFRI_API || window.location.origin;
  var ORDENES = [];

  function $(sel) { return document.querySelector(sel); }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function moneyDOP(value) {
    if (value == null) return '';
    return new Intl.NumberFormat('es-DO', {
      style: 'currency', currency: 'DOP', maximumFractionDigits: 0,
    }).format(value);
  }

  function toast(message, type) {
    var el = $('#toast');
    el.textContent = message;
    el.className = 'toast show' + (type ? ' ' + type : '');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.className = 'toast'; }, 3600);
  }

  function fechaCorta(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('es-DO', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function badgeEstado(estado, estadoDisplay) {
    var cls = 'bg-emerald-50 text-emerald-700 ring-emerald-600/20';
    if (estado === 'cancelado') cls = 'bg-red-50 text-red-700 ring-red-600/20';
    else if (estado === 'pendiente') cls = 'bg-amber-50 text-amber-700 ring-amber-600/20';
    return '<span class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-label-md font-bold ring-1 ring-inset ' + cls + '">' +
      esc(estadoDisplay || estado) + '</span>';
  }

  function badgePago(pagos) {
    var pago = Array.isArray(pagos) && pagos.length ? pagos[0] : null;
    if (!pago) return 'Sin datos de pago';
    return 'Pago con ' + (pago.metodo_display || pago.metodo || '') + ' · ' +
      (pago.estado_display || pago.estado || '');
  }

  function mostrarVacio(titulo, texto, cta) {
    $('#mcLoading').classList.add('hidden');
    $('#mcEmptyTitle').textContent = titulo;
    $('#mcEmptyText').textContent = texto;
    $('#mcEmptyCta').innerHTML = cta || '';
    $('#mcEmpty').classList.remove('hidden');
    $('#mcList').classList.remove('hidden');
  }

  function mostrarLista() {
    $('#mcDetail').classList.add('hidden');
    $('#mcEmpty').classList.add('hidden');
    $('#mcList').classList.remove('hidden');
  }

  function renderDetalle(o) {
    mostrarLista();
    $('#mcDetail').classList.remove('hidden');
    $('#mcList').classList.add('hidden');

    var itemsHtml = (o.items || []).map(function (it) {
      return '<div class="flex items-center gap-4">' +
        '<div class="h-16 w-16 shrink-0 overflow-hidden rounded-xl bg-surface-container">' +
          '<img src="' + esc(it.imagen) + '" alt="' + esc(it.nombre) + '" class="h-full w-full object-cover" loading="lazy">' +
        '</div>' +
        '<div class="min-w-0 flex-1">' +
          '<div class="truncate font-semibold text-on-surface">' + esc(it.nombre) + '</div>' +
          '<div class="text-sm text-on-surface-variant">' + it.cantidad + ' × ' + moneyDOP(it.precio_unitario) + '</div>' +
        '</div>' +
        '<div class="text-sm font-bold text-on-surface">' + moneyDOP(it.subtotal) + '</div>' +
      '</div>';
    }).join('') || '<div class="text-sm text-on-surface-variant">Sin artículos.</div>';

    $('#mcDetailContent').innerHTML =
      '<div class="flex flex-wrap items-start justify-between gap-4 border-b border-outline-variant pb-6">' +
        '<div>' +
          '<p class="font-label-md font-bold text-on-surface-variant">PEDIDO</p>' +
          '<h2 class="mt-1 font-headline-md text-2xl font-bold text-on-surface">' + esc(o.numero) + '</h2>' +
          '<p class="mt-1 text-sm text-on-surface-variant">Realizado el ' + esc(fechaCorta(o.created_at)) + '</p>' +
        '</div>' +
        badgeEstado(o.estado, o.estado_display) +
      '</div>' +
      '<div class="mt-6 space-y-4">' + itemsHtml + '</div>' +
      '<div class="mt-6 flex flex-col gap-1 border-t border-outline-variant pt-4 text-sm sm:ml-auto sm:max-w-xs">' +
        '<div class="flex justify-between text-on-surface-variant"><span>Subtotal</span><span>' + moneyDOP(o.subtotal) + '</span></div>' +
        '<div class="flex justify-between text-on-surface-variant"><span>Envío</span><span>' + ((o.envio || 0) === 0 ? 'Gratis' : moneyDOP(o.envio)) + '</span></div>' +
        '<div class="flex justify-between pt-1 text-base font-bold text-on-surface"><span>Total</span><span>' + moneyDOP(o.total) + '</span></div>' +
        '<div class="mt-2 text-on-surface-variant">' + esc(badgePago(o.pagos)) + '</div>' +
      '</div>';
  }

  function renderLista(ordenes) {
    $('#mcLoading').classList.add('hidden');
    $('#mcList').classList.remove('hidden');

    if (!ordenes.length) {
      mostrarVacio(
        'Aún no tienes compras',
        'Cuando realices tu primera compra, aparecerá aquí.',
        '<a href="/productos/" class="mt-6 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 font-label-md text-white transition-colors hover:bg-primary-hover">' +
          '<span class="material-symbols-outlined">storefront</span> Ir a la tienda</a>'
      );
      return;
    }

    $('#mcOrders').innerHTML = ordenes.map(function (o) {
      var n = (o.items || []).length;
      return '<button type="button" data-orden="' + esc(o.numero) + '" class="w-full rounded-2xl border border-outline-variant bg-white p-5 text-left shadow-sm transition-colors hover:bg-surface-container-low">' +
        '<div class="flex flex-wrap items-center justify-between gap-3">' +
          '<div class="min-w-0">' +
            '<p class="font-label-md font-bold text-on-surface-variant">' + esc(o.numero) + '</p>' +
            '<p class="mt-1 truncate font-semibold text-on-surface">' + (n === 1 ? '1 artículo' : n + ' artículos') + '</p>' +
            '<p class="mt-0.5 text-sm text-on-surface-variant">' + esc(fechaCorta(o.created_at)) + '</p>' +
          '</div>' +
          '<div class="flex items-center gap-3">' +
            badgeEstado(o.estado, o.estado_display) +
            '<span class="text-base font-bold text-on-surface">' + moneyDOP(o.total) + '</span>' +
          '</div>' +
        '</div>' +
      '</button>';
    }).join('');

    $('#mcOrders').querySelectorAll('[data-orden]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var numero = btn.getAttribute('data-orden');
        var orden = ORDENES.find(function (x) { return x.numero === numero; });
        if (orden) renderDetalle(orden);
      });
    });
  }

  async function cargarCompras() {
    var token = localStorage.getItem('refri_access');
    if (!token) {
      mostrarVacio(
        'Inicia sesión para ver tus compras',
        'Necesitas iniciar sesión con tu cuenta de cliente para consultar tu historial.',
        '<a href="/" class="mt-6 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 font-label-md text-white transition-colors hover:bg-primary-hover">Ir a la página principal</a>'
      );
      return;
    }
    try {
      var res = await fetch(API_BASE + '/api/tienda/mis-compras/', {
        headers: { 'Authorization': 'Bearer ' + token },
      });
      if (res.status === 401 || res.status === 403) {
        mostrarVacio(
          'Sesión no válida',
          'Tu sesión expiró o no tienes permisos de cliente. Vuelve a iniciar sesión.',
          '<a href="/" class="mt-6 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 font-label-md text-white transition-colors hover:bg-primary-hover">Ir a la página principal</a>'
        );
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      var ordenes = (data && (data.results || data)) || [];
      ORDENES = ordenes;
      renderLista(ordenes);
    } catch (e) {
      $('#mcLoading').classList.add('hidden');
      mostrarVacio(
        'No se pudieron cargar tus compras',
        'Verifica tu conexión e intenta de nuevo.',
        ''
      );
      toast('Error al cargar tus compras.', 'error');
    }
  }

  var backBtn = $('#mcBack');
  if (backBtn) backBtn.addEventListener('click', function () { mostrarLista(); });

  cargarCompras();
})();
