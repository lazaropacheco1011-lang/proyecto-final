/* ==========================================================================
   RefriMaster — Confirmación de pedido
   Lee el número de orden de la URL y muestra el detalle público desde la API.
   ========================================================================== */
(function () {
  'use strict';

  var API_BASE = window.REFRI_API || 'http://127.0.0.1:8000';

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

  var ESTADO_PAGO = {
    aprobado: { cls: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20' },
    pendiente: { cls: 'bg-amber-50 text-amber-700 ring-amber-600/20' },
    rechazado: { cls: 'bg-red-50 text-red-700 ring-red-600/20' },
    reembolsado: { cls: 'bg-slate-100 text-slate-700 ring-slate-600/20' },
  };

  function badgePago(pagos) {
    var pago = Array.isArray(pagos) && pagos.length ? pagos[0] : null;
    if (!pago) return { texto: 'Sin datos de pago', clase: 'bg-slate-100 text-slate-700 ring-slate-600/20' };
    var s = ESTADO_PAGO[pago.estado] || ESTADO_PAGO.pendiente;
    var detalle = 'Pago con ' + (pago.metodo_display || pago.metodo || '') + ' · ' +
      (pago.estado_display || pago.estado || '');
    if (pago.ultimos_digitos) detalle += ' · **** ' + pago.ultimos_digitos;
    if (pago.referencia) detalle += ' · Ref: ' + pago.referencia;
    return { texto: detalle, clase: s.cls };
  }

  async function cargarOrden(numero) {
    try {
      var res = await fetch(API_BASE + '/api/tienda/ordenes/p/' + encodeURIComponent(numero) + '/');
      if (res.status === 404) {
        $('#confLoading').classList.add('hidden');
        $('#confTitle').textContent = 'Pedido no encontrado';
        $('#confSub').textContent = 'No pudimos localizar el pedido. Revisa el número e inténtalo de nuevo.';
        toast('Pedido no encontrado.', 'error');
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var o = await res.json();
      renderizar(o);
    } catch (e) {
      $('#confLoading').classList.add('hidden');
      $('#confTitle').textContent = 'No se pudo cargar el pedido';
      $('#confSub').textContent = 'Verifica tu conexión e intenta de nuevo.';
      toast('Error al cargar el pedido.', 'error');
    }
  }

  function renderizar(o) {
    var cancelada = o.estado === 'cancelado';
    var pago = badgePago(o.pagos);
    var rechazada = o.pagos && o.pagos.some(function (p) { return p.estado === 'rechazado'; });

    $('#confLoading').classList.add('hidden');
    $('#confContent').classList.remove('hidden');
    $('#confNumero').textContent = o.numero;

    var estadoCls = 'bg-emerald-50 text-emerald-700 ring-emerald-600/20';
    if (cancelada) estadoCls = 'bg-red-50 text-red-700 ring-red-600/20';
    else if (o.estado === 'pendiente') estadoCls = 'bg-amber-50 text-amber-700 ring-amber-600/20';
    var st = $('#confEstado');
    st.className = 'inline-flex items-center gap-2 rounded-full px-4 py-1.5 font-label-md font-bold ring-1 ring-inset ' + estadoCls;
    st.textContent = o.estado_display || o.estado;

    var pagoEl = $('#confPagoDetalle');
    if (cancelada) {
      $('#confTitle').textContent = 'Pedido cancelado';
      $('#confSub').textContent = 'Tu pedido fue cancelado. Si ya realizaste un pago, este será reembolsado.';
      $('#confStateIcon').textContent = 'cancel';
      $('#confStateIcon').className = 'material-symbols-outlined text-6xl text-error';
      pagoEl.textContent = 'El pedido fue cancelado.';
      $('#confPago').classList.add('hidden');
    } else if (rechazada) {
      $('#confTitle').textContent = 'Pago rechazado';
      $('#confSub').textContent = 'No pudimos procesar el pago. Tu pedido quedó pendiente: intenta nuevamente o contacta a un asesor.';
      $('#confStateIcon').textContent = 'error';
      $('#confStateIcon').className = 'material-symbols-outlined text-6xl text-error';
      pagoEl.textContent = pago.texto + '. No se realizó ningún cargo a tu tarjeta.';
    } else {
      pagoEl.textContent = pago.texto + '. Recibirás el estado de tu pedido por correo.';
    }

    $('#confItems').innerHTML = (o.items || []).map(function (it) {
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
    }).join('');

    $('#confSubtotal').textContent = moneyDOP(o.subtotal);
    $('#confEnvio').textContent = (o.envio || 0) === 0 ? 'Gratis' : moneyDOP(o.envio);
    $('#confTotal').textContent = moneyDOP(o.total);
  }

  /* ---------- Menú móvil + año ---------- */
  var menuBtn = $('#menuBtn');
  var mobileMenu = $('#mobileMenu');
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', function () { mobileMenu.classList.toggle('hidden'); });
  }
  var yearEl = $('#year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  var numero = new URLSearchParams(location.search).get('orden');
  if (!numero) {
    $('#confLoading').classList.add('hidden');
    $('#confTitle').textContent = 'Pedido no encontrado';
    $('#confSub').textContent = 'No se recibió ningún número de pedido.';
    toast('Falta el número de pedido.', 'error');
  } else {
    cargarOrden(numero);
  }
})();
