/* ==========================================================================
   RefriMaster — Página del carrito de compras
   ========================================================================== */
(function () {
  'use strict';

  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 window.location.origin;

  var ENVIO = { costo: 25000, gratis_desde: 500000 };

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function toast(message, type) {
    var el = $('#toast');
    el.textContent = message;
    el.className = 'toast show' + (type ? ' ' + type : '');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.className = 'toast'; }, 3600);
  }

  function moneyDOP(value) {
    if (value == null) return '';
    return new Intl.NumberFormat('es-DO', {
      style: 'currency', currency: 'DOP', maximumFractionDigits: 0,
    }).format(value);
  }

  function envioCosto(subtotal) {
    if (subtotal >= ENVIO.gratis_desde) return 0;
    return ENVIO.costo;
  }

  async function loadConfig() {
    try {
      var res = await fetch(API_BASE + '/api/tienda/config/');
      if (!res.ok) return;
      var c = await res.json();
      if (c.costo_envio != null) ENVIO.costo = Number(c.costo_envio);
      if (c.envio_gratis_desde != null) ENVIO.gratis_desde = Number(c.envio_gratis_desde);
    } catch (e) { /* valores por defecto */ }
  }

  function itemRow(it) {
    var lineTotal = (parseFloat(it.precio) || 0) * it.cantidad;
    return '<div class="flex w-full min-w-0 flex-col gap-4 rounded-3xl border border-outline-variant bg-white p-5 shadow-sm sm:flex-row sm:items-center">' +
      '<a href="/productos/" class="block aspect-[4/3] w-full shrink-0 overflow-hidden rounded-xl bg-surface-container sm:h-36 sm:w-44 sm:aspect-auto">' +
        '<img src="' + esc(it.imagen) + '" alt="' + esc(it.nombre) + '" class="h-full w-full object-contain p-2" loading="lazy">' +
      '</a>' +
      '<div class="min-w-0 flex-1">' +
        '<h3 class="truncate font-headline-md text-headline-md font-bold text-on-surface">' + esc(it.nombre) + '</h3>' +
        '<p class="mt-1 text-sm text-on-surface-variant">Precio unitario: ' + moneyDOP(it.precio) + '</p>' +
        '<div class="mt-3 flex flex-wrap items-center gap-3">' +
          '<div class="flex items-center rounded-xl border border-outline-variant">' +
            '<button data-cart-minus="' + it.id + '" type="button" class="px-3 py-2 text-on-surface transition-colors hover:bg-surface-dim" aria-label="Disminuir"><span class="material-symbols-outlined text-sm">remove</span></button>' +
            '<span class="w-12 border-x border-outline-variant py-2 text-center font-bold text-on-surface">' + it.cantidad + '</span>' +
            '<button data-cart-plus="' + it.id + '" type="button" class="px-3 py-2 text-on-surface transition-colors hover:bg-surface-dim" aria-label="Aumentar"><span class="material-symbols-outlined text-sm">add</span></button>' +
          '</div>' +
          '<button data-cart-remove="' + it.id + '" type="button" class="ml-auto inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-semibold text-error transition-colors hover:bg-red-50">' +
            '<span class="material-symbols-outlined text-sm">delete</span> Quitar</button>' +
        '</div>' +
      '</div>' +
      '<div class="text-right">' +
        '<span class="font-label-md font-bold text-on-surface-variant">SUBTOTAL</span>' +
        '<div class="text-lg font-extrabold tracking-tight text-primary">' + moneyDOP(lineTotal) + '</div>' +
      '</div>' +
    '</div>';
  }

  function render() {
    var items = window.Cart.items();
    var subtotal = window.Cart.subtotal();
    var envio = envioCosto(subtotal);
    var total = subtotal + envio;

    var itemsBox = $('#cartItems');
    var summaryBox = $('#cartSummary');

    if (!items.length) {
      itemsBox.innerHTML = '<div class="flex flex-col items-center justify-center rounded-3xl border border-dashed border-outline bg-white py-20 text-center">' +
        '<span class="material-symbols-outlined text-6xl text-slate-400">shopping_cart</span>' +
        '<h2 class="mt-4 font-headline-md text-headline-md font-bold text-on-surface">Tu carrito está vacío</h2>' +
        '<p class="mt-2 max-w-sm text-sm text-on-surface-variant">Explora el almacén y agrega productos de refrigeración para comenzar tu pedido.</p>' +
        '<a href="/productos/" class="mt-6 inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 font-label-md text-white transition-colors hover:bg-primary-hover">' +
          '<span class="material-symbols-outlined">storefront</span> Ir al almacén</a>' +
      '</div>';
      summaryBox.innerHTML = '';
      return;
    }

    itemsBox.innerHTML = '<div class="space-y-4">' +
      '<div class="flex flex-wrap items-center justify-between gap-2">' +
        '<h2 class="font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">' +
          items.length + ' producto' + (items.length === 1 ? '' : 's') + '</h2>' +
        '<button data-cart-clear class="inline-flex items-center gap-2 rounded-xl border border-outline-variant px-4 py-2 font-label-md text-on-surface transition-colors hover:bg-surface-dim">' +
          '<span class="material-symbols-outlined text-sm">delete_sweep</span> Vaciar carrito</button>' +
      '</div>' +
      items.map(itemRow).join('') +
    '</div>';

    summaryBox.innerHTML = '<div class="sticky top-20 rounded-3xl border border-outline-variant bg-white p-6 shadow-sm">' +
      '<h3 class="font-headline-md text-headline-md font-bold text-on-surface">Resumen</h3>' +
      '<div class="mt-4 space-y-3 text-sm">' +
        '<div class="flex items-center justify-between"><span class="text-on-surface-variant">Subtotal</span><span class="font-semibold text-on-surface">' + moneyDOP(subtotal) + '</span></div>' +
        '<div class="flex items-center justify-between">' +
          '<span class="text-on-surface-variant">Envío</span>' +
          '<span class="font-semibold ' + (envio === 0 ? 'text-success' : 'text-on-surface') + '">' + (envio === 0 ? 'Gratis' : moneyDOP(envio)) + '</span>' +
        '</div>' +
        '<div class="flex items-center justify-between border-t border-outline-variant pt-3">' +
          '<span class="font-bold text-on-surface">Total</span>' +
          '<span class="text-xl font-extrabold tracking-tight text-primary">' + moneyDOP(total) + '</span>' +
        '</div>' +
      '</div>' +
      (envio > 0
        ? '<p class="mt-3 rounded-lg bg-primary-container px-3 py-2 text-xs text-on-primary-container">' +
            'Agrega ' + moneyDOP(ENVIO.gratis_desde - subtotal) + ' más para envío gratis.</p>'
        : '<p class="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">¡Tienes envío gratis!</p>') +
      '<button data-pagar class="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 font-label-md text-white transition-colors hover:bg-primary-hover">' +
        '<span class="material-symbols-outlined">lock</span> Continuar al pago</button>' +
      '<a href="/productos/" class="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl border border-outline-variant py-3 font-label-md text-on-surface transition-colors hover:bg-surface-dim">' +
        '<span class="material-symbols-outlined">arrow_back</span> Seguir comprando</a>' +
    '</div>';
  }

  $('#cartItems').addEventListener('click', function (e) {
    var minus = e.target.closest('[data-cart-minus]');
    var plus = e.target.closest('[data-cart-plus]');
    var remove = e.target.closest('[data-cart-remove]');
    var clear = e.target.closest('[data-cart-clear]');
    if (clear) {
      window.Cart.clear();
      toast('Carrito vaciado.', 'info');
    } else if (minus) {
      var it = window.Cart.items().find(function (i) { return i.id === parseInt(minus.dataset.cartMinus, 10); });
      if (it) window.Cart.setQty(it.id, it.cantidad - 1);
    } else if (plus) {
      var it2 = window.Cart.items().find(function (i) { return i.id === parseInt(plus.dataset.cartPlus, 10); });
      if (it2) window.Cart.setQty(it2.id, it2.cantidad + 1);
    } else if (remove) {
      window.Cart.remove(parseInt(remove.dataset.cartRemove, 10));
      toast('Producto eliminado.', 'info');
    }
    render();
  });

  $('#cartSummary').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-pagar]');
    if (!btn) return;
    if (isStaff()) {
      toast('Solo los clientes pueden realizar compras.', 'error');
      return;
    }
    var token = null;
    try { token = localStorage.getItem('refri_access'); } catch (e) { /* ok */ }
    if (!token) {
      try { localStorage.setItem('refri_checkout_return', '/checkout/'); } catch (e) { /* ok */ }
      window.location.href = '/?open_login=1';
      return;
    }
    window.location.href = '/checkout/';
  });

  /* ---------- Roles que no deben usar el carrito ---------- */
  var STAFF_ROLES = ['administrador', 'supervisor', 'tecnico', 'almacen'];

  function getUser() {
    try { return JSON.parse(localStorage.getItem('refri_user')); } catch (e) { return null; }
  }

  function isStaff() {
    var u = getUser();
    return u && STAFF_ROLES.indexOf(u.role) >= 0;
  }

  /* ---------- Sesión (opcional) ---------- */
  function applySession(user) {
    var area = $('#sessionArea');
    if (!user) {
      area.innerHTML = '<a href="/" class="inline-flex items-center gap-2 rounded-xl border-2 border-primary/25 px-4 py-2 font-label-md font-bold text-primary transition-all hover:border-primary hover:bg-primary-container active:scale-95"><span class="material-symbols-outlined text-base">login</span>Iniciar Sesión</a>';
    } else {
      var name = user.full_name || user.username || 'Usuario';
      var panelBtn = (STAFF_ROLES.indexOf(user.role) >= 0)
        ? '<a href="/admin-dashboard/" class="rounded-lg bg-primary px-4 py-2 font-label-md text-white transition-colors hover:bg-primary-hover">Panel</a>'
        : '';
      area.innerHTML = '<span class="hidden font-body-md font-medium text-on-surface-variant md:inline">Hola, ' + esc(name) + '</span>' + panelBtn;
    }
    area.classList.remove('hidden');
    area.classList.add('flex');
  }
  try {
    var raw = localStorage.getItem('refri_user');
    if (raw) applySession(JSON.parse(raw));
    else applySession(null);
  } catch (e) { applySession(null); }

  /* ---------- Menú móvil + año ---------- */
  var menuBtn = $('#menuBtn');
  var mobileMenu = $('#mobileMenu');
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', function () { mobileMenu.classList.toggle('hidden'); });
    $$('#mobileMenu a').forEach(function (a) {
      a.addEventListener('click', function () { mobileMenu.classList.add('hidden'); });
    });
  }
  var yearEl = $('#year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  /* ---------- Arranque ---------- */
  (async function init() {
    if (isStaff()) {
      toast('El carrito de compras está disponible solo para clientes.', 'error');
      var itemsBox = $('#cartItems');
      if (itemsBox) {
        itemsBox.innerHTML = '<div class="flex flex-col items-center justify-center gap-4 rounded-3xl border border-dashed border-outline bg-white py-20 text-center">' +
          '<span class="material-symbols-outlined text-6xl text-error">block</span>' +
          '<h2 class="font-headline-md text-headline-md font-bold text-on-surface">Acceso no disponible</h2>' +
          '<p class="max-w-sm text-sm text-on-surface-variant">El carrito de compras está disponible únicamente para clientes.</p>' +
          '<a href="/admin-dashboard/" class="mt-2 inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3 font-label-md text-white transition-colors hover:bg-primary-hover">' +
            '<span class="material-symbols-outlined">dashboard</span> Ir al panel</a>' +
        '</div>';
      }
      var summaryBox = $('#cartSummary');
      if (summaryBox) summaryBox.innerHTML = '';
      return;
    }
    await loadConfig();
    render();
  })();
})();
