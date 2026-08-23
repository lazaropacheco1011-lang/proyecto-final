/* ==========================================================================
   RefriMaster — Página independiente de Productos / Almacén
   - Categorías y productos de la vitrina (API Django)
   - Filtros por categoría, búsqueda, detalle de producto (modal)
   ========================================================================== */

(function () {
  'use strict';

  /* ------------------------------------------------------------------
   * Configuración de la API
   * ------------------------------------------------------------------ */
  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 'http://127.0.0.1:8000';

  var EMPRESA = {
    nombre: 'RefriMaster',
    email: 'contacto@refrimaster.com',
  };

  /* ---------- Utilidades ---------- */
  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

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

  /* Precio efectivo del producto: si está en oferta se usa el precio de oferta;
     el precio normal (precio) siempre se conserva para mostrar tachado. */
  function productPricing(p) {
    var original = p.precio != null ? Number(p.precio) : null;
    var oferta = p.precio_oferta != null ? Number(p.precio_oferta) : null;
    var enOferta = !!(p.en_oferta && oferta != null);
    return { enOferta: enOferta, original: original, final: enOferta ? oferta : original };
  }

  async function tryRefresh() {
    var refresh = localStorage.getItem('refri_refresh');
    if (!refresh) return false;
    try {
      var res = await fetch(API_BASE + '/api/auth/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: refresh }),
      });
      var data = await res.json();
      if (!res.ok || !data.access) return false;
      localStorage.setItem('refri_access', data.access);
      if (data.refresh) localStorage.setItem('refri_refresh', data.refresh);
      return true;
    } catch (e) {
      return false;
    }
  }

  async function api(path, options) {
    options = options || {};
    var token = localStorage.getItem('refri_access');
    var headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
    if (token) headers['Authorization'] = 'Bearer ' + token;

    var res = await fetch(API_BASE + path, Object.assign({}, options, { headers: headers }));

    if (res.status === 401) {
      if (await tryRefresh()) {
        headers['Authorization'] = 'Bearer ' + localStorage.getItem('refri_access');
        res = await fetch(API_BASE + path, Object.assign({}, options, { headers: headers }));
      }
    }

    var data = null;
    try { data = await res.json(); } catch (e) { /* cuerpo no JSON */ }
    if (!res.ok) {
      var err = new Error('API error ' + res.status);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function apiErrorMessage(err) {
    var d = err && err.data;
    if (!d) return 'No fue posible completar la petición. Verifica tu conexión.';
    if (typeof d === 'string') return d;
    if (typeof d === 'object') {
      if (typeof d.message === 'string' && d.message) {
        return String(d.message).replace(/^(error|non_field_errors):\s*/i, '');
      }
      if (typeof d.detail === 'string' && d.detail) return d.detail;
      if (d.errors && typeof d.errors === 'object') {
        var ekeys = Object.keys(d.errors);
        if (ekeys.length) {
          var e0 = d.errors[ekeys[0]];
          if (Array.isArray(e0) && e0.length) return e0[0];
          if (typeof e0 === 'string') return e0;
        }
      }
      var keys = Object.keys(d);
      for (var i = 0; i < keys.length; i++) {
        if (keys[i] === 'status' || keys[i] === 'message' || keys[i] === 'errors') continue;
        var first = d[keys[i]];
        if (Array.isArray(first) && first.length) return first[0];
        if (typeof first === 'string') return first;
      }
    }
    return 'No fue posible completar la petición. Verifica tu conexión.';
  }

  /* ---------- Modales ---------- */
  function openModal(name) {
    var m = $('#modal-' + name);
    if (!m) return;
    m.classList.remove('hidden');
    m.classList.add('flex');
    document.body.style.overflow = 'hidden';
  }

  function closeModal(name) {
    var m = $('#modal-' + name);
    if (!m) return;
    m.classList.add('hidden');
    m.classList.remove('flex');
    document.body.style.overflow = '';
  }

  function closeAll() {
    closeModal('producto');
    closeModal('solicitud');
  }

  $$('[data-close]').forEach(function (btn) {
    btn.addEventListener('click', function () { closeModal(btn.dataset.close); });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });

  /* ---------- Sesión del usuario ---------- */
  var STAFF_ROLES = ['administrador', 'supervisor', 'tecnico', 'almacen'];

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

  (function initSession() {
    try {
      var raw = localStorage.getItem('refri_user');
      if (raw) applySession(JSON.parse(raw));
      else applySession(null);
    } catch (e) {
      applySession(null);
    }
  })();

  /* ---------- Menú móvil ---------- */
  var menuBtn = $('#menuBtn');
  var mobileMenu = $('#mobileMenu');
  if (menuBtn && mobileMenu) {
    menuBtn.addEventListener('click', function () {
      mobileMenu.classList.toggle('hidden');
    });
    $$('#mobileMenu a').forEach(function (a) {
      a.addEventListener('click', function () {
        mobileMenu.classList.add('hidden');
      });
    });
  }

  /* ---------- Año del footer y scroll del navbar ---------- */
  var yearEl = $('#year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  var navEl = document.querySelector('nav');
  if (navEl) {
    window.addEventListener('scroll', function () {
      if (window.scrollY > 50) {
        navEl.classList.add('shadow-md');
        navEl.classList.remove('border-outline-variant');
      } else {
        navEl.classList.remove('shadow-md');
        navEl.classList.add('border-outline-variant');
      }
    }, { passive: true });
  }

  /* ------------------------------------------------------------------
   * Vitrina de productos
   * ------------------------------------------------------------------ */
  var UMBRAL_STOCK_BAJO = 5;
  var ROLES_STOCK = ['administrador', 'almacen'];
  var ROLES_GESTION = ['administrador', 'supervisor', 'almacen'];
  var currentUser = null;
  try { currentUser = JSON.parse(localStorage.getItem('refri_user')); } catch (e) { currentUser = null; }
  var esGestion = currentUser && ROLES_GESTION.indexOf(currentUser.role) >= 0;
  var esStock = currentUser && ROLES_STOCK.indexOf(currentUser.role) >= 0;

  var state = { cat: '', search: '', disp: '', page: 1 };
  var cats = [];
  var catMap = {};
  var currentProduct = null;
  var PAGE_SIZE = 20;

  async function fetchPage(page, categoria, search, disp) {
    var qs = 'page=' + page;
    if (categoria) qs += '&categoria=' + encodeURIComponent(categoria);
    if (search) qs += '&search=' + encodeURIComponent(search);
    if (disp) qs += '&disp=' + encodeURIComponent(disp);
    var data = await api('/api/productos/?' + qs);
    return {
      products: data.results || [],
      count: data.count || 0,
      page: page,
      totalPages: Math.max(1, Math.ceil((data.count || 0) / PAGE_SIZE)),
      hasPrev: !!data.previous,
      hasNext: !!data.next,
    };
  }

  async function loadCats() {
    try {
      cats = await api('/api/categorias/');
    } catch (e) {
      cats = [];
    }
    catMap = {};
    cats.forEach(function (c) { catMap[c.id] = c; });
  }

  function stockState(p) {
    if (p.agotado) return { cls: 'av-badge-error', icon: 'remove_circle', txt: 'Agotado' };
    if (p.stock <= UMBRAL_STOCK_BAJO) return { cls: 'av-badge-warning', icon: 'warning', txt: 'Stock bajo · ' + p.stock + ' und' };
    return { cls: 'av-badge-success', icon: 'check_circle', txt: 'Disponible · ' + p.stock + ' und' };
  }

  function productImage(p) {
    var icono = (catMap[p.categoria] && catMap[p.categoria].icono) || 'inventory_2';
    return '<div data-producto="' + esc(p.id) + '" class="relative aspect-[4/3] cursor-pointer overflow-hidden bg-gradient-to-br from-primary-container via-surface-container to-surface-container-high">' +
      '<span class="material-symbols-outlined absolute inset-0 flex items-center justify-center text-6xl text-primary/40">' + esc(icono) + '</span>' +
      (p.imagen
        ? '<img src="' + esc(p.imagen) + '" alt="' + esc(p.nombre) + '" class="absolute inset-0 h-full w-full object-contain p-7 transition-transform duration-500 group-hover:scale-105" loading="lazy" width="800" height="560" onload="this.previousElementSibling.classList.add(\'hidden\');" onerror="this.onerror=null; this.remove();">'
        : '') +
      '<div class="absolute left-4 right-4 top-4 z-10 flex flex-wrap items-start justify-between gap-2">' +
        '<span class="img-badge min-w-0 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-on-surface shadow-sm backdrop-blur">' + esc(p.categoria_nombre) + '</span>' +
        (p.destacado
          ? '<span class="flex shrink-0 items-center gap-1 rounded-full bg-warning px-3 py-1 text-xs font-bold text-white shadow-sm"><span class="material-symbols-outlined text-xs">star</span>Destacado</span>'
          : '') +
      '</div>' +
      '</div>';
  }

  function productAction(p) {
    var esStaff = currentUser && STAFF_ROLES.indexOf(currentUser.role) >= 0;
    if (esStaff) return '';
    var icon, label, cls;
    if (p.agotado) {
      icon = 'remove_circle'; label = 'Agotado';
      cls = 'mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-slate-100 py-2.5 font-label-md font-bold text-slate-400';
      return '<button type="button" disabled class="' + cls + '"><span class="material-symbols-outlined text-base">' + icon + '</span>' + label + '</button>';
    }
    if (productPricing(p).final == null) {
      icon = 'mail'; label = 'Solicitar cotización';
      cls = 'mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl border-2 border-primary/25 py-2.5 font-label-md font-bold text-primary transition-all hover:border-primary hover:bg-primary-container';
      return '<button type="button" data-solicitar="' + esc(p.id) + '" class="' + cls + '"><span class="material-symbols-outlined text-base">' + icon + '</span>' + label + '</button>';
    }
    icon = 'shopping_cart'; label = 'Comprar';
    cls = 'mt-4 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-2.5 font-label-md font-bold text-white transition-colors hover:bg-primary-hover';
    return '<button type="button" data-producto="' + esc(p.id) + '" class="' + cls + '"><span class="material-symbols-outlined text-base">' + icon + '</span>' + label + '</button>';
  }

  function adminActions(p) {
    if (!esGestion) return '';
    var stockBtn = esStock
      ? '<button data-stock="' + p.id + '" class="gest-btn gest-btn-primary" title="Actualizar stock"><span class="material-symbols-outlined text-sm">inventory</span> Stock</button>'
      : '';
    return '<div class="mt-4 grid grid-cols-2 gap-2 border-t border-outline-variant pt-4">' +
      stockBtn +
      '<a href="/admin-dashboard/#/almacen/editar/' + p.id + '" class="gest-btn" title="Editar producto"><span class="material-symbols-outlined text-sm">edit</span> Editar</a>' +
      '<a href="/admin-dashboard/#/almacen" class="gest-btn" title="Gestionar en el panel"><span class="material-symbols-outlined text-sm">tune</span> Gestionar</a>' +
      '</div>';
  }

  /* ---------- WhatsApp por producto ---------- */
  var WA_ICON = '<svg viewBox="0 0 32 32" fill="currentColor" aria-hidden="true" focusable="false">' +
    '<path d="M16.004 3.2C8.94 3.2 3.2 8.94 3.2 16.004c0 2.257.59 4.463 1.71 6.407L3.2 28.8l6.496-1.692a12.76 12.76 0 0 0 6.308 1.607h.005c7.065 0 12.79-5.74 12.79-12.804A12.72 12.72 0 0 0 16.004 3.2zm0 23.37a10.6 10.6 0 0 1-5.4-1.48l-.387-.23-3.843 1.001 1.026-3.747-.253-.395a10.55 10.55 0 0 1-1.623-5.716c0-5.862 4.77-10.632 10.634-10.632a10.56 10.56 0 0 1 7.5 3.108 10.56 10.56 0 0 1 3.106 7.517c-.002 5.86-4.77 10.632-10.634 10.632z" fill-rule="evenodd"/>' +
    '<path d="M22.87 18.15c-.302-.151-1.785-.881-2.061-.981-.276-.1-.477-.151-.678.151-.201.302-.779.981-.955 1.182-.176.201-.352.227-.653.076-.302-.152-1.274-.47-2.427-1.498-.897-.8-1.503-1.786-1.68-2.087-.176-.302-.018-.465.133-.615.135-.135.302-.352.452-.528.151-.176.201-.302.302-.503.1-.201.05-.377-.025-.529-.076-.151-.678-1.633-.928-2.236-.244-.586-.492-.506-.678-.515l-.577-.01c-.2 0-.528.075-.803.377-.276.302-1.054 1.03-1.054 2.512 0 1.482 1.078 2.914 1.228 3.115.15.201 2.121 3.238 5.139 4.54.718.31 1.279.495 1.716.633.721.23 1.377.197 1.896.12.579-.087 1.785-.73 2.036-1.435.251-.704.251-1.308.176-1.434-.076-.125-.276-.2-.578-.352z"/>' +
    '</svg>';

  function productWhatsApp(p) {
    var wa = window.REFRI_WHATSAPP || { number: '18091234567' };
    var msg = 'Hola, estoy interesado en el producto: ' + p.nombre + '.';
    var href = 'https://wa.me/' + wa.number + '?text=' + encodeURIComponent(msg);
    return '<a href="' + href + '" target="_blank" rel="noopener" class="wa-btn" title="Consultar por WhatsApp">' +
      WA_ICON + 'Consultar por WhatsApp</a>';
  }

  function productCard(p) {
    var pricing = productPricing(p);
    var hasPrecio = pricing.final != null;
    var st = stockState(p);
    var precioHTML = hasPrecio
      ? (pricing.enOferta
          ? '<span class="min-w-0 leading-tight">' +
              '<span class="block text-xs font-semibold text-on-surface-variant line-through">' + moneyDOP(pricing.original) + '</span>' +
              '<span class="text-xl font-extrabold tracking-tight text-primary">' + moneyDOP(pricing.final) + '</span>' +
            '</span>'
          : '<span class="min-w-0 text-xl font-extrabold tracking-tight text-primary">' + moneyDOP(pricing.final) + '</span>')
      : '<span class="rounded-lg bg-primary-container px-2.5 py-1 text-xs font-bold text-on-primary-container">CONSULTAR PRECIO</span>';
    return '<article class="av-card group flex flex-col overflow-hidden rounded-3xl border border-outline-variant bg-white shadow-sm transition-all duration-300 hover:-translate-y-1.5 hover:shadow-xl">' +
      productImage(p) +
      '<div class="flex flex-1 flex-col p-6">' +
        '<h3 data-producto="' + esc(p.id) + '" class="cursor-pointer font-headline-md text-headline-md font-bold text-on-surface transition-colors hover:text-primary">' + esc(p.nombre) + '</h3>' +
        '<p class="mt-2 flex-1 text-sm leading-relaxed text-on-surface-variant">' + esc(p.descripcion) + '</p>' +
        '<div class="mt-4 flex flex-wrap items-center justify-between gap-2">' +
          precioHTML +
          '<span class="' + st.cls + ' av-badge"><span class="material-symbols-outlined text-sm">' + st.icon + '</span>' + st.txt + '</span>' +
        '</div>' +
        productAction(p) +
        productWhatsApp(p) +
        adminActions(p) +
      '</div>' +
    '</article>';
  }

  function emptyState(icon, title, sub) {
    return '<div class="flex flex-col items-center justify-center py-16 text-center">' +
      '<span class="material-symbols-outlined text-5xl text-slate-400">' + esc(icon) + '</span>' +
      '<p class="mt-3 font-semibold text-on-surface">' + esc(title) + '</p>' +
      (sub ? '<p class="mt-1 text-sm text-on-surface-variant">' + esc(sub) + '</p>' : '') +
      '</div>';
  }

  function resultsHeader(d) {
    var title, label;
    if (state.search) {
      title = 'Resultados de búsqueda';
      label = d.count + ' producto' + (d.count === 1 ? '' : 's') + ' para "' + state.search + '"';
    } else if (state.cat && catMap[state.cat]) {
      title = catMap[state.cat].nombre;
      label = d.count + ' producto' + (d.count === 1 ? '' : 's');
    } else {
      title = 'Todos los productos';
      label = d.count + ' producto' + (d.count === 1 ? '' : 's') + ' disponibles';
    }
    var html = '<div class="mb-8 flex flex-wrap items-end justify-between gap-3">' +
      '<div class="min-w-0"><span class="font-label-md font-bold text-primary">VITRINA</span>' +
      '<h2 class="mt-1 break-words font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">' + esc(title) + '</h2>' +
      '<p class="break-words text-sm text-on-surface-variant">' + esc(label) + '</p></div>';
    if (state.search || state.cat) {
      html += '<button data-clear class="inline-flex items-center gap-2 rounded-xl border border-outline-variant px-4 py-2.5 font-label-md font-bold text-on-surface transition-colors hover:bg-surface-dim">' +
        '<span class="material-symbols-outlined text-sm">close</span> Limpiar</button>';
    }
    html += '</div>';
    return html;
  }

  function paginationHTML(d) {
    if (d.count <= PAGE_SIZE) return '';
    return '<div class="pager">' +
      '<span class="text-sm text-on-surface-variant">' + d.count + ' producto' + (d.count === 1 ? '' : 's') + ' · página ' + d.page + ' de ' + d.totalPages + '</span>' +
      '<div class="flex items-center gap-2">' +
        '<button type="button" data-page="' + (d.page - 1) + '" class="pager-btn"' + (d.hasPrev ? '' : ' disabled') + '>' +
          '<span class="material-symbols-outlined text-base">chevron_left</span> Anterior</button>' +
        '<button type="button" data-page="' + (d.page + 1) + '" class="pager-btn"' + (d.hasNext ? '' : ' disabled') + '>Siguiente' +
          '<span class="material-symbols-outlined text-base">chevron_right</span></button>' +
      '</div></div>';
  }

  function render() {
    var results = $('#productosResults');
    results.innerHTML = '<div class="flex items-center justify-center gap-2 py-16 text-on-surface-variant">' +
      '<span class="material-symbols-outlined animate-spin">progress_activity</span> Cargando productos…</div>';

    fetchPage(state.page, state.cat, state.search, state.disp).then(function (d) {
      if (!d.products.length && d.count > 0 && state.page > d.totalPages) {
        state.page = d.totalPages;
        render();
        return;
      }
      if (!d.products.length) {
        var msg = state.search
          ? 'Prueba con otro término de búsqueda.'
          : (state.cat ? 'Prueba con otra categoría o vuelve a "Todos".' : 'Prueba de nuevo más tarde.');
        results.innerHTML = resultsHeader(d) + emptyState('search_off', 'Sin resultados', msg);
        return;
      }
      results.innerHTML = resultsHeader(d) +
        '<div class="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">' +
          d.products.map(productCard).join('') +
        '</div>' +
        paginationHTML(d);
    }).catch(function () {
      results.innerHTML = emptyState('error', 'No se pudo cargar el almacén', 'Intenta nuevamente en unos momentos.');
    });
  }

  function tileHTML(id, icono, nombre, count, desc, active) {
    return '<button type="button" data-cat="' + esc(id) + '" class="cat-tile' + (active ? ' active' : '') + '" title="' + esc(nombre) + '">' +
      '<span class="flex w-full min-w-0 items-center justify-between gap-2">' +
        '<span class="tile-icon flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-primary-container text-on-primary-container">' +
          '<span class="material-symbols-outlined">' + esc(icono) + '</span></span>' +
        '<span class="shrink-0 rounded-full bg-surface-dim px-2.5 py-1 text-xs font-bold text-on-surface-variant">' + count + '</span>' +
      '</span>' +
      '<span class="min-w-0">' +
        '<span class="tile-label block text-sm font-bold text-on-surface">' + esc(nombre) + '</span>' +
        (desc ? '<span class="tile-sub mt-0.5 block text-xs text-on-surface-variant">' + esc(desc) + '</span>' : '') +
      '</span>' +
    '</button>';
  }

  function buildCategorias() {
    var el = $('#productosCategorias');
    if (!el) return;
    var total = cats.reduce(function (s, c) { return s + (c.total_productos || 0); }, 0);
    var html = tileHTML('', 'grid_view', 'Todos', total, 'Ver todos los productos', state.cat === '');
    html += cats.map(function (c) {
      return tileHTML(
        String(c.id), c.icono || 'category', c.nombre, c.total_productos || 0,
        c.descripcion, String(state.cat) === String(c.id)
      );
    }).join('');
    el.innerHTML = html;
  }

  function fmtNum(n) {
    return new Intl.NumberFormat('es-DO').format(n);
  }

  function kpiCard(icon, tint, value, label, hint) {
    return '<article class="kpi-card">' +
      '<span class="kpi-icon ' + tint + '"><span class="material-symbols-outlined">' + icon + '</span></span>' +
      '<div class="min-w-0">' +
        '<p class="kpi-value">' + value + '</p>' +
        '<p class="kpi-label">' + label + '</p>' +
        (hint ? '<p class="kpi-hint">' + hint + '</p>' : '') +
      '</div></article>';
  }

  async function fetchAllProducts() {
    var out = [];
    var page = 1;
    for (;;) {
      var data = await api('/api/productos/?page=' + page);
      out = out.concat(data.results || []);
      if (!data.next) break;
      page++;
    }
    return out;
  }

  async function refreshKpis() {
    var kpiEl = $('#kpiCards');
    if (!kpiEl) return;
    var catEl = $('#kpiCategorias');
    kpiEl.innerHTML = '<div class="col-span-full flex items-center gap-2 py-6 text-sm text-on-surface-variant">' +
      '<span class="material-symbols-outlined animate-spin">progress_activity</span> Calculando resumen…</div>';
    try {
      var products = await fetchAllProducts();
      var total = products.length;
      var disponibles = 0, bajo = 0, agotados = 0;
      products.forEach(function (p) {
        if (p.agotado) {
          agotados++;
        } else {
          disponibles++;
          if (p.stock <= UMBRAL_STOCK_BAJO) bajo++;
        }
      });
      kpiEl.innerHTML =
        kpiCard('inventory_2', 'bg-primary-container text-primary', fmtNum(total), 'Total de productos', 'Registrados en el almacén') +
        kpiCard('check_circle', 'bg-success/10 text-success', fmtNum(disponibles), 'Productos disponibles', 'Con stock para venta') +
        kpiCard('warning', 'bg-warning/10 text-warning', fmtNum(bajo), 'Stock bajo', UMBRAL_STOCK_BAJO + ' unidades o menos') +
        kpiCard('remove_circle', 'bg-error/10 text-error', fmtNum(agotados), 'Productos agotados', 'Sin unidades disponibles');
      if (catEl) catEl.textContent = fmtNum(cats.length);
    } catch (e) {
      kpiEl.innerHTML = '';
      if (catEl) catEl.textContent = '—';
    }
  }

  var productoCache = {};

  async function getProducto(id) {
    if (!productoCache[id]) {
      try {
        productoCache[id] = await api('/api/productos/' + id + '/');
      } catch (e) {
        toast(apiErrorMessage(e), 'error');
        return null;
      }
    }
    return productoCache[id];
  }

  async function openProductoModal(id) {
    if (!productoCache[id]) {
      try {
        productoCache[id] = await api('/api/productos/' + id + '/');
      } catch (e) {
        toast(apiErrorMessage(e), 'error');
        return;
      }
    }
    var p = productoCache[id];
    var pricing = productPricing(p);
    var hasPrecio = pricing.final != null;
    var img = $('#prodImg');
    var fb = $('#prodImgFallback');
    if (p.imagen) {
      img.onerror = function () { img.classList.add('hidden'); if (fb) fb.classList.remove('hidden'); };
      img.src = p.imagen;
      img.classList.remove('hidden');
      if (fb) fb.classList.add('hidden');
    } else {
      img.classList.add('hidden');
      if (fb) fb.classList.remove('hidden');
    }
    img.alt = p.nombre;
    $('#prodCat').textContent = p.categoria_nombre;
    $('#prodName').textContent = p.nombre;
    $('#prodDesc').textContent = p.descripcion;
    $('#prodPrice').innerHTML = hasPrecio
      ? (pricing.enOferta
          ? '<span class="block text-sm font-semibold text-on-surface-variant line-through">' + moneyDOP(pricing.original) + '</span>' +
            '<span class="text-3xl font-extrabold tracking-tight text-primary">' + moneyDOP(pricing.final) + '</span>'
          : moneyDOP(pricing.final))
      : 'Consultar precio';
    var stockEl = $('#prodStock');
    if (p.agotado) {
      stockEl.innerHTML = '<span class="av-badge av-badge-error"><span class="material-symbols-outlined text-sm">remove_circle</span> Agotado</span><span class="text-on-surface-variant">Sin stock disponible</span>';
    } else if (p.stock <= UMBRAL_STOCK_BAJO) {
      stockEl.innerHTML = '<span class="av-badge av-badge-warning"><span class="material-symbols-outlined text-sm">warning</span> Stock bajo</span><span class="text-on-surface-variant">Solo ' + p.stock + ' unidades en almacén</span>';
    } else {
      stockEl.innerHTML = '<span class="av-badge av-badge-success"><span class="material-symbols-outlined text-sm">check_circle</span> Disponible</span><span class="text-on-surface-variant">' + p.stock + ' unidades en almacén</span>';
    }
    stockEl.className = 'mt-3 flex flex-wrap items-center gap-2 text-sm font-semibold';
    $('#prodQty').value = '1';
    $('#prodGoCart').classList.add('hidden');
    var cta = $('#prodCta');
    var esStaff = currentUser && STAFF_ROLES.indexOf(currentUser.role) >= 0;
    if (esStaff) {
      cta.classList.add('hidden');
    } else {
      cta.classList.remove('hidden');
      cta.disabled = !hasPrecio || p.agotado;
      cta.classList.toggle('opacity-40', cta.disabled);
      cta.classList.toggle('cursor-not-allowed', cta.disabled);
      cta.querySelector('span.material-symbols-outlined').textContent =
        (!hasPrecio ? 'query_stats' : (p.agotado ? 'remove_circle' : 'add_shopping_cart'));
      cta.lastChild.textContent = ' ' + (!hasPrecio ? 'Consultar precio' : (p.agotado ? 'Sin stock' : 'Agregar al carrito'));
    }
    currentProduct = p;
    openModal('producto');
  }

  /* ---------- Carrito ---------- */
  function currentQty() {
    var p = currentProduct;
    var val = parseInt($('#prodQty').value, 10) || 1;
    if (p && p.stock != null) val = Math.min(val, p.stock);
    return Math.max(1, val);
  }

  function setProdQty(v) {
    var p = currentProduct;
    var max = (p && p.stock != null) ? p.stock : 999;
    $('#prodQty').value = Math.max(1, Math.min(v, max));
  }

  $('#prodQtyMinus').addEventListener('click', function () { setProdQty(currentQty() - 1); });
  $('#prodQtyPlus').addEventListener('click', function () { setProdQty(currentQty() + 1); });
  $('#prodQty').addEventListener('change', function () { setProdQty(parseInt($('#prodQty').value, 10) || 1); });

  $('#prodCta').addEventListener('click', function () {
    if (!currentProduct) return;
    var esStaff = currentUser && STAFF_ROLES.indexOf(currentUser.role) >= 0;
    if (esStaff) { toast('Solo los clientes pueden agregar productos al carrito.', 'error'); return; }
    var p = currentProduct;
    var pricing = productPricing(p);
    if (pricing.final == null || p.agotado) return;
    var cant = currentQty();
    window.Cart.add({ id: p.id, nombre: p.nombre, imagen: p.imagen, precio: pricing.final, stock: p.stock }, cant);
    toast(cant + ' × ' + p.nombre + ' agregado al carrito.', 'success');
    $('#prodGoCart').classList.remove('hidden');
  });

  $('#prodGoCart').addEventListener('click', function () {
    window.location.href = '/carrito/';
  });

  $$('[data-open-solicitud]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      if (currentProduct) openSolicitudModal(currentProduct);
    });
  });

  /* ---------- Solicitud de compra ---------- */
  function setSolicitudMessage(text, type) {
    var el = $('#solicitudMsg');
    el.classList.remove('hidden', 'text-red-700', 'bg-red-50', 'text-emerald-700', 'bg-emerald-50');
    if (!text) {
      el.textContent = '';
      el.classList.add('hidden');
      return;
    }
    el.textContent = text;
    el.classList.add(type === 'success' ? 'text-emerald-700 bg-emerald-50' : 'text-red-700 bg-red-50');
  }

  function openSolicitudModal(product) {
    if (!product) return;
    currentProduct = product;
    $('#solProducto').textContent = product.nombre;
    $('#solCantidad').value = '1';
    $('#solNombre').value = '';
    $('#solContacto').value = '';
    $('#solObs').value = '';
    setSolicitudMessage('', '');
    openModal('solicitud');
  }

  $('#solicitudForm').addEventListener('submit', function (e) {
    e.preventDefault();
    var p = currentProduct;
    var cantidad = $('#solCantidad').value || '1';
    var nombre = $('#solNombre').value.trim();
    var contacto = $('#solContacto').value.trim();
    var obs = $('#solObs').value.trim();
    if (!p) return;
    if (!nombre || !contacto) {
      setSolicitudMessage('Completa tu nombre y un medio de contacto.', 'error');
      return;
    }
    var body = 'Hola, deseo realizar la siguiente solicitud de compra:\n\n' +
      'Producto: ' + p.nombre + '\n' +
      'Cantidad: ' + cantidad + '\n' +
      'Nombre: ' + nombre + '\n' +
      'Contacto: ' + contacto + '\n' +
      (obs ? 'Observaciones: ' + obs + '\n' : '') +
      '\nQuedo atento(a) a su respuesta.';
    var mailto = 'mailto:' + EMPRESA.email +
      '?subject=' + encodeURIComponent('Solicitud de compra: ' + p.nombre) +
      '&body=' + encodeURIComponent(body);
    window.open(mailto, '_blank');
    closeModal('solicitud');
    toast('Solicitud preparada. Se abrirá tu correo para enviarla.', 'success');
  });

  /* ---------- Actualización rápida de stock (personal) ---------- */
  var stockProduct = null;

  function setStockMsg(text, type) {
    var el = $('#stockMsg');
    el.classList.remove('hidden', 'text-red-700', 'bg-red-50', 'text-emerald-700', 'bg-emerald-50');
    if (!text) {
      el.textContent = '';
      el.classList.add('hidden');
      return;
    }
    el.textContent = text;
    el.classList.add(type === 'success' ? 'text-emerald-700 bg-emerald-50' : 'text-red-700 bg-red-50');
  }

  async function openStockModal(id) {
    var p = productoCache[id];
    if (!p) {
      try {
        p = await api('/api/productos/' + id + '/');
        productoCache[id] = p;
      } catch (err) {
        toast(apiErrorMessage(err), 'error');
        return;
      }
    }
    stockProduct = p;
    $('#stockProducto').textContent = p.nombre;
    $('#stockCantidad').value = p.stock || 0;
    $('#stockVisible').checked = !!p.disponible;
    setStockMsg('', '');
    openModal('stock');
  }

  $('#stockForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    if (!stockProduct) return;
    var stock = parseInt($('#stockCantidad').value, 10);
    if (isNaN(stock) || stock < 0) {
      setStockMsg('El stock debe ser un número mayor o igual a 0.', 'error');
      return;
    }
    var btn = e.target.querySelector('button[type=submit]');
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.classList.add('opacity-60', 'cursor-not-allowed');
    try {
      var data = await api('/api/productos/' + stockProduct.id + '/', {
        method: 'PATCH',
        body: JSON.stringify({ stock: stock, disponible: $('#stockVisible').checked }),
      });
      productoCache[data.id] = data;
      stockProduct = data;
      setStockMsg('Stock actualizado correctamente.', 'success');
      toast('Stock de ' + data.nombre + ' actualizado.', 'success');
      closeModal('stock');
      refreshKpis();
      render();
      if (currentProduct && currentProduct.id === data.id) currentProduct = data;
    } catch (err) {
      setStockMsg(apiErrorMessage(err), 'error');
    } finally {
      btn.disabled = false;
      btn.classList.remove('opacity-60', 'cursor-not-allowed');
    }
  });

  /* ---------- Eventos ---------- */
  $('#productosDisp').addEventListener('click', function (e) {
    var b = e.target.closest('[data-disp]');
    if (!b) return;
    state.disp = b.dataset.disp;
    state.page = 1;
    $$('#productosDisp .av-btn').forEach(function (x) {
      x.classList.toggle('active', x === b);
    });
    render();
  });

  $('#productosCategorias').addEventListener('click', function (e) {
    var tile = e.target.closest('[data-cat]');
    if (!tile) return;
    state.cat = tile.dataset.cat;
    state.search = '';
    state.page = 1;
    $('#productosSearch').value = '';
    buildCategorias();
    render();
    var target = $('#productosResults');
    if (target) {
      setTimeout(function () {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 60);
    }
  });

  $('#productosResults').addEventListener('click', function (e) {
    var pageBtn = e.target.closest('[data-page]');
    if (pageBtn && !pageBtn.disabled) {
      var pg = parseInt(pageBtn.dataset.page, 10);
      if (pg >= 1) {
        state.page = pg;
        render();
        var top = $('#productosResults');
        if (top) top.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      return;
    }
    var clearBtn = e.target.closest('[data-clear]');
    if (clearBtn) {
      state.search = '';
      state.cat = '';
      state.page = 1;
      $('#productosSearch').value = '';
      buildCategorias();
      render();
      return;
    }
    var stockBtn = e.target.closest('[data-stock]');
    if (stockBtn) {
      openStockModal(stockBtn.dataset.stock);
      return;
    }
    var solicitar = e.target.closest('[data-solicitar]');
    if (solicitar) {
      getProducto(solicitar.dataset.solicitar).then(function (p) {
        if (p) openSolicitudModal(p);
      });
      return;
    }
    var btn = e.target.closest('[data-producto]');
    if (btn) openProductoModal(btn.dataset.producto);
  });

  var searchInput = $('#productosSearch');
  var searchTimer = null;
  searchInput.addEventListener('input', function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () {
      state.search = searchInput.value.trim();
      state.page = 1;
      render();
    }, 300);
  });

  /* ---------- Colapsar/expandir filtros (menú sticky del almacén) ---------- */
  var filtrosToggle = $('#filtrosToggle');
  var filtrosPanel = $('#filtrosPanel');
  var filtrosChevron = $('#filtrosChevron');
  if (filtrosToggle && filtrosPanel) {
    var filtrosCollapsed = localStorage.getItem('refri_filtros_collapsed') === '1';
    function applyFiltros() {
      filtrosPanel.classList.toggle('hidden', filtrosCollapsed);
      filtrosToggle.setAttribute('aria-expanded', String(!filtrosCollapsed));
      if (filtrosChevron) filtrosChevron.textContent = filtrosCollapsed ? 'expand_more' : 'expand_less';
      filtrosToggle.title = filtrosCollapsed ? 'Mostrar filtros' : 'Ocultar filtros';
    }
    applyFiltros();
    filtrosToggle.addEventListener('click', function () {
      filtrosCollapsed = !filtrosCollapsed;
      localStorage.setItem('refri_filtros_collapsed', filtrosCollapsed ? '1' : '0');
      applyFiltros();
    });
  }

  /* ---------- Arranque ---------- */
  (function init() {
    loadCats().then(function () {
      buildCategorias();
      render();
      refreshKpis();
      var pid = new URLSearchParams(location.search).get('producto');
      if (pid) {
        var results = $('#productosResults');
        if (results) results.scrollIntoView({ behavior: 'smooth', block: 'start' });
        openProductoModal(pid);
      }
    });
  })();
})();
