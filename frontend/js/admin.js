/* ==========================================================================
   RefriMaster — Panel de administración
   SPA que consume la API REST de Django (DRF + JWT).
   - Autenticación con refresh automático
   - Navegación por secciones según rol
   - CRUD completo: clientes, técnicos, equipos, solicitudes,
     instalaciones, pagos/facturas, inventario, reportes, usuarios
   ========================================================================== */

(function () {
  'use strict';

  /* ------------------------------------------------------------------
   * Configuración
   * ------------------------------------------------------------------ */
  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 window.location.origin;
  var PAGE_SIZE = 20;
  var STAFF_ROLES = ['administrador', 'supervisor', 'tecnico', 'almacen'];
  var STOCK_MINIMO = 5;

  var S = { user: null, section: 'dashboard' };
  var listState = {};

  /* ------------------------------------------------------------------
   * Utilidades DOM
   * ------------------------------------------------------------------ */
  function $(sel, root) { return (root || document).querySelector(sel); }

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
    toast._t = setTimeout(function () { el.className = 'toast'; }, 3800);
  }

  function money(v) {
    if (v == null || v === '') return '—';
    return new Intl.NumberFormat('es-DO', {
      style: 'currency', currency: 'DOP', maximumFractionDigits: 0,
    }).format(Number(v));
  }

  function fmtDate(v) {
    if (!v) return '—';
    var d = new Date(v);
    if (isNaN(d)) return v;
    return d.toLocaleDateString('es-DO');
  }

  function fmtDT(v) {
    if (!v) return '—';
    var d = new Date(v);
    if (isNaN(d)) return v;
    return d.toLocaleString('es-DO', { dateStyle: 'short', timeStyle: 'short' });
  }

  function dtLocal(v) { return v ? String(v).slice(0, 16) : ''; }

  function initials(name) {
    name = (name || '').trim();
    if (!name) return '?';
    var parts = name.split(/\s+/);
    return (parts[0][0] || '?').toUpperCase() +
           (parts[1] ? parts[1][0].toUpperCase() : '');
  }

  /* ------------------------------------------------------------------
   * Badges por estado
   * ------------------------------------------------------------------ */
  var BADGE_MAP = {
    'pendiente': 'badge-warning',
    'aprobada': 'badge-info',
    'aprobado': 'badge-success',
    'reprogramada': 'badge-info',
    'rechazada': 'badge-error',
    'rechazado': 'badge-error',
    'reembolsado': 'badge-neutral',
    'completada': 'badge-success',
    'asignada': 'badge-primary',
    'en_proceso': 'badge-primary',
    'finalizada': 'badge-success',
    'confirmado': 'badge-primary',
    'preparando': 'badge-info',
    'enviado': 'badge-info',
    'entregado': 'badge-success',
    'cancelada': 'badge-error',
    'programada': 'badge-info',
    'en_curso': 'badge-primary',
    'realizada': 'badge-success',
    'vencida': 'badge-neutral',
    'pagado': 'badge-success',
    'fallido': 'badge-error',
    'disponible': 'badge-success',
    'instalado': 'badge-primary',
    'averiado': 'badge-error',
    'en_reparacion': 'badge-warning',
    'retirado': 'badge-neutral',
    'entrada': 'badge-success',
    'salida': 'badge-warning',
    'ajuste': 'badge-info',
    'baja': 'badge-neutral',
    'media': 'badge-primary',
    'alta': 'badge-warning',
    'urgente': 'badge-error',
    'administrador': 'badge-error',
    'supervisor': 'badge-warning',
    'tecnico': 'badge-primary',
    'almacen': 'badge-info',
    'cliente': 'badge-neutral',
  };

  function estadoBadge(value, label) {
    return '<span class="badge ' + (BADGE_MAP[value] || 'badge-neutral') + '">' +
           esc(label || value) + '</span>';
  }

  /* ------------------------------------------------------------------
   * Sesión y API
   * ------------------------------------------------------------------ */
  function clearSession() {
    localStorage.removeItem('refri_access');
    localStorage.removeItem('refri_refresh');
    localStorage.removeItem('refri_user');
  }

  function forceLogin() {
    clearSession();
    window.location.href = '/';
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
      } else {
        forceLogin();
        throw new Error('Sesión expirada. Vuelve a iniciar sesión.');
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

  async function fetchAll(url, params) {
    var out = [];
    var page = 1;
    while (true) {
      var sep = url.indexOf('?') >= 0 ? '&' : '?';
      var data = await api(url + sep + 'page=' + page + (params ? '&' + params : ''));
      var results = Array.isArray(data) ? data : (data.results || []);
      out = out.concat(results);
      var next = Array.isArray(data) ? null : data.next;
      if (!next || !results.length) break;
      page += 1;
    }
    return out;
  }

  function apiErrorMessage(err) {
    var d = err && err.data;
    if (!d) return 'No fue posible completar la petición. Verifica tu conexión.';
    function flat(v) {
      if (typeof v === 'string' && v) return v;
      if (Array.isArray(v)) return flat(v[0]);
      if (v && typeof v === 'object') return flat(v.detail || v.message || Object.values(v)[0]);
      return '';
    }
    var msg = flat(d);
    if (msg) return msg;
    return 'No fue posible completar la petición. Verifica tu conexión.';
  }

  function isAdmin() { return S.user && S.user.role === 'administrador'; }
  function isSupervisor() { return S.user && S.user.role === 'supervisor'; }
  function canDelete() { return isAdmin() || isSupervisor(); }
  function canManageAlmacen() { return isAdmin() || S.user.role === 'almacen'; }

  /* ------------------------------------------------------------------
   * NOTIFICACIONES (RF-24)
   * ------------------------------------------------------------------ */
  var NOTIF_ICON = {
    ASIGNACION: 'handyman',
    CAMBIO_ESTADO: 'swap_horiz',
    FINALIZACION: 'task_alt',
    MANTENIMIENTO: 'event_available',
    SISTEMA: 'notifications',
  };

  function notifItemHTML(n) {
    var ico = NOTIF_ICON[n.tipo] || 'notifications';
    return '<div class="notif-item' + (n.leida ? '' : ' unread') + '" data-notif="' + n.id + '">' +
      '<span class="notif-ico tipo-' + esc(n.tipo) + '"><span class="material-symbols-outlined">' + ico + '</span></span>' +
      '<div class="min-w-0 flex-1">' +
        '<div class="text-sm font-semibold text-on-surface">' + esc(n.titulo) + '</div>' +
        '<div class="mt-0.5 line-clamp-2 text-xs text-on-surface-variant">' + esc(n.mensaje) + '</div>' +
        '<div class="mt-1 text-[10px] text-on-surface-variant">' + fmtDT(n.fecha) + '</div>' +
      '</div></div>';
  }

  async function refreshNotifBadge() {
    try {
      var r = await api('/api/notificaciones/no_leidas/');
      var badge = $('#notifBadge');
      var count = (r && typeof r.count === 'number') ? r.count : 0;
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.toggle('hidden', count <= 0);
    } catch (e) { /* silencioso */ }
  }

  async function openNotifList() {
    var list = $('#notifList');
    list.innerHTML = '<div class="p-6 text-center text-sm text-on-surface-variant">Cargando…</div>';
    try {
      var r = await api('/api/notificaciones/?ordering=-fecha');
      var items = r.results || [];
      list.innerHTML = items.length
        ? items.map(notifItemHTML).join('')
        : '<div class="p-8 text-center"><span class="material-symbols-outlined text-3xl text-outline">notifications_none</span>' +
          '<p class="mt-2 text-sm text-on-surface-variant">Sin notificaciones.</p></div>';
    } catch (e) {
      list.innerHTML = '<div class="p-6 text-center text-sm text-error">No se pudieron cargar.</div>';
    }
  }

  function setupNotificaciones() {
    var btn = $('#notifBtn');
    var drop = $('#notifDropdown');
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var wasHidden = drop.classList.contains('hidden');
      drop.classList.toggle('hidden');
      if (wasHidden) openNotifList();
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('#notifWrap')) drop.classList.add('hidden');
    });
    $('#notifList').addEventListener('click', function (e) {
      var item = e.target.closest('[data-notif]');
      if (!item) return;
      var id = item.dataset.notif;
      api('/api/notificaciones/' + id + '/marcar_leida/', { method: 'POST', body: '{}' })
        .then(function () { refreshNotifBadge(); })
        .catch(function () { /* silencioso */ });
      item.classList.remove('unread');
    });
    $('#notifAllRead').addEventListener('click', function () {
      api('/api/notificaciones/marcar_todas_leidas/', { method: 'POST', body: '{}' })
        .then(function () {
          $$('#notifList .notif-item').forEach(function (el) { el.classList.remove('unread'); });
          refreshNotifBadge();
          toast('Todas las notificaciones fueron marcadas como leídas.', 'success');
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    });
    refreshNotifBadge();
    setInterval(refreshNotifBadge, 60000);
  }


  /* ------------------------------------------------------------------
   * Exportar reportes (PDF / Excel)
   * ------------------------------------------------------------------ */
  function exportarReporte(formato) {
    var tipoSel = $('#exportTipo');
    var tipo = tipoSel ? tipoSel.value : 'general';
    var token = localStorage.getItem('refri_access');
    fetch(API_BASE + '/api/dashboard/exportar/?formato=' + encodeURIComponent(formato) +
          '&tipo=' + encodeURIComponent(tipo), {
      headers: { 'Authorization': 'Bearer ' + token },
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().catch(function () { return null; })
            .then(function (d) { throw new Error((d && (d.detail || d.message)) || 'No se pudo exportar.'); });
        }
        return res.blob();
      })
      .then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'reporte_' + tipo + '.' + (formato === 'xlsx' ? 'xlsx' : 'pdf');
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        toast('Reporte exportado.', 'success');
      })
      .catch(function (err) { toast(err.message || 'No se pudo exportar.', 'error'); });
  }

  /* ------------------------------------------------------------------
   * Construcción de UI reutilizable
   * ------------------------------------------------------------------ */
  function tableRows(columns, items) {
    if (!items || !items.length) {
      return '<tr><td colspan="' + columns.length + '">' +
              '<div class="empty-state"><span class="material-symbols-outlined">inbox</span>' +
              '<p>Sin registros para mostrar.</p></div></td></tr>';
    }
    return items.map(function (item) {
      var rowId = item && item.id != null ? ' data-id="' + esc(item.id) + '"' : '';
      return '<tr' + rowId + '>' + columns.map(function (c) {
        var v = c.render ? c.render(item) : item[c.key];
        return '<td>' + (v == null ? '—' : v) + '</td>';
      }).join('') + '</tr>';
    }).join('');
  }

  function buildTable(columns, items) {
    var html = '<div class="overflow-x-auto"><table class="adm-table"><thead><tr>';
    html += columns.map(function (c) { return '<th>' + esc(c.label) + '</th>'; }).join('');
    html += '</tr></thead><tbody data-list-body>' + tableRows(columns, items) + '</tbody></table></div>';
    return html;
  }

  function paginationHTML(state, data) {
    if (!data || !data.count || data.count <= PAGE_SIZE) return '';
    var pages = Math.ceil(data.count / PAGE_SIZE);
    var html = '<div class="flex flex-wrap items-center justify-between gap-2 border-t border-outline-variant px-4 py-3">';
    html += '<span class="text-xs text-on-surface-variant">' + data.count +
            ' registros · página ' + state.page + ' de ' + pages + '</span>';
    html += '<div class="flex items-center gap-2">';
    html += '<button class="btn btn-ghost" data-action="page" data-page="prev"' +
            (data.previous ? '' : ' disabled') + '>Anterior</button>';
    html += '<button class="btn btn-ghost" data-action="page" data-page="next"' +
            (data.next ? '' : ' disabled') + '>Siguiente</button>';
    html += '</div></div>';
    return html;
  }

  function toolbarHTML(opts) {
    var html = '<div class="flex flex-col gap-3 sm:flex-row sm:items-center">';
    html += '<div class="relative w-full sm:max-w-xs">';
    html += '<span data-search-icon class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 cursor-pointer text-sm text-on-surface-variant">search</span>';
    html += '<input data-search class="adm-input pl-9" placeholder="' + esc(opts.placeholder || 'Buscar…') +
            '" value="' + esc(opts.search || '') + '">';
    html += '<div data-search-dropdown class="absolute left-0 top-full z-50 mt-1 hidden w-full max-h-64 overflow-y-auto rounded-xl border border-outline-variant bg-white shadow-lg"></div>';
    html += '</div>';
    if (opts.filters && opts.filters.length) {
      html += '<div class="flex flex-wrap items-center gap-2">';
      opts.filters.forEach(function (f) {
        html += '<select data-filter="' + esc(f.name) + '" class="adm-select w-auto">';
        html += '<option value="">' + esc(f.label) + '</option>';
        (f.options || []).forEach(function (o) {
          html += '<option value="' + esc(o.value) + '"' +
                  (String(o.value) === String(f.value || '') ? ' selected' : '') + '>' +
                  esc(o.label) + '</option>';
        });
        html += '</select>';
      });
      html += '</div>';
    }
    if (opts.buttons && opts.buttons.length) {
      html += '<div class="flex flex-wrap items-center gap-2 sm:ml-auto">';
      opts.buttons.forEach(function (b) {
        html += '<button data-action="' + esc(b.action) + '" class="btn ' + (b.variant || 'btn-primary') + '">';
        if (b.icon) html += '<span class="material-symbols-outlined text-sm">' + esc(b.icon) + '</span>';
        html += esc(b.label) + '</button>';
      });
      html += '</div>';
    }
    html += '</div>';
    return html;
  }

  function viewShell(opts) {
    return '<div class="panel-card">' +
           '<div class="border-b border-outline-variant p-4">' + toolbarHTML(opts.toolbar) + '</div>' +
           buildTable(opts.columns, opts.items) +
           paginationHTML(opts.state, opts.data) +
           '</div>';
  }

  function actionBtns(item, opts) {
    var html = '<div class="flex items-center gap-1">';
    (opts || []).forEach(function (a) {
      if (a.kind === 'icon') {
        var cls = 'btn btn-ghost p-1.5';
        var iconCls = 'text-base';
        if (a.danger) { cls += ' hover:bg-error/10'; iconCls += ' text-error'; }
        else if (a.color === 'primary') { cls += ' hover:bg-primary/10'; iconCls += ' text-primary'; }
        html += '<button class="' + cls + '" data-action="' + esc(a.action) +
                '" data-id="' + esc(item.id) + '" title="' + esc(a.title || a.action) + '">' +
                '<span class="material-symbols-outlined ' + iconCls + '">' + esc(a.icon) + '</span></button>';
      } else {
        html += '<button class="btn btn-ghost" data-action="' + esc(a.action) +
                '" data-id="' + esc(item.id) + '">' + esc(a.label) + '</button>';
      }
    });
    html += '</div>';
    return html;
  }

  /* ------------------------------------------------------------------
   * Formularios
   * ------------------------------------------------------------------ */
  function fieldHTML(f) {
    var req = f.required ? ' required' : '';
    var cls = 'adm-input';
    var val = f.value == null ? '' : f.value;
    var hint = f.hint ? '<p class="mt-1 text-xs text-on-surface-variant">' + esc(f.hint) + '</p>' : '';
    var label = '<label class="field-label" for="f_' + esc(f.name) + '">' + esc(f.label) +
                (f.required ? ' <span class="text-error">*</span>' : '') + '</label>';
    var span = f.span ? ' sm:col-span-' + f.span : '';
    var inner;

    if (f.type === 'divider') {
      return '<div class="col-span-full mt-1 border-t border-outline-variant pt-3">' +
             '<p class="font-semibold text-sm text-on-surface">' + esc(f.label) + '</p></div>';
    } else if (f.type === 'select') {
      inner = '<select id="f_' + esc(f.name) + '" name="' + esc(f.name) + '" class="adm-select"' + req +
              (f.disabled ? ' disabled' : '') + '>' +
              '<option value="">— Selecciona —</option>' +
              (f.options || []).map(function (o) {
                return '<option value="' + esc(o.value) + '"' +
                       (String(o.value) === String(val) ? ' selected' : '') + '>' +
                       esc(o.label) + '</option>';
              }).join('') + '</select>';
    } else if (f.type === 'textarea') {
      inner = '<textarea id="f_' + esc(f.name) + '" name="' + esc(f.name) + '" class="adm-textarea"' +
              req + ' placeholder="' + esc(f.placeholder || '') + '">' + esc(val) + '</textarea>';
    } else if (f.type === 'checkbox') {
      inner = '<label class="flex cursor-pointer items-center gap-2">' +
              '<input type="checkbox" name="' + esc(f.name) + '"' + (val ? ' checked' : '') +
              (f.disabled ? ' disabled' : '') + ' class="h-4 w-4 accent-primary">' +
              '<span class="text-sm text-on-surface">' + esc(f.label) + '</span></label>';
      return '<div class="sm:col-span-' + (f.span || 2) + '">' + inner + hint + '</div>';
    } else if (f.type === 'image') {
      var has = !!val;
      inner =
        '<div class="flex items-start gap-4">' +
          '<div id="prev_' + esc(f.name) + '" class="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-outline-variant bg-surface-dim">' +
            (has ? '<img src="' + esc(val) + '" alt="Vista previa" class="h-full w-full object-cover" loading="lazy">' :
                   '<span class="material-symbols-outlined text-3xl text-on-surface-variant">image</span>') +
          '</div>' +
          '<div class="flex flex-col gap-2">' +
            '<input type="file" id="file_' + esc(f.name) + '" accept="image/*" class="hidden">' +
            '<button type="button" id="btnSel_' + esc(f.name) + '" class="btn btn-primary inline-flex w-fit items-center gap-2">' +
              '<span class="material-symbols-outlined text-sm">' + (has ? 'sync_alt' : 'upload_file') + '</span>' +
              (has ? 'Cambiar imagen' : 'Seleccionar imagen') +
            '</button>' +
            '<button type="button" id="btnRm_' + esc(f.name) + '" class="btn btn-ghost inline-flex w-fit items-center gap-2' + (has ? '' : ' hidden') + '">' +
              '<span class="material-symbols-outlined text-sm">delete</span>Quitar imagen</button>' +
            '<input id="f_' + esc(f.name) + '" name="' + esc(f.name) + '" type="text" value="' + esc(val) +
              '" readonly class="adm-input text-xs" placeholder="Sin imagen seleccionada">' +
          '</div>' +
        '</div>';
      return '<div' + span + '>' + label + inner + hint + '</div>';
    } else {
      inner = '<input id="f_' + esc(f.name) + '" name="' + esc(f.name) + '" type="' + (f.type || 'text') +
              '" class="' + cls + '" value="' + esc(val) + '" placeholder="' + esc(f.placeholder || '') + '"' +
              req + (f.step ? ' step="' + f.step + '"' : '') + (f.min != null ? ' min="' + f.min + '"' : '') +
              (f.disabled ? ' disabled' : '') + '>';
    }

    return '<div' + span + '>' + label + inner + hint + '</div>';
  }

  function formHTML(fields) {
    return '<form id="modalForm" class="grid grid-cols-1 gap-3 sm:grid-cols-2">' +
           fields.map(fieldHTML).join('') + '</form>';
  }

  function getFormData(form, nullables) {
    var data = {};
    nullables = nullables || [];
    form.querySelectorAll('[name]').forEach(function (f) {
      var name = f.name;
      if (f.disabled) return;
      if (f.type === 'checkbox') { data[name] = f.checked; return; }
      var v = f.value;
      if (nullables.indexOf(name) >= 0 && (v === '' || v == null)) { data[name] = null; return; }
      if (f.type === 'number') { data[name] = v === '' ? null : Number(v); return; }
      data[name] = v;
    });
    return data;
  }

  function wireImageUpload(name) {
    // Conecta un campo de tipo 'image' (campo file + botón + vista previa):
    // al elegir un archivo lo sube a la API y guarda la URL en el campo
    // oculto (readonly) que se envía con el formulario.
    var fileInput = $('#file_' + name);
    if (!fileInput) return;
    var hidden = $('#f_' + name);
    var prev = $('#prev_' + name);
    var btnSel = $('#btnSel_' + name);
    var btnRm = $('#btnRm_' + name);

    function render(url) {
      hidden.value = url || '';
      prev.innerHTML = url
        ? '<img src="' + esc(url) + '" alt="Vista previa" class="h-full w-full object-cover" loading="lazy">'
        : '<span class="material-symbols-outlined text-3xl text-on-surface-variant">image</span>';
      if (btnSel) {
        btnSel.innerHTML = url
          ? '<span class="material-symbols-outlined text-sm">sync_alt</span>Cambiar imagen'
          : '<span class="material-symbols-outlined text-sm">upload_file</span>Seleccionar imagen';
        btnSel.disabled = false;
      }
      if (btnRm) btnRm.classList.toggle('hidden', !url);
    }

    if (btnSel) btnSel.addEventListener('click', function () { fileInput.click(); });

    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file) return;
      if (!/^image\//.test(file.type)) { toast('Selecciona un archivo de imagen válido.', 'error'); fileInput.value = ''; return; }
      if (file.size > 5 * 1024 * 1024) { toast('La imagen supera los 5 MB.', 'error'); fileInput.value = ''; return; }
      prev.innerHTML = '<img src="' + (window.URL || window.webkitURL).createObjectURL(file) +
                       '" alt="Vista previa" class="h-full w-full object-cover">';
      if (btnSel) {
        btnSel.disabled = true;
        btnSel.innerHTML = '<span class="material-symbols-outlined text-sm">progress_activity</span>Subiendo…';
      }
      var fd = new FormData();
      fd.append('imagen', file);
      apiUpload('/api/productos/subir-imagen/', fd)
        .then(function (res) {
          render(res.url || res.imagen || '');
          toast('Imagen subida correctamente.', 'success');
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); render(hidden.value); fileInput.value = ''; })
        .then(function () { if (btnSel) btnSel.disabled = false; });
    });

    if (btnRm) btnRm.addEventListener('click', function () {
      fileInput.value = '';
      render('');
    });
  }

  function optList(items, valueKey, labelKey) {
    return (items || []).map(function (i) {
      var label = typeof labelKey === 'function' ? labelKey(i) : (i ? i[labelKey] : '');
      return { value: i ? i[valueKey] : '', label: (label == null || label === '') ? String(i ? i[valueKey] : '') : label };
    });
  }

  /* ------------------------------------------------------------------
   * Modales
   * ------------------------------------------------------------------ */
  function closeModal() {
    var root = $('#modalRoot');
    root.innerHTML = '';
  }

  function clearBadDatetime(el) {
    if (el && el.type === 'datetime-local' && el.validity && el.validity.badInput) {
      el.value = '2000-01-01T00:00';
      el.value = '';
    }
  }

  function openModal(title, bodyHTML, opts) {
    opts = opts || {};
    closeModal();
    var root = $('#modalRoot');
    var wrap = document.createElement('div');
    wrap.className = 'modal-backdrop';
    wrap.innerHTML =
      '<div class="modal-panel" style="max-width:' + (opts.width || '640px') + '">' +
        '<div class="flex items-center justify-between border-b border-outline-variant px-5 py-4">' +
          '<h2 class="text-lg font-bold tracking-tight text-on-surface">' + esc(title) + '</h2>' +
          '<button class="rounded-lg p-1 text-on-surface-variant hover:bg-surface-dim" data-close>' +
            '<span class="material-symbols-outlined">close</span></button>' +
        '</div>' +
        '<div class="max-h-[72vh] overflow-y-auto px-5 py-4">' + bodyHTML + '</div>' +
        (opts.footer ? '<div class="flex justify-end gap-2 border-t border-outline-variant px-5 py-4">' +
          opts.footer + '</div>' : '') +
      '</div>';
    wrap.addEventListener('click', function (e) {
      if (e.target === wrap) closeModal();
    });
    wrap.addEventListener('click', function (e) {
      var c = e.target.closest('[data-close]');
      if (c) closeModal();
    });
    wrap.addEventListener('invalid', function (e) {
      var el = e.target;
      if (el && el.type === 'datetime-local' && el.validity && el.validity.badInput) {
        e.preventDefault();
        clearBadDatetime(el);
      }
    }, true);
    root.appendChild(wrap);
    var first = wrap.querySelector('input,select,textarea');
    if (first) setTimeout(function () { first.focus(); }, 40);
    return wrap;
  }

  function modalFooter(cancelLabel, submitLabel, submitClass) {
    return '<button type="button" class="btn btn-ghost" data-close>' + esc(cancelLabel || 'Cancelar') +
           '</button>' +
           '<button type="submit" form="modalForm" class="btn ' + (submitClass || 'btn-primary') + '">' +
           esc(submitLabel || 'Guardar') + '</button>';
  }

  function setBusy(btn, busy) {
    if (!btn) return;
    if (busy) {
      btn.dataset.label = btn.textContent;
      btn.textContent = 'Procesando…';
      btn.disabled = true;
    } else {
      btn.textContent = btn.dataset.label || btn.textContent;
      btn.disabled = false;
    }
  }

  /* ------------------------------------------------------------------
   * Estado de listas y carga
   * ------------------------------------------------------------------ */
  function st(key, defaults) {
    return listState[key] || (listState[key] = Object.assign({ page: 1, search: '' }, defaults));
  }

  async function loadList(url, state, params) {
    var qs = ['page=' + (state.page || 1)];
    if (state.search) qs.push('search=' + encodeURIComponent(state.search));
    if (params) {
      Object.keys(params).forEach(function (k) {
        if (state[k]) qs.push(k + '=' + encodeURIComponent(state[k]));
      });
    }
    return api(url + (url.indexOf('?') >= 0 ? '&' : '?') + qs.join('&'));
  }

  function setViewLoading() {
    $('#view').innerHTML =
      '<div class="space-y-4"><div class="skeleton h-12"></div>' +
      '<div class="skeleton h-56"></div><div class="skeleton h-56"></div></div>';
  }

  function setViewError(msg) {
    $('#view').innerHTML =
      '<div class="panel-card p-10 text-center">' +
      '<span class="material-symbols-outlined text-5xl text-error">error</span>' +
      '<p class="mt-3 font-semibold text-on-surface">No se pudieron cargar los datos</p>' +
      '<p class="mt-1 text-sm text-on-surface-variant">' + esc(msg) + '</p>' +
      '<button class="btn btn-primary mt-4" data-action="retry">Reintentar</button></div>';
  }

  /* ------------------------------------------------------------------
   * DASHBOARD
   * ------------------------------------------------------------------ */
  function statCard(label, value, icon, colorClass) {
    return '<div class="stat-card">' +
      '<div class="flex items-center justify-between">' +
        '<span class="text-xs font-semibold text-on-surface-variant">' + esc(label) + '</span>' +
        '<span class="material-symbols-outlined ' + (colorClass || 'text-primary') + '">' + esc(icon) + '</span>' +
      '</div>' +
      '<div class="stat-value mt-2 font-bold tracking-tight text-on-surface">' + value + '</div>' +
    '</div>';
  }

  /* ------------------------------------------------------------------
   * Módulos agrupados del Dashboard (accesos rápidos navegables)
   * ------------------------------------------------------------------ */
  var DASH_GROUPS = [
    {
      title: 'Operaciones',
      icon: 'bolt',
      subtitle: 'Instalaciones, servicios, agenda y mantenimientos',
      modules: [
        { key: 'instalaciones', label: 'Instalaciones', icon: 'home_repair_service', section: 'instalaciones', preset: { estado: '' } },
        { key: 'instalaciones_pendientes', label: 'Instalaciones pendientes', icon: 'schedule', section: 'instalaciones', preset: { estado: 'pendiente' } },
        { key: 'instalaciones_realizadas', label: 'Instalaciones realizadas', icon: 'task_alt', section: 'instalaciones', preset: { estado: 'finalizada' } },
        { key: 'servicios_pendientes', label: 'Servicios pendientes', icon: 'pending_actions', section: 'servicios', preset: { estado: 'pendiente' } },
        { key: 'servicios_proceso', label: 'Servicios en proceso', icon: 'autorenew', section: 'servicios', preset: { estado: 'en_proceso' } },
        { key: 'servicios_completados', label: 'Servicios completados', icon: 'check_circle', section: 'servicios', preset: { estado: 'finalizada' } },
        { key: 'agenda', label: 'Agenda', icon: 'calendar_month', section: 'agenda', preset: {} },
        { key: 'mantenimientos_proximos', label: 'Mantenimientos próximos', icon: 'event_available', section: 'mantenimientos', preset: { vencidos: '', proximos: '1' } },
        { key: 'mantenimientos_vencidos', label: 'Mantenimientos vencidos', icon: 'event_busy', section: 'mantenimientos', preset: { vencidos: '1', proximos: '' } },
      ],
    },
    {
      title: 'Inventario y equipos',
      icon: 'inventory_2',
      subtitle: 'Equipos, materiales, stock y vitrina',
      modules: [
        { key: 'equipos', label: 'Equipos', icon: 'ac_unit', section: 'equipos', preset: { estado: '' } },
        { key: 'materiales', label: 'Materiales', icon: 'inventory_2', section: 'inventario', preset: { tab: 'materiales', stock_bajo: '' } },
        { key: 'stock_bajo', label: 'Stock bajo', icon: 'warning', section: 'inventario', preset: { tab: 'materiales', stock_bajo: '1' } },
        { key: 'almacen', label: 'Almacén', icon: 'storefront', section: 'almacen', preset: { tab: 'productos' } },
        { key: 'historial_equipos', label: 'Historial de equipos', icon: 'history', section: 'equipos', preset: { estado: '' } },
        { key: 'control_materiales', label: 'Control de materiales', icon: 'handyman', section: 'inventario', preset: { tab: 'movimientos' },
          allowed: function () { return canDelete() || S.user.role === 'almacen'; } },
      ],
    },
    {
      title: 'Administración y finanzas',
      icon: 'manage_accounts',
      subtitle: 'Clientes, personal, pagos, reportes y calificaciones',
      modules: [
        { key: 'clientes', label: 'Clientes', icon: 'group', section: 'clientes', preset: { tipo: '' } },
        { key: 'tecnicos', label: 'Técnicos', icon: 'engineering', section: 'tecnicos', preset: { disponible: '' } },
        { key: 'usuarios', label: 'Usuarios', icon: 'manage_accounts', section: 'usuarios', preset: { role: '' } },
        { key: 'pagos_recibidos', label: 'Pagos recibidos', icon: 'payments', section: 'pagos', preset: { tab: 'pagos', estado: 'pagado' } },
        { key: 'reportes', label: 'Reportes', icon: 'bar_chart', section: 'reportes', preset: {} },
        { key: 'calificaciones', label: 'Calificaciones', icon: 'star', section: 'evaluaciones', preset: {} },
      ],
    },
  ];

  function findModule(key) {
    var found = null;
    DASH_GROUPS.some(function (g) {
      return g.modules.some(function (m) {
        if (m.key === key) { found = m; return true; }
        return false;
      });
    });
    return found;
  }

  function goToModule(key) {
    var mod = findModule(key);
    if (!mod) return;
    var sec = SECTIONS[mod.section];
    if (!sec || sec.roles.indexOf(S.user.role) < 0 || (mod.allowed && !mod.allowed())) {
      toast('No tienes permisos para acceder a este módulo.', 'error');
      return;
    }
    if (mod.preset) {
      var s = st(mod.section, {});
      Object.keys(mod.preset).forEach(function (k) { s[k] = mod.preset[k]; });
      s.page = 1;
      if (mod.preset.search === undefined) s.search = '';
    }
    go(mod.section);
  }

  function moduleGroupHTML(g) {
    var mods = g.modules.filter(function (m) {
      var sec = SECTIONS[m.section];
      if (!sec || sec.roles.indexOf(S.user.role) < 0) return false;
      if (m.allowed && !m.allowed()) return false;
      return true;
    });
    if (!mods.length) return '';
    return '<div class="panel-card p-5">' +
      '<div class="flex items-center gap-2">' +
        '<span class="material-symbols-outlined text-primary">' + esc(g.icon) + '</span>' +
        '<div>' +
          '<h3 class="text-sm font-bold tracking-tight text-on-surface">' + esc(g.title) + '</h3>' +
          (g.subtitle ? '<p class="text-xs text-on-surface-variant">' + esc(g.subtitle) + '</p>' : '') +
        '</div>' +
      '</div>' +
      '<div class="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">' +
        mods.map(function (m) {
          return '<button type="button" data-module="' + esc(m.key) + '" class="module-card" title="Ir a ' + esc(m.label) + '">' +
            '<span class="module-card-icon"><span class="material-symbols-outlined">' + esc(m.icon) + '</span></span>' +
            '<span class="module-card-label">' + esc(m.label) + '</span>' +
            '<span class="material-symbols-outlined module-card-arrow">arrow_forward</span>' +
          '</button>';
        }).join('') +
      '</div>' +
    '</div>';
  }

  function barChartHTML(title, rows) {
    var max = 1;
    rows.forEach(function (r) {
      var n = Number(r.value) || 0;
      if (n > max) max = n;
    });
    var html = '<div class="panel-card p-5">' +
      '<h3 class="text-sm font-bold tracking-tight text-on-surface">' + esc(title) + '</h3>' +
      '<div class="mt-4 space-y-3">';
    if (!rows.length) {
      html += '<div class="flex flex-col items-center justify-center py-8 text-center">' +
              '<span class="material-symbols-outlined text-3xl text-outline">monitoring</span>' +
              '<p class="mt-2 text-sm text-on-surface-variant">Sin datos para este período.</p></div>';
    } else {
      rows.slice(-12).forEach(function (r) {
        var pct = Math.round((Number(r.value) || 0) / max * 100);
        html += '<div><div class="flex items-center justify-between text-xs">' +
                '<span class="font-medium text-on-surface-variant">' + esc(r.label) + '</span>' +
                '<span class="font-semibold text-on-surface">' + r.value + '</span></div>' +
                '<div class="bar-track mt-1"><div class="bar-fill" style="width:' + pct + '%"></div></div></div>';
      });
    }
    html += '</div></div>';
    return html;
  }

  async function renderDashboard() {
    setViewLoading();
    var d;
    try {
      d = await api('/api/dashboard/');
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }

    var html = '<div class="space-y-5">';

    html += '<div class="flex flex-wrap items-center gap-2">' +
      '<span class="text-sm font-semibold text-on-surface">Exportar reporte:</span>' +
      '<select id="exportTipo" class="adm-select w-auto">' +
        '<option value="general">General</option><option value="instalaciones">Instalaciones</option>' +
        '<option value="servicios">Servicios</option><option value="materiales">Materiales</option>' +
        (S.user.role === 'tecnico' ? '' : '<option value="pagos">Pagos</option>') +
      '</select>' +
      '<button data-export="pdf" class="btn btn-ghost"><span class="material-symbols-outlined text-sm">picture_as_pdf</span>PDF</button>' +
      '<button data-export="xlsx" class="btn btn-ghost"><span class="material-symbols-outlined text-sm">table_view</span>Excel</button>' +
    '</div>';

    html += '<div class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">';
    html += statCard('Clientes', d.total_clientes, 'group');
    html += statCard('Técnicos', d.total_tecnicos, 'engineering', 'text-secondary');
    html += statCard('Técnicos disponibles', d.tecnicos_disponibles, 'verified_user', 'text-success');
    html += statCard('Técnicos ocupados', d.tecnicos_ocupados, 'engineering', 'text-warning');
    html += statCard('Equipos', d.total_equipos, 'ac_unit');
    html += statCard('Instalaciones', d.total_instalaciones, 'home_repair_service');
    html += statCard('Usuarios', d.total_usuarios, 'manage_accounts', 'text-on-surface-variant');
    html += statCard('Instalaciones realizadas', d.instalaciones_realizadas, 'task_alt', 'text-success');
    html += statCard('Instalaciones pendientes', d.instalaciones_pendientes, 'schedule', 'text-warning');
    html += statCard('Servicios pendientes', d.servicios_pendientes, 'pending_actions', 'text-warning');
    html += statCard('Servicios en proceso', d.servicios_en_proceso, 'autorenew', 'text-secondary');
    html += statCard('Servicios completados', d.servicios_completados, 'check_circle', 'text-success');
    if (S.user.role !== 'tecnico') {
      html += statCard('Ventas', money(d.ventas), 'trending_up', 'text-success');
      html += statCard('Pagos pendientes', money(d.pagos_pendientes), 'hourglass_empty', 'text-warning');
    }
    html += statCard('Mantenimientos próximos', d.mantenimientos_proximos, 'event_available', 'text-secondary');
    html += statCard('Mantenimientos vencidos', d.mantenimientos_vencidos, 'event_busy',
                     d.mantenimientos_vencidos ? 'text-error' : 'text-on-surface-variant');
    html += statCard('Materiales', d.materiales_count, 'inventory_2');
    html += statCard('Stock bajo', d.materiales_stock_bajo, 'warning',
                     d.materiales_stock_bajo ? 'text-error' : 'text-success');
    if (S.user.role !== 'tecnico') {
      html += statCard('Pagos recibidos', money(d.total_pagos), 'payments', 'text-success');
    }
    html += statCard('Calificación promedio', d.calificacion_promedio != null
                     ? Number(d.calificacion_promedio).toFixed(1) : '—', 'star', 'text-warning');
    html += '</div>';

    html += DASH_GROUPS.map(moduleGroupHTML).join('');

    html += '<div class="grid gap-4 xl:grid-cols-2">';
    html += barChartHTML('Servicios por mes', (d.servicios_por_mes || []).map(function (r) {
      return { label: r.mes, value: r.total };
    }));
    html += barChartHTML('Instalaciones por mes', (d.instalaciones_por_mes || []).map(function (r) {
      return { label: r.mes, value: r.total };
    }));
    html += '</div>';

    var porTecnico = [];
    try {
      porTecnico = await api('/api/dashboard/servicios-por-tecnico/');
    } catch (e) { porTecnico = []; }

    html += '<div class="grid gap-4 xl:grid-cols-2">';
    html += barChartHTML('Ordenes por técnico', porTecnico.map(function (t) {
      return { label: t.nombre || 'Técnico', value: t.total_ordenes };
    }));
    html += '<div class="panel-card p-5"><h3 class="text-sm font-bold tracking-tight text-on-surface">' +
            'Materiales con stock bajo</h3><div class="mt-4">' +
            buildTable([
              { key: 'codigo', label: 'Código' },
              { key: 'nombre', label: 'Material' },
              { key: 'cantidad', label: 'Disponible', render: function (m) { return money(m.cantidad_disponible); } },
              { key: 'minimo', label: 'Mínimo', render: function (m) { return money(m.stock_minimo); } },
            ], (d.materiales_stock_bajo_list || [])) +
            '</div></div>';
    html += '</div>';

    html += '</div>';
    $('#view').innerHTML = html;
    $$('#view [data-export]').forEach(function (b) {
      b.addEventListener('click', function () { exportarReporte(b.dataset.export); });
    });
  }

  /* ------------------------------------------------------------------
   * CLIENTES
   * ------------------------------------------------------------------ */
  async function renderClientes() {
    sdCache = {};
    cssClear('clientes');   // lista completa fresca
    setViewLoading();
    var state = st('clientes', { tipo: '', tipo_documento: '' });
    var qs = ['page=' + (state.page || 1)];
    if (state.search) qs.push('search=' + encodeURIComponent(state.search));
    if (state.tipo) qs.push('tipo=' + encodeURIComponent(state.tipo));
    if (state.tipo_documento) qs.push('tipo_documento=' + encodeURIComponent(state.tipo_documento));
    var token = localStorage.getItem('refri_access');
    var data;
    try {
      var res = await fetch(API_BASE + '/api/clientes/?' + qs.join('&'), {
        headers: token ? { 'Authorization': 'Bearer ' + token } : {}
      });
      if (!res.ok) throw new Error('Error ' + res.status);
      data = await res.json();
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Cliente', render: function (c) {
          return '<div class="font-semibold text-on-surface">' + esc(c.nombre_completo) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">' +
                   (c.tipo_documento_display ? esc(c.tipo_documento_display) + ': ' : '') +
                   esc(c.documento_numero) + '</div>';
        } },
      { label: 'Tipo', render: function (c) { return esc(c.tipo === 'empresa' ? 'Empresa' : 'Persona'); } },
      { label: 'Correo', key: 'email' },
      { label: 'Teléfono', key: 'telefono' },
      { label: 'Ciudad', key: 'ciudad' },
      { label: 'Registro', render: function (c) { return esc(fmtDate(c.fecha_registro)); } },
      { label: 'Equipos', render: function (c) {
          return '<span class="badge badge-primary">' + c.total_equipos + '</span>';
        } },
      { label: 'Acciones', render: function (c) {
          var btns = [
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(c, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por nombre, documento, correo…',
        filters: [
          { name: 'tipo', label: 'Tipo', value: state.tipo, options: [
              { value: 'persona', label: 'Persona' }, { value: 'empresa', label: 'Empresa' } ] },
          { name: 'tipo_documento', label: 'Documento', value: state.tipo_documento, options: [
              { value: 'cc', label: 'Cédula' }, { value: 'pasaporte', label: 'Pasaporte' },
              { value: 'rnc', label: 'RNC' }, { value: 'nit', label: 'NIT' },
              { value: 'otro', label: 'Otro' } ] },
        ],
        buttons: [{ action: 'crear', icon: 'add', label: 'Nuevo cliente' }],
      },
      columns: columns,
      items: data.results || [],
    });

    clientSideSearch({
      key: 'clientes',
      url: '/api/clientes/',
      columns: columns,
      filter: function (c, q) {
        q = q.toLowerCase();
        return (c.nombre_completo || '').toLowerCase().indexOf(q) >= 0 ||
               (c.documento_numero || '').toLowerCase().indexOf(q) >= 0 ||
               (c.email || '').toLowerCase().indexOf(q) >= 0 ||
               (c.telefono || '').toLowerCase().indexOf(q) >= 0 ||
               (c.ciudad || '').toLowerCase().indexOf(q) >= 0;
      },
    });
  }

  /* ------------------------------------------------------------------
   * TÉCNICOS
   * ------------------------------------------------------------------ */
  async function renderTecnicos() {
    sdCache = {};
    cssClear('tecnicos');
    setViewLoading();
    var state = st('tecnicos', { disponible: '' });
    var data;
    try {
      data = await loadList('/api/tecnicos/', state, ['disponible']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Técnico', render: function (t) {
          return '<div class="font-semibold text-on-surface">' + esc(t.nombre) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">@' + esc(t.username) + '</div>';
        } },
      { label: 'Supervisor', render: function (t) {
          return t.supervisor_nombre ? esc(t.supervisor_nombre) : '<span class="text-on-surface-variant">—</span>';
        } },
      { label: 'Especialidad', key: 'especialidad' },
      { label: 'Teléfono', key: 'telefono' },
      { label: 'Correo', key: 'email' },
      { label: 'Disponible', render: function (t) {
          return t.disponible ? '<span class="badge badge-success">Disponible</span>'
                              : '<span class="badge badge-neutral">Ocupado</span>';
        } },
      { label: 'Acciones', render: function (t) {
          var btns = [
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar perfil', color: 'primary' },
          ];
          if (isAdmin()) {
            btns.push({ kind: 'icon', action: 'editar_usuario', icon: 'manage_accounts', title: 'Editar usuario' });
          }
          if (canDelete() || isSupervisor()) {
            btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar técnico', danger: true });
          }
          return actionBtns(t, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por nombre, usuario, especialidad…',
        filters: [
          { name: 'disponible', label: 'Disponibilidad', value: state.disponible, options: [
              { value: 'true', label: 'Disponibles' }, { value: 'false', label: 'Ocupados' } ] },
        ],
        buttons: (function () {
          if (isSupervisor()) return [{ action: 'crear_trabajo', icon: 'add', label: 'Agregar trabajo' }];
          return [{ action: 'crear', icon: 'person_add', label: 'Agregar técnico' }];
        })(),
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'tecnicos',
      url: '/api/tecnicos/',
      columns: columns,
      fields: ['nombre', 'username', 'especialidad', 'telefono', 'email', 'supervisor_nombre'],
      active: ['disponible'],
    });
  }

  /* ------------------------------------------------------------------
   * SUPERVISORES
   * ------------------------------------------------------------------ */
  async function renderSupervisores() {
    sdCache = {};
    cssClear('supervisores');
    setViewLoading();
    var state = st('supervisores', {});
    var data;
    try {
      data = await loadList('/api/supervisores/', state, []);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Supervisor', render: function (s) {
          return '<div class="font-semibold text-on-surface">' + esc(s.nombre) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">@' + esc(s.username) + '</div>';
        } },
      { label: 'Correo', key: 'email' },
      { label: 'Teléfono', key: 'telefono' },
      { label: 'Técnicos', render: function (s) {
          return '<span class="badge badge-primary">' + (s.tecnicos_count || 0) + '</span>';
        } },
      { label: 'Registro', render: function (s) { return fmtDate(s.created_at); } },
      { label: 'Acciones', render: function (s) {
          var btns = [
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar supervisor', color: 'primary' },
            { kind: 'icon', action: 'editar_usuario', icon: 'manage_accounts', title: 'Editar usuario' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar supervisor', danger: true });
          return actionBtns(s, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por nombre, usuario, correo…',
        buttons: [{ action: 'crear', icon: 'person_add', label: 'Agregar supervisor' }],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'supervisores',
      url: '/api/supervisores/',
      columns: columns,
      fields: ['nombre', 'username', 'email', 'telefono'],
      active: [],
    });
  }

  /* ------------------------------------------------------------------
   * PRODUCTOS / EQUIPOS
   * ------------------------------------------------------------------ */
  async function renderEquipos() {
    sdCache = {};
    cssClear('equipos');
    setViewLoading();
    var state = st('equipos', { estado: '' });
    var data;
    try {
      data = await loadList('/api/equipos/', state, ['estado']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Equipo', render: function (e) {
          return '<div class="font-semibold text-on-surface">' + esc(e.marca) + ' ' + esc(e.modelo) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">' + esc(e.numero_serie) + '</div>';
        } },
      { label: 'Tipo', key: 'tipo_nombre' },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Capacidad', key: 'capacidad' },
      { label: 'Refrigerante', key: 'refrigerante' },
      { label: 'Estado', render: function (e) { return estadoBadge(e.estado, e.estado_display); } },
      { label: 'Garantía', render: function (e) {
          if (e.garantia_activa) return '<span class="badge badge-success">Vigente</span>';
          if (e.garantia_hasta) return '<span class="badge badge-neutral">Vencida</span>';
          return '—';
        } },
      { label: 'Acciones', render: function (e) {
          var btns = [
            { kind: 'icon', action: 'historial', icon: 'history', title: 'Historial del equipo' },
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(e, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por marca, modelo, serie, cliente…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: [
              { value: 'disponible', label: 'Disponible' }, { value: 'instalado', label: 'Instalado' },
              { value: 'averiado', label: 'Averiado' }, { value: 'en_reparacion', label: 'En reparación' },
              { value: 'retirado', label: 'Retirado' } ] },
        ],
        buttons: [
          { action: 'tipos', icon: 'category', label: 'Tipos', variant: 'btn-ghost' },
          { action: 'crear', icon: 'add', label: 'Nuevo equipo' },
        ],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'equipos',
      url: '/api/equipos/',
      columns: columns,
      fields: ['marca', 'modelo', 'numero_serie', 'tipo_nombre', 'cliente_nombre', 'capacidad', 'refrigerante'],
      active: ['estado'],
    });
  }

  /* ------------------------------------------------------------------
   * MIS EQUIPOS (portal del cliente)
   * ------------------------------------------------------------------ */
  async function renderMisEquipos() {
    sdCache = {};
    cssClear('mis_equipos');
    setViewLoading();
    var state = st('mis_equipos', {});
    var data;
    try {
      data = await loadList('/api/equipos/', state, []);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Equipo', render: function (e) {
          return '<div class="font-semibold text-on-surface">' + esc(e.marca) + ' ' + esc(e.modelo) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">' + esc(e.numero_serie) + '</div>';
        } },
      { label: 'Tipo', key: 'tipo_nombre' },
      { label: 'Capacidad', key: 'capacidad' },
      { label: 'Refrigerante', key: 'refrigerante' },
      { label: 'Estado', render: function (e) { return estadoBadge(e.estado, e.estado_display); } },
      { label: 'Registrado', render: function (e) { return fmtDate(e.created_at); } },
      { label: 'Acciones', render: function (e) {
          return actionBtns(e, [{ kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' }]);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por marca, modelo o serie…',
        buttons: [{ action: 'crear', icon: 'add', label: 'Registrar equipo' }],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'mis_equipos',
      url: '/api/equipos/',
      columns: columns,
      fields: ['marca', 'modelo', 'numero_serie', 'tipo_nombre', 'capacidad', 'refrigerante'],
      active: [],
    });
  }

  async function openEquipoClienteForm(item) {
    var tipos = [];
    try { tipos = await fetchAll('/api/tipos-equipo/'); } catch (e) { tipos = []; }
    var fields = [
      { name: 'tipo', label: 'Tipo de equipo', type: 'select', required: true, value: item ? item.tipo : '',
        options: optList(tipos, 'id', 'nombre') },
      { name: 'marca', label: 'Marca', type: 'text', required: true, value: item ? item.marca : '' },
      { name: 'modelo', label: 'Modelo', type: 'text', required: true, value: item ? item.modelo : '' },
      { name: 'numero_serie', label: 'No. de serie', type: 'text', required: true, value: item ? item.numero_serie : '',
        placeholder: 'Si aplica' },
      { name: 'capacidad', label: 'Capacidad', type: 'text', value: item ? item.capacidad : '', placeholder: 'Ej: 12000 BTU' },
      { name: 'refrigerante', label: 'Refrigerante', type: 'text', value: item ? item.refrigerante : '', placeholder: 'Ej: R-410A' },
      { name: 'ubicacion', label: 'Ubicación', type: 'text', value: item ? item.ubicacion : '', placeholder: 'Ej: Sala principal' },
      { name: 'descripcion', label: 'Descripción / datos adicionales', type: 'textarea', span: 2, value: item ? item.descripcion : '',
        placeholder: 'Describe tu equipo y cualquier dato adicional…' },
    ];
    var modal = openModal(item ? 'Editar equipo' : 'Registrar equipo', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Registrar equipo'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/equipos/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/equipos/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Equipo actualizado.' : 'Equipo registrado correctamente.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function misEquiposAction(action, id) {
    if (action === 'crear') return openEquipoClienteForm(null);
    if (action === 'editar') return getItem('/api/equipos/' + id + '/').then(openEquipoClienteForm);
  }

  /* ------------------------------------------------------------------
   * SOLICITUDES
   * ------------------------------------------------------------------ */
  async function renderSolicitudes() {
    sdCache = {};
    cssClear('solicitudes');
    setViewLoading();
    var state = st('solicitudes', { estado: '', prioridad: '' });
    var data;
    try {
      data = await loadList('/api/solicitudes/', state, ['estado', 'prioridad']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: '#', render: function (s) { return '<span class="font-semibold">' + s.id + '</span>'; } },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Equipo solicitado', key: 'tipo_equipo_solicitado' },
      { label: 'Prioridad', render: function (s) { return estadoBadge(s.prioridad, s.prioridad_display); } },
      { label: 'Estado', render: function (s) { return estadoBadge(s.estado, s.estado_display); } },
      { label: 'Fecha solicitud', render: function (s) { return fmtDate(s.fecha_solicitud); } },
      { label: 'Fecha deseada', render: function (s) { return fmtDate(s.fecha_deseada); } },
      { label: 'Acciones', render: function (s) {
          var btns = [
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
            { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(s, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por cliente o equipo solicitado…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: [
              { value: 'pendiente', label: 'Pendiente' }, { value: 'aprobada', label: 'Aprobada' },
              { value: 'reprogramada', label: 'Reprogramada' }, { value: 'rechazada', label: 'Rechazada' },
              { value: 'completada', label: 'Completada' } ] },
          { name: 'prioridad', label: 'Prioridad', value: state.prioridad, options: [
              { value: 'baja', label: 'Baja' }, { value: 'media', label: 'Media' },
              { value: 'alta', label: 'Alta' }, { value: 'urgente', label: 'Urgente' } ] },
        ],
        buttons: [{ action: 'crear', icon: 'add', label: 'Nueva solicitud' }],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'solicitudes',
      url: '/api/solicitudes/',
      columns: columns,
      fields: ['id', 'cliente_nombre', 'tipo_equipo_solicitado', 'prioridad_display', 'estado_display'],
      active: ['estado', 'prioridad'],
    });
  }

  /* ------------------------------------------------------------------
   * INSTALACIONES
   * ------------------------------------------------------------------ */
  async function renderInstalaciones() {
    sdCache = {};
    cssClear('instalaciones');
    setViewLoading();
    var state = st('instalaciones', { estado: '' });
    var data;
    try {
      data = await loadList('/api/instalaciones/', state, ['estado']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: '#', render: function (i) { return '<span class="font-semibold">' + i.id + '</span>'; } },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Equipo', key: 'equipo_nombre' },
      { label: 'Técnico', key: 'tecnico_nombre' },
      { label: 'Fecha programada', render: function (i) { return fmtDT(i.fecha_programada); } },
      { label: 'Prioridad', render: function (i) { return estadoBadge(i.prioridad, i.prioridad_display); } },
      { label: 'Estado', render: function (i) { return estadoBadge(i.estado, i.estado_display); } },
      { label: 'Evid.', render: function (i) { return i.total_evidencias || 0; } },
      { label: 'Acciones', render: function (i) {
          var btns = [
            { kind: 'icon', action: 'ver', icon: 'visibility', title: 'Ver detalle' },
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
            { kind: 'icon', action: 'reprogramar', icon: 'update', title: 'Reprogramar' },
            { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(i, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por cliente, dirección, equipo…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: [
              { value: 'pendiente', label: 'Pendiente' }, { value: 'asignada', label: 'Asignada' },
              { value: 'en_proceso', label: 'En proceso' }, { value: 'finalizada', label: 'Finalizada' },
              { value: 'cancelada', label: 'Cancelada' }, { value: 'reprogramada', label: 'Reprogramada' } ] },
        ],
        buttons: (S.user.role === 'administrador' || S.user.role === 'supervisor') ? [
          { action: 'crear', icon: 'add', label: 'Nueva instalación' },
          { action: 'agenda', icon: 'calendar_month', label: 'Agenda', variant: 'btn-ghost' },
        ] : [
          { action: 'agenda', icon: 'calendar_month', label: 'Agenda', variant: 'btn-ghost' },
        ],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'instalaciones',
      url: '/api/instalaciones/',
      columns: columns,
      fields: ['cliente_nombre', 'equipo_nombre', 'tecnico_nombre', 'direccion', 'prioridad_display', 'estado_display'],
      active: ['estado'],
    });
  }

  /* ------------------------------------------------------------------
   * AGENDA
   * ------------------------------------------------------------------ */
  var ESTADOS_INSTALACION = [
    { value: 'pendiente', label: 'Pendiente' }, { value: 'asignada', label: 'Asignada' },
    { value: 'en_proceso', label: 'En proceso' }, { value: 'finalizada', label: 'Finalizada' },
    { value: 'cancelada', label: 'Cancelada' }, { value: 'reprogramada', label: 'Reprogramada' },
  ];

  function apiUpload(path, formData) {
    var token = localStorage.getItem('refri_access');
    return fetch(API_BASE + path, { method: 'POST', headers: token ? { 'Authorization': 'Bearer ' + token } : {}, body: formData })
      .then(function (res) {
        if (res.status === 401) return tryRefresh().then(function (ok) {
          if (!ok) { forceLogin(); throw new Error('Sesión expirada.'); }
          return apiUpload(path, formData);
        });
        return res.text().then(function (text) {
          var d = null;
          try { d = JSON.parse(text); } catch (e) { d = null; }
          if (!res.ok) {
            var err = new Error('API error ' + res.status);
            err.status = res.status; err.data = d; err.body = text;
            throw err;
          }
          return d;
        });
      });
  }

  function renderAgenda() {
    var state = st('agenda', { tab: 'calendario' });
    var html = tabsHTML(state, [
      { value: 'calendario', label: 'Calendario' },
      { value: 'mapa', label: 'Mapa' },
    ]) + '<div class="tab-content"></div>';
    $('#view').innerHTML = html;
    if (state.tab === 'mapa') renderMapa();
    else renderCalendario();
  }

  async function renderCalendario() {
    var state = st('agenda', { tab: 'calendario', anio: new Date().getFullYear(), mes: new Date().getMonth() });
    if (state.anio == null || state.mes == null) {
      var ahora = new Date();
      state.anio = ahora.getFullYear();
      state.mes = ahora.getMonth();
    }
    var instalaciones = [];
    try {
      instalaciones = await fetchAll('/api/instalaciones/');
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    // Agrupar por fecha (pared en zona del servidor, igual que el filtro ?fecha=).
    var porFecha = {};
    instalaciones.forEach(function (i) {
      var f = (i.fecha_programada || '').slice(0, 10);
      if (!f) return;
      (porFecha[f] = porFecha[f] || []).push(i);
    });

    var primerDia = new Date(state.anio, state.mes, 1);
    var offset = (primerDia.getDay() + 6) % 7; // lunes = 0
    var diasEnMes = new Date(state.anio, state.mes + 1, 0).getDate();
    var hoy = new Date();
    var hoyStrLocal = hoy.toISOString().slice(0, 10);

    var celdas = [];
    // Celdas del mes anterior
    var diasMesAnt = new Date(state.anio, state.mes, 0).getDate();
    for (var i = 0; i < offset; i++) {
      var dAnt = diasMesAnt - offset + i + 1;
      celdas.push({ dia: dAnt, outside: true });
    }
    for (var d = 1; d <= diasEnMes; d++) celdas.push({ dia: d, outside: false });
    var total = celdas.length;
    var rest = (7 - total % 7) % 7;
    for (var r = 1; r <= rest; r++) celdas.push({ dia: r, outside: true });

    var nombreMes = primerDia.toLocaleDateString('es-DO', { month: 'long', year: 'numeric' });
    var html = '<div class="panel-card p-5">' +
      '<div class="cal-header mb-4">' +
        '<div class="flex items-center gap-2">' +
          '<button class="btn btn-ghost" data-cal="prev" title="Mes anterior"><span class="material-symbols-outlined">chevron_left</span></button>' +
          '<button class="btn btn-ghost" data-cal="today" title="Hoy">Hoy</button>' +
          '<button class="btn btn-ghost" data-cal="next" title="Mes siguiente"><span class="material-symbols-outlined">chevron_right</span></button>' +
          '<span class="ml-2 text-lg font-bold capitalize tracking-tight text-on-surface">' + esc(nombreMes) + '</span>' +
        '</div>' +
          (S.user.role === 'administrador' || S.user.role === 'supervisor'
            ? '<button data-action="crear" class="btn btn-primary"><span class="material-symbols-outlined text-sm">add</span>Nueva instalación</button>'
            : '') +
        '</div>' +
      '<div class="cal-grid">' +
        ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'].map(function (w) { return '<div class="cal-dow">' + w + '</div>'; }).join('') +
        celdas.map(function (c) {
          var key;
          if (c.outside) key = (c.dia > 10 ? state.anio - 1 : state.anio) + '-' + String(state.mes + 1).padStart(2, '0') + '-' + String(c.dia).padStart(2, '0');
          else key = state.anio + '-' + String(state.mes + 1).padStart(2, '0') + '-' + String(c.dia).padStart(2, '0');
          // Simplificación visual para celdas fuera del mes.
          var evs = c.outside ? [] : (porFecha[key] || []);
          var cls = ['cal-cell'];
          if (c.outside) cls.push('outside');
          if (!c.outside && key === hoyStrLocal) cls.push('today');
          if (!c.outside && state.fecha === key) cls.push('selected');
          var evHTML = evs.slice(0, 3).map(function (e) {
            var ico = e.estado === 'finalizada' ? 'task_alt' : (e.estado === 'cancelada' ? 'cancel' : 'event');
            return '<div class="cal-event" data-day="' + key + '" data-id="' + e.id + '" title="' +
                   esc(e.cliente_nombre) + ' · ' + esc(e.estado_display) + '">' +
                   '<span class="material-symbols-outlined">' + ico + '</span><span class="truncate">' +
                   (e.tecnico_nombre ? esc(e.tecnico_nombre) : esc(e.cliente_nombre)) + '</span></div>';
          }).join('');
          if (evs.length > 3) evHTML += '<div class="cal-event" data-day="' + key + '">+' + (evs.length - 3) + ' más</div>';
          return '<div class="' + cls.join(' ') + '" data-day="' + key + '" data-outside="' + c.outside + '">' +
                 '<div class="cal-num">' + c.dia + '</div><div class="cal-events">' + evHTML + '</div></div>';
        }).join('') +
      '</div></div>';

    html += '<div id="agendaDia" class="mt-5"></div>';
    var container = $('#view').querySelector('.tab-content') || $('#view');
    container.innerHTML = html;
    renderAgendaDia(porFecha, state.fecha || hoyStrLocal, state);

    container.querySelectorAll('[data-cal]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (b.dataset.cal === 'prev') { state.mes--; if (state.mes < 0) { state.mes = 11; state.anio--; } }
        else if (b.dataset.cal === 'next') { state.mes++; if (state.mes > 11) { state.mes = 0; state.anio++; } }
        else { state.anio = hoy.getFullYear(); state.mes = hoy.getMonth(); }
        state.fecha = '';
        renderCalendario();
      });
    });
    $('#view').querySelectorAll('[data-day]').forEach(function (c) {
      c.addEventListener('click', function (ev) {
        if (ev.target.closest('.cal-event')) return;
        if (c.dataset.outside === 'true') return;
        var d = c.dataset.day;
        if (state.fecha === d) { state.fecha = ''; d = hoyStrLocal; }
        else state.fecha = d;
        renderCalendario();
      });
    });
    // Abrir detalle al hacer clic en un evento del calendario.
    container.querySelectorAll('.cal-event[data-id]').forEach(function (b) {
      b.addEventListener('click', function () { openInstalacionDetalle(Number(b.dataset.id)); });
    });
  }

  function renderAgendaDia(porFecha, fecha, state) {
    var evs = porFecha[fecha] || [];
    var fechaFmt = '';
    try { fechaFmt = new Date(fecha + 'T00:00:00').toLocaleDateString('es-DO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }); } catch (e) { fechaFmt = fecha; }
    var html = '<div class="panel-card">' +
      '<div class="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant p-4">' +
        '<h3 class="text-sm font-bold capitalize tracking-tight text-on-surface">' + esc(fechaFmt) + '</h3>' +
        '<span class="text-xs text-on-surface-variant">' + evs.length + ' instalación(es)</span>' +
      '</div>' +
      buildTable([
        { label: '#', render: function (i) { return '<span class="font-semibold">' + i.id + '</span>'; } },
        { label: 'Cliente', key: 'cliente_nombre' },
        { label: 'Técnico', key: 'tecnico_nombre' },
        { label: 'Hora', render: function (i) { return fmtDT(i.fecha_programada); } },
        { label: 'Prioridad', render: function (i) { return estadoBadge(i.prioridad, i.prioridad_display); } },
        { label: 'Estado', render: function (i) { return estadoBadge(i.estado, i.estado_display); } },
        { label: 'Acciones', render: function (i) {
            var btns = [
              { kind: 'icon', action: 'ver', icon: 'visibility', title: 'Ver detalle' },
              { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
              { kind: 'icon', action: 'reprogramar', icon: 'update', title: 'Reprogramar' },
              { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
            ];
            return actionBtns(i, btns);
          } },
      ], evs) + '</div>';
    $('#agendaDia').innerHTML = html;
  }

  function loadLeaflet() {
    return new Promise(function (resolve) {
      if (window.L && window.L.map) { resolve(window.L); return; }
      var css = document.createElement('link');
      css.rel = 'stylesheet';
      css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      document.head.appendChild(css);
      var s = document.createElement('script');
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
      s.onload = function () { resolve(window.L); };
      document.head.appendChild(s);
    });
  }

  async function renderMapa() {
    var container = $('#view').querySelector('.tab-content') || $('#view');
    container.innerHTML = '<div class="panel-card p-5"><h3 class="mb-3 text-sm font-bold tracking-tight text-on-surface">Mapa de instalaciones</h3>' +
      '<div id="mapaInstalaciones" class="map-container"></div>' +
      '<p class="mt-2 text-xs text-on-surface-variant">Las instalaciones con coordenadas se muestran en el mapa. Al editar una instalación puedes geocodificar su dirección.</p></div>';
    var puntos = [];
    try {
      puntos = await api('/api/instalaciones/mapa/');
    } catch (err) {
      container.querySelector('#mapaInstalaciones').innerHTML =
        '<div class="flex h-full items-center justify-center text-sm text-on-surface-variant">' + esc(apiErrorMessage(err)) + '</div>';
      return;
    }
    var L = await loadLeaflet();
    var mapaEl = document.getElementById('mapaInstalaciones');
    if (!mapaEl) return;
    var map = L.map(mapaEl).setView([19.4792, -70.6931], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
    if (!puntos.length) {
      L.marker([19.4792, -70.6931]).addTo(map).bindPopup('Santiago de los Caballeros · aún no hay instalaciones georreferenciadas').openPopup();
    }
    puntos.forEach(function (p) {
      var lat = Number(p.latitud), lng = Number(p.longitud);
      if (isNaN(lat) || isNaN(lng)) return;
      var marker = L.marker([lat, lng]).addTo(map);
      marker.bindPopup(
        '<strong>' + esc(p.cliente) + '</strong><br>' +
        esc(p.direccion) + (p.ciudad ? ', ' + esc(p.ciudad) : '') + '<br>' +
        '<span class="badge badge-neutral">' + esc(p.estado_display) + '</span><br>' +
        '<a href="#" data-mapa-id="' + p.id + '">Ver detalle</a>'
      );
    });
    map.on('popupopen', function () {
      var link = mapEl.querySelector('a[data-mapa-id]');
      if (link) {
        link.addEventListener('click', function (e) { e.preventDefault(); openInstalacionDetalle(Number(link.dataset.mapaId)); });
      }
    });
  }

  /* ------------------------------------------------------------------
   * Detalle de instalación: evidencias, firma, materiales, historial
   * ------------------------------------------------------------------ */
  async function openInstalacionDetalle(id) {
    var i;
    try { i = await getItem('/api/instalaciones/' + id + '/'); }
    catch (err) { toast(apiErrorMessage(err), 'error'); return; }

    var coordText = (i.latitud && i.longitud)
      ? '<a href="https://www.google.com/maps?q=' + esc(i.latitud) + ',' + esc(i.longitud) + '" target="_blank" rel="noopener" class="text-primary hover:underline">' +
        esc(i.latitud) + ', ' + esc(i.longitud) + '</a>'
      : '<span class="text-on-surface-variant">Sin coordenadas</span>';

    var body = '' +
      '<div class="mb-4 flex flex-wrap items-center gap-2">' +
        '<span class="badge badge-primary">Instalación #' + i.id + '</span>' +
        estadoBadge(i.estado, i.estado_display) +
        estadoBadge(i.prioridad, i.prioridad_display) +
      '</div>' +
      '<div class="det-grid">' +
        '<div><div class="det-label">Cliente</div><div class="det-value">' + esc(i.cliente_nombre) + '</div></div>' +
        '<div><div class="det-label">Técnico</div><div class="det-value">' + esc(i.tecnico_nombre || 'Sin asignar') + '</div></div>' +
        '<div><div class="det-label">Equipo</div><div class="det-value">' + esc(i.equipo_nombre || '—') + '</div></div>' +
        '<div><div class="det-label">Programada</div><div class="det-value">' + fmtDT(i.fecha_programada) + '</div></div>' +
        '<div><div class="det-label">Dirección</div><div class="det-value">' + esc(i.direccion) + (i.ciudad ? ', ' + esc(i.ciudad) : '') + '</div></div>' +
        '<div><div class="det-label">Coordenadas</div><div class="det-value">' + coordText + '</div></div>' +
      '</div>' +
      (i.observaciones ? '<p class="mt-3 text-sm text-on-surface-variant">' + esc(i.observaciones) + '</p>' : '') +
      '<div class="mt-4 flex flex-wrap gap-2">' +
        '<button class="btn btn-ghost" data-det="editar">Editar</button>' +
        '<button class="btn btn-ghost" data-det="reprogramar">Reprogramar</button>' +
        '<button class="btn btn-ghost" data-det="estado">Cambiar estado</button>' +
        '<a class="btn btn-ghost" href="https://www.google.com/maps?q=' + esc(i.direccion) + ', ' + esc(i.ciudad || '') +
          '" target="_blank" rel="noopener">Abrir en mapas</a>' +
      '</div>' +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Evidencias fotográficas</h4><div id="detEvidencias"></div></div>' +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Firmas digitales</h4><div id="detFirmas"></div></div>' +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Materiales utilizados</h4><div id="detMateriales"></div></div>' +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Historial de estados</h4><div id="detHistorial"></div></div>';

    openModal('Instalación #' + i.id, body, {
      footer: '<button type="button" class="btn btn-primary" data-close>Cerrar</button>',
      width: '720px',
    });

    var wrap = $('#modalRoot').querySelector('.modal-panel');
    renderDetEvidencias(i);
    renderDetFirmas(i);
    renderDetMateriales(i);
    renderDetHistorial(i);

    wrap.querySelector('[data-det=editar]').addEventListener('click', function () { closeModal(); openInstalacionForm(i); });
    wrap.querySelector('[data-det=estado]').addEventListener('click', function () { closeModal(); openEstadoModal('instalaciones', i, ESTADOS_INSTALACION); });
    wrap.querySelector('[data-det=reprogramar]').addEventListener('click', function () { closeModal(); reprogramarInstalacion(i); });
  }

  function renderDetEvidencias(i) {
    var cont = $('#detEvidencias');
    var FASE_LABEL = { antes: 'Antes', durante: 'Durante', despues: 'Después' };
    var imgs = (i.evidencias || []).map(function (e) {
      return '<div class="evid-thumb"><img src="' + esc(e.url) + '" alt="' + esc(e.fase) + '" loading="lazy">' +
             '<div class="evid-cap">' + esc(FASE_LABEL[e.fase] || e.fase) + '</div></div>';
    }).join('');
    cont.innerHTML =
      '<div class="evid-grid mb-3">' + (imgs || '<p class="text-sm text-on-surface-variant">Sin evidencias (requeridas para finalizar, RN-05).</p>') + '</div>' +
      '<form id="formEvidencia" class="grid grid-cols-1 gap-2 sm:grid-cols-2">' +
        '<select name="fase" class="adm-select"><option value="antes">Antes</option><option value="durante">Durante</option><option value="despues">Después</option></select>' +
        '<input name="descripcion" class="adm-input" placeholder="Descripción (opcional)">' +
        '<input name="imagen" type="file" accept="image/*" class="adm-input sm:col-span-2" required>' +
        '<button type="submit" class="btn btn-primary sm:col-span-2"><span class="material-symbols-outlined text-sm">photo_camera</span>Subir evidencia</button>' +
      '</form>';
    $('#formEvidencia').addEventListener('submit', function (e) {
      e.preventDefault();
      var fd = new FormData(e.target);
      fd.append('content_type', 'instalaciones.instalacion');
      fd.append('object_id', String(i.id));
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      apiUpload('/api/evidencias/', fd)
        .then(function () {
          toast('Evidencia subida.', 'success');
          openInstalacionDetalle(i.id);
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); setBusy(btn, false); });
    });
  }

  function renderDetFirmas(i) {
    var cont = $('#detFirmas');
    var firmas = (i.firmas || []).map(function (f) {
      return '<div class="flex items-center gap-3 rounded-lg border border-outline-variant p-2">' +
             '<img src="' + esc(f.url) + '" alt="firma" class="h-12 w-20 rounded-md object-contain" style="background:#fff">' +
             '<div class="min-w-0 flex-1"><div class="truncate text-sm font-semibold text-on-surface">' + esc(f.nombre) + '</div>' +
             '<div class="text-xs text-on-surface-variant">' + esc(f.documento || '—') + ' · ' + fmtDT(f.created_at) + '</div></div></div>';
    }).join('');
    cont.innerHTML =
      (firmas ? '<div class="mb-3 space-y-2">' + firmas + '</div>' : '<p class="mb-3 text-sm text-on-surface-variant">Sin firmas registradas.</p>') +
      '<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">' +
        '<input id="firmaNombre" class="adm-input" placeholder="Nombre del firmante" value="' + esc(i.cliente_nombre || '') + '">' +
        '<input id="firmaDoc" class="adm-input" placeholder="Documento">' +
      '</div>' +
      '<div class="sig-canvas-wrap mt-2"><canvas id="firmaCanvas" class="sig-canvas"></canvas></div>' +
      '<div class="mt-2 flex flex-wrap gap-2">' +
        '<button id="firmaLimpiar" class="btn btn-ghost">Limpiar</button>' +
        '<button id="firmaGuardar" class="btn btn-primary"><span class="material-symbols-outlined text-sm">draw</span>Guardar firma</button>' +
      '</div>';
    var canvas = $('#firmaCanvas');
    var ctx = canvas.getContext('2d');
    function resizeCanvas() {
      var rect = canvas.getBoundingClientRect();
      var dpr = window.devicePixelRatio || 1;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.scale(dpr, dpr);
      ctx.lineWidth = 2;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#0F172A';
    }
    resizeCanvas();
    var drawing = false;
    function pos(e) {
      var rect = canvas.getBoundingClientRect();
      var pt = e.touches ? e.touches[0] : e;
      return { x: pt.clientX - rect.left, y: pt.clientY - rect.top };
    }
    canvas.addEventListener('mousedown', function (e) { drawing = true; ctx.beginPath(); ctx.moveTo(pos(e).x, pos(e).y); });
    canvas.addEventListener('mousemove', function (e) { if (!drawing) return; var p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); });
    window.addEventListener('mouseup', function () { drawing = false; });
    canvas.addEventListener('touchstart', function (e) { e.preventDefault(); drawing = true; ctx.beginPath(); ctx.moveTo(pos(e).x, pos(e).y); });
    canvas.addEventListener('touchmove', function (e) { e.preventDefault(); if (!drawing) return; var p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke(); });
    canvas.addEventListener('touchend', function () { drawing = false; });
    $('#firmaLimpiar').addEventListener('click', function () { ctx.clearRect(0, 0, canvas.width, canvas.height); });
    $('#firmaGuardar').addEventListener('click', function () {
      var nombre = $('#firmaNombre').value.trim();
      if (!nombre) { toast('Indica el nombre del firmante.', 'error'); return; }
      var dataUrl = canvas.toDataURL('image/png');
      var blob = new Blob([atob(dataUrl.split(',')[1])], { type: 'image/png' });
      var fd = new FormData();
      fd.append('content_type', 'instalaciones.instalacion');
      fd.append('object_id', String(i.id));
      fd.append('nombre', nombre);
      fd.append('documento', $('#firmaDoc').value.trim());
      fd.append('imagen', blob, 'firma.png');
      var btn = $('#firmaGuardar');
      setBusy(btn, true);
      apiUpload('/api/firmas/', fd)
        .then(function () {
          toast('Firma registrada.', 'success');
          openInstalacionDetalle(i.id);
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); setBusy(btn, false); });
    });
  }

  function renderDetMateriales(i) {
    var cont = $('#detMateriales');
    var isTecnico = S.user.role === 'tecnico';
    var filas = (i.materiales_instalacion || []).map(function (m) {
      var detLine = '<div class="min-w-0"><div class="truncate text-sm font-medium text-on-surface">' + esc(m.material_nombre) + '</div>' +
             '<div class="text-xs text-on-surface-variant">' + m.cantidad + ' ' + esc(m.material_unidad) +
             (isTecnico ? '' : ' × ' + money(m.precio_unitario)) + '</div></div>';
      return '<div class="flex items-center justify-between gap-2 py-2">' + detLine +
             (isTecnico ? '' : '<div class="font-semibold text-on-surface">' + money(m.subtotal) + '</div>') + '</div>';
    }).join('');
    cont.innerHTML =
      '<div class="divide-y divide-outline-variant">' + (filas || '<p class="py-1 text-sm text-on-surface-variant">Sin materiales registrados.</p>') + '</div>' +
      (isTecnico ? '' :
       '<div class="mt-1 flex justify-between border-t border-outline-variant pt-2 text-sm"><span class="font-semibold text-on-surface">Total materiales</span>' +
       '<span class="font-bold text-primary">' + money(i.total_materiales) + '</span></div>') +
      '<p class="mt-2 text-xs text-on-surface-variant">El inventario se descuenta al finalizar la instalación (RN-06).</p>' +
      '<form id="formMaterial" class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">' +
        '<select name="material" class="adm-select sm:col-span-1" required><option value="">Material…</option></select>' +
        '<input name="cantidad" type="number" min="0.01" step="0.01" class="adm-input" placeholder="Cantidad" required>' +
        '<input name="precio_unitario" type="number" min="0" step="0.01" class="adm-input" placeholder="Precio (opcional)">' +
        '<button type="submit" class="btn btn-primary sm:col-span-3"><span class="material-symbols-outlined text-sm">add</span>Agregar material</button>' +
      '</form>';
    fetchAll('/api/materiales/').then(function (mats) {
      var sel = $('#formMaterial').querySelector('[name=material]');
      sel.innerHTML = '<option value="">Material…</option>' + mats.map(function (m) {
        return '<option value="' + m.id + '">' + esc(m.nombre) + ' · disp. ' + m.cantidad_disponible + ' ' + esc(m.unidad_display) + '</option>';
      }).join('');
    }).catch(function () { /* listado no disponible */ });
    $('#formMaterial').addEventListener('submit', function (e) {
      e.preventDefault();
      var data = {
        material: Number(e.target.querySelector('[name=material]').value),
        cantidad: Number(e.target.querySelector('[name=cantidad]').value),
      };
      var pre = e.target.querySelector('[name=precio_unitario]').value;
      if (pre !== '') data.precio_unitario = Number(pre);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      api('/api/instalaciones/' + i.id + '/materiales/', { method: 'POST', body: JSON.stringify(data) })
        .then(function () {
          toast('Material agregado.', 'success');
          openInstalacionDetalle(i.id);
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); setBusy(btn, false); });
    });
  }

  async function renderDetHistorial(i) {
    var cont = $('#detHistorial');
    cont.innerHTML = '<p class="text-sm text-on-surface-variant">Cargando historial…</p>';
    var logs = [];
    try { logs = await api('/api/instalaciones/' + i.id + '/historial/'); }
    catch (e) { cont.innerHTML = '<p class="text-sm text-on-surface-variant">No se pudo cargar.</p>'; return; }
    cont.innerHTML = logs.length
      ? '<div class="timeline">' + logs.map(function (l) {
          return '<div class="timeline-item">' +
                 '<div class="flex flex-wrap items-center gap-2">' +
                 '<span class="text-sm font-semibold text-on-surface">' + esc(l.estado_anterior || '—') + ' → ' + esc(l.estado_nuevo) + '</span>' +
                 estadoBadge(l.estado_nuevo, l.estado_nuevo) + '</div>' +
                 (l.comentario ? '<p class="mt-0.5 text-xs text-on-surface-variant">' + esc(l.comentario) + '</p>' : '') +
                 '<p class="mt-0.5 text-[11px] text-on-surface-variant">' + fmtDT(l.fecha) +
                 (l.usuario_nombre ? ' · ' + esc(l.usuario_nombre) : '') + '</p></div>';
        }).join('') + '</div>'
      : '<p class="text-sm text-on-surface-variant">Sin cambios de estado registrados.</p>';
  }

  function reprogramarInstalacion(i) {
    var fields = [
      { name: 'fecha_programada', label: 'Nueva fecha programada', type: 'datetime-local', required: true, value: dtLocal(i.fecha_programada),
        hint: 'Selecciona la fecha y hora desde el calendario.' },
      { name: 'motivo', label: 'Motivo de la reprogramación', type: 'textarea', span: 2, value: '' },
    ];
    var body = formHTML(fields) +
      '<div class="mt-3"><button id="btnSlots" type="button" class="btn btn-ghost">' +
      '<span class="material-symbols-outlined text-sm">schedule</span>Ver horarios disponibles</button>' +
      '<div id="slotList" class="mt-3 flex flex-wrap gap-2"></div></div>' +
      '<p class="mt-2 text-xs text-on-surface-variant">Sugerencias de la agenda inteligente (RN-03): bloques de 30 min entre 08:00 y 18:00, sin conflicto con otras instalaciones del técnico.</p>';
    openModal('Reprogramar instalación #' + i.id, body, {
      footer: modalFooter('Cancelar', 'Reprogramar'),
    });
    $('#btnSlots').addEventListener('click', function () {
      var fecha = $('#modalForm [name=fecha_programada]').value;
      if (!fecha) { toast('Primero elige la nueva fecha.', 'error'); return; }
      var fechaStr = fecha.slice(0, 10);
      var qs = '?fecha=' + fechaStr + '&duracion_minutos=120';
      if (i.tecnico) qs += '&tecnico=' + i.tecnico;
      qs += '&instalacion=' + i.id;
      $('#slotList').innerHTML = '<span class="text-sm text-on-surface-variant">Cargando…</span>';
      api('/api/instalaciones/disponibilidad/' + qs)
        .then(function (r) {
          var slots = r.slots || [];
          if (!slots.length) {
            $('#slotList').innerHTML = '<span class="text-sm text-error">No hay horarios libres para ese día.</span>';
            return;
          }
          $('#slotList').innerHTML = slots.map(function (s, idx) {
            return '<button type="button" class="slot-chip" data-slot="' + s.inicio + '" data-idx="' + idx + '">' +
                   fmtDT(s.inicio) + '</button>';
          }).join('');
          $('#slotList').querySelectorAll('.slot-chip').forEach(function (c) {
            c.addEventListener('click', function () {
              $('#slotList').querySelectorAll('.slot-chip').forEach(function (x) { x.classList.remove('active'); });
              c.classList.add('active');
              $('#modalForm [name=fecha_programada]').value = dtLocal(c.dataset.slot);
            });
          });
        })
        .catch(function (err) { $('#slotList').innerHTML = '<span class="text-sm text-error">' + esc(apiErrorMessage(err)) + '</span>'; });
    });
    $('#modalForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      api('/api/instalaciones/' + i.id + '/reprogramar/', { method: 'PATCH', body: JSON.stringify(data) })
        .then(function () {
          toast('Instalación reprogramada y notificada al cliente y técnico.', 'success');
          closeModal();
          reloadCurrent();
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); setBusy(btn, false); });
    });
  }

  function agendaAction(action, id) {
    if (action === 'crear') return openInstalacionForm(null);
    if (action === 'ver') return openInstalacionDetalle(id);
    if (action === 'editar') return getItem('/api/instalaciones/' + id + '/').then(openInstalacionForm);
    if (action === 'reprogramar') return getItem('/api/instalaciones/' + id + '/').then(reprogramarInstalacion);
    if (action === 'estado') return getItem('/api/instalaciones/' + id + '/').then(function (i) {
      openEstadoModal('instalaciones', i, ESTADOS_INSTALACION);
    });
  }

  /* ------------------------------------------------------------------
   * PAGOS / FACTURAS
   * ------------------------------------------------------------------ */
  function tabsHTML(state, tabs) {
    var html = '<div class="mb-4 flex flex-wrap items-center gap-2">';
    tabs.forEach(function (t) {
      html += '<button data-action="tab" data-tab="' + esc(t.value) + '" class="btn ' +
              (state.tab === t.value ? 'btn-primary' : 'btn-ghost') + '">' + esc(t.label) + '</button>';
    });
    html += '</div>';
    return html;
  }

  async function renderPagos() {
    sdCache = {};
    cssClear('pagos');
    setViewLoading();
    var state = st('pagos', { tab: 'pagos', estado: '', metodo: '' });
    var html = tabsHTML(state, [
      { value: 'pagos', label: 'Pagos' },
      { value: 'facturas', label: 'Facturas' },
    ]);

    if (state.tab === 'facturas') {
      var facturas;
      var colsFacturas;
      try {
        facturas = await loadList('/api/facturas/', state);
      } catch (err) {
        setViewError(apiErrorMessage(err));
        return;
      }
      html += viewShell({
        state: state,
        data: facturas,
        toolbar: {
          search: state.search,
          placeholder: 'Buscar por número o cliente…',
          buttons: [{ action: 'nueva_factura', icon: 'add', label: 'Nueva factura' }],
        },
        columns: (colsFacturas = [
          { label: 'Número', render: function (f) { return '<span class="font-semibold">' + esc(f.numero) + '</span>'; } },
          { label: 'Cliente', key: 'cliente_nombre' },
          { label: 'Orden', key: 'orden_numero' },
          { label: 'Fecha', render: function (f) { return fmtDate(f.fecha); } },
          { label: 'Subtotal', render: function (f) { return money(f.subtotal); } },
          { label: 'IVA', render: function (f) { return money(f.iva); } },
          { label: 'Total', render: function (f) { return '<span class="font-semibold">' + money(f.total) + '</span>'; } },
          { label: 'Acciones', render: function (f) {
              var btns = [{ kind: 'icon', action: 'ver_factura', icon: 'visibility', title: 'Ver detalle' }];
              if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar_factura', icon: 'delete', title: 'Eliminar', danger: true });
              return actionBtns(f, btns);
            } },
        ]),
        items: facturas.results || [],
      });
      $('#view').innerHTML = html;
      cssRegister({
        key: 'pagos:facturas',
        url: '/api/facturas/',
        columns: colsFacturas,
        fields: ['numero', 'cliente_nombre', 'orden_numero'],
        active: [],
      });
      return;
    }

    var pagos;
    var colsPagos;
    var specPagos = cssSpec();
    var useCssPagos = specPagos && (!specPagos.active || specPagos.active());
    try {
      if (useCssPagos && state.search) {
        // Búsqueda client-side: el servidor /api/pagos/ no filtra por cliente,
        // así que al seleccionar una sugerencia se cargan todos y se filtran en memoria.
        // Se pagina en memoria con la misma estructura existente (state.page / paginationHTML).
        var fullPagos = await cssFullList(specPagos);
        var filtrados = fullPagos.filter(function (p) { return specPagos.filter(p, state.search); });
        var totalPaginas = Math.max(1, Math.ceil(filtrados.length / PAGE_SIZE));
        var pagina = Math.min(Math.max(1, state.page || 1), totalPaginas);
        if (pagina !== (state.page || 1)) state.page = pagina;
        pagos = {
          results: filtrados.slice((pagina - 1) * PAGE_SIZE, pagina * PAGE_SIZE),
          count: filtrados.length,
          previous: pagina > 1 ? pagina - 1 : null,
          next: pagina < totalPaginas ? pagina + 1 : null,
        };
      } else {
        pagos = await loadList('/api/pagos/', state, ['estado', 'metodo']);
      }
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    html += viewShell({
      state: state,
      data: pagos,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por referencia o cliente…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: [
              { value: 'pendiente', label: 'Pendiente' }, { value: 'pagado', label: 'Pagado' },
              { value: 'fallido', label: 'Fallido' } ] },
          { name: 'metodo', label: 'Método', value: state.metodo, options: [
              { value: 'efectivo', label: 'Efectivo' }, { value: 'tarjeta', label: 'Tarjeta' },
              { value: 'transferencia', label: 'Transferencia' }, { value: 'cheque', label: 'Cheque' } ] },
        ],
        buttons: [{ action: 'crear', icon: 'add', label: 'Nuevo pago' }],
      },
      columns: (colsPagos = [
        { label: 'Cliente', key: 'cliente_nombre' },
        { label: 'Concepto', render: function (p) {
            if (p.orden_numero) return 'Orden ' + esc(p.orden_numero);
            if (p.instalacion_id) return 'Instalación #' + p.instalacion_id;
            return '—';
          } },
        { label: 'Monto', render: function (p) { return '<span class="font-semibold">' + money(p.monto) + '</span>'; } },
        { label: 'Abono', render: function (p) { return p.es_abono ? '<span class="badge badge-info">Abono</span>' : '—'; } },
        { label: 'Método', render: function (p) { return esc(p.metodo_display); } },
        { label: 'Estado', render: function (p) { return estadoBadge(p.estado, p.estado_display); } },
        { label: 'Fecha', render: function (p) { return fmtDate(p.fecha); } },
        { label: 'Acciones', render: function (p) {
            var btns = [{ kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' }];
            if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
            return actionBtns(p, btns);
          } },
      ]),
      items: pagos.results || [],
    });
    $('#view').innerHTML = html;
    cssRegister({
      key: 'pagos:pagos',
      url: '/api/pagos/',
      columns: colsPagos,
      fields: ['cliente_nombre', 'orden_numero', 'instalacion_id', 'metodo_display', 'referencia', 'estado_display'],
      active: ['estado', 'metodo'],
    });
  }

  /* ------------------------------------------------------------------
   * INVENTARIO
   * ------------------------------------------------------------------ */
  async function renderInventario() {
    sdCache = {};
    cssClear('inventario');
    setViewLoading();
    var state = st('inventario', { tab: 'materiales', categoria: '', unidad_medida: '' });
    var html = tabsHTML(state, [
      { value: 'materiales', label: 'Materiales' },
    ]);
    if (canDelete() || S.user.role === 'almacen') {
      html = tabsHTML(state, [
        { value: 'materiales', label: 'Materiales' },
        { value: 'movimientos', label: 'Movimientos' },
      ]);
    }

    if (state.tab === 'movimientos') {
      var movs;
      var colsMovs;
      try {
        movs = await loadList('/api/movimientos/', state);
      } catch (err) {
        setViewError(apiErrorMessage(err));
        return;
      }
      html += viewShell({
        state: state,
        data: movs,
        toolbar: { search: state.search, placeholder: 'Buscar por material o motivo…' },
        columns: (colsMovs = [
          { label: 'Fecha', render: function (m) { return fmtDT(m.fecha); } },
          { label: 'Material', render: function (m) {
              return '<div class="font-medium text-on-surface">' + esc(m.material_nombre) + '</div>' +
                     '<div class="text-xs text-on-surface-variant">' + esc(m.material_codigo) + '</div>';
            } },
          { label: 'Tipo', render: function (m) { return estadoBadge(m.tipo, m.tipo_display); } },
          { label: 'Cantidad', render: function (m) { return m.cantidad; } },
          { label: 'Motivo', key: 'motivo' },
          { label: 'Usuario', key: 'usuario_nombre' },
        ]),
        items: movs.results || [],
      });
      $('#view').innerHTML = html;
      cssRegister({
        key: 'inventario:movimientos',
        url: '/api/movimientos/',
        columns: colsMovs,
        fields: ['material_nombre', 'material_codigo', 'motivo', 'usuario_nombre', 'tipo_display'],
        active: [],
      });
      return;
    }

    var mats;
    var colsMats;
    var matsUrl = state.stock_bajo ? '/api/materiales/stock_bajo/' : '/api/materiales/';
    try {
      mats = await loadList(matsUrl, state, ['categoria', 'unidad_medida']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    if (state.stock_bajo) {
      html += '<div class="info-banner"><span class="material-symbols-outlined text-base">warning</span>' +
              'Mostrando materiales con stock igual o por debajo del mínimo.</div>';
    }
    html += viewShell({
      state: state,
      data: mats,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por nombre, código, categoría…',
        filters: [
          { name: 'unidad_medida', label: 'Unidad', value: state.unidad_medida, options: [
              { value: 'unidad', label: 'Unidad' }, { value: 'metro', label: 'Metro' },
              { value: 'litro', label: 'Litro' }, { value: 'galon', label: 'Galón' },
              { value: 'kilogramo', label: 'Kilogramo' }, { value: 'libra', label: 'Libra' },
              { value: 'paquete', label: 'Paquete' } ] },
        ],
        buttons: [{ action: 'crear', icon: 'add', label: 'Nuevo material' }],
      },
      columns: (colsMats = [
        { label: 'Material', render: function (m) {
            return '<div class="font-semibold text-on-surface">' + esc(m.nombre) + '</div>' +
                   '<div class="text-xs text-on-surface-variant">' + esc(m.codigo) + '</div>';
          } },
        { label: 'Categoría', key: 'categoria' },
        { label: 'Unidad', key: 'unidad_display' },
        { label: 'Disponible', render: function (m) { return money(m.cantidad_disponible); } },
        { label: 'Mínimo', render: function (m) { return money(m.stock_minimo); } },
        { label: 'Stock', render: function (m) {
            return m.stock_bajo ? '<span class="badge badge-error">Bajo</span>'
                                : '<span class="badge badge-success">OK</span>';
          } },
      ].concat(S.user.role !== 'tecnico' ? [
        { label: 'Precio', render: function (m) { return money(m.precio); } },
      ] : []).concat([
        { label: 'Acciones', render: function (m) {
            var btns = [
              { kind: 'icon', action: 'entrada', icon: 'inventory', title: 'Entrada / ajuste' },
              { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
            ];
            if (canDelete() || S.user.role === 'almacen') {
              btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
            }
            return actionBtns(m, btns);
          } },
      ])),
      items: mats.results || [],
    });
    $('#view').innerHTML = html;
    cssRegister({
      key: 'inventario:materiales',
      url: '/api/materiales/',
      columns: colsMats,
      fields: ['nombre', 'codigo', 'categoria', 'unidad_display'],
      active: ['categoria', 'unidad_medida', 'stock_bajo'],
    });
  }

  /* ------------------------------------------------------------------
   * ALMACÉN / VITRINA
   * ------------------------------------------------------------------ */
  async function renderAlmacen() {
    sdCache = {};
    cssClear('almacen');
    setViewLoading();
    var state = st('almacen', { tab: 'productos', categoria: '', disponible: '' });
    var tabs = [
      { value: 'productos', label: 'Productos' },
      { value: 'categorias', label: 'Categorías' },
    ];
    if (canManageAlmacen()) tabs.push({ value: 'historial', label: 'Historial' });
    var html = tabsHTML(state, tabs);

    if (state.tab === 'historial') {
      var logs;
      var colsLogs;
      try {
        logs = await loadList('/api/auditoria/', state, ['model_name']);
      } catch (err) {
        setViewError(apiErrorMessage(err));
        return;
      }
      var ACCION_BADGE = {
        crear: 'badge-success',
        actualizar: 'badge-primary',
        eliminar: 'badge-error',
        cambio_estado: 'badge-warning',
      };
      var ACCION_LABEL = {
        crear: 'Crear', actualizar: 'Actualizar', eliminar: 'Eliminar',
        cambio_estado: 'Cambio de estado', otro: 'Otro',
      };
      html += viewShell({
        state: state,
        data: logs,
        toolbar: {
          search: state.search,
          placeholder: 'Buscar en el historial…',
          filters: [
            { name: 'model_name', label: 'Registro', value: state.model_name, options: [
                { value: 'almacen.producto', label: 'Productos' },
                { value: 'almacen.categoria', label: 'Categorías' },
              ] },
          ],
        },
        columns: (colsLogs = [
          { label: 'Fecha', render: function (l) { return fmtDT(l.created_at); } },
          { label: 'Usuario', key: 'usuario' },
          { label: 'Acción', render: function (l) {
              return '<span class="badge ' + (ACCION_BADGE[l.action] || 'badge-neutral') + '">' +
                     esc(ACCION_LABEL[l.action] || l.action) + '</span>';
            } },
          { label: 'Registro', render: function (l) {
              return '<div class="font-medium text-on-surface">' + esc(l.object_repr || '—') + '</div>' +
                     '<div class="text-xs text-on-surface-variant">' + esc(l.model_name) + '</div>';
            } },
          { label: 'Detalle', render: function (l) {
              var ch = l.changes;
              if (!ch || typeof ch !== 'object') return '—';
              var keys = Object.keys(ch);
              if (!keys.length) return '—';
              return keys.slice(0, 4).map(function (k) {
                var v = ch[k];
                if (v && typeof v === 'object') v = JSON.stringify(v);
                return '<span class="badge badge-neutral">' + esc(k) + '</span> ' + esc(v);
              }).join(' ');
            } },
        ]),
        items: logs.results || [],
      });
      $('#view').innerHTML = html;
      cssRegister({
        key: 'almacen:historial',
        url: '/api/auditoria/',
        columns: colsLogs,
        fields: ['usuario', 'object_repr', 'model_name', 'action'],
        active: ['model_name'],
      });
      return;
    }

    if (state.tab === 'categorias') {
      var cats;
      try {
        cats = await api('/api/categorias/');
      } catch (err) {
        setViewError(apiErrorMessage(err));
        return;
      }
      var cols = [
        { label: 'Categoría', render: function (c) {
            return '<div class="flex items-center gap-2"><span class="material-symbols-outlined text-on-surface-variant">' +
                   esc(c.icono) + '</span><span class="font-semibold text-on-surface">' + esc(c.nombre) + '</span></div>';
          } },
        { label: 'Descripción', key: 'descripcion' },
        { label: 'Productos', render: function (c) { return '<span class="badge badge-primary">' + c.total_productos + '</span>'; } },
        { label: 'Orden', render: function (c) { return c.orden; } },
        { label: 'Acciones', render: function (c) {
            var btns = [{ kind: 'icon', action: 'editar_categoria', icon: 'edit', title: 'Editar', color: 'primary' }];
            if (canManageAlmacen()) btns.push({ kind: 'icon', action: 'eliminar_categoria', icon: 'delete', title: 'Eliminar', danger: true });
            return actionBtns(c, btns);
          } },
      ];
      html += '<div class="panel-card">' +
        '<div class="flex flex-wrap items-center justify-between gap-2 border-b border-outline-variant p-4">' +
        '<span class="text-sm font-semibold text-on-surface">' + cats.length + ' categorías</span>' +
        '<button data-action="crear_categoria" class="btn btn-primary">' +
        '<span class="material-symbols-outlined text-sm">add</span>Nueva categoría</button>' +
        '</div>' + buildTable(cols, cats) + '</div>';
      $('#view').innerHTML = html;
      return;
    }

    var data;
    var colsProd;
    try {
      data = await loadList('/api/productos/', state, ['categoria', 'disponible']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var res = data.results || [];
    var agotados = res.filter(function (p) { return p.agotado || p.stock === 0; }).length;
    var bajos = res.filter(function (p) { return !p.agotado && p.stock > 0 && p.stock <= STOCK_MINIMO; }).length;
    if (agotados || bajos) {
      html += '<div class="mb-3 flex flex-wrap items-center gap-2 text-xs">' +
              '<span class="badge badge-neutral">' + res.length + ' productos</span>' +
              (bajos ? '<span class="badge badge-warning">' + bajos + ' con stock bajo (≤ ' + STOCK_MINIMO + ')</span>' : '') +
              (agotados ? '<span class="badge badge-error">' + agotados + ' agotados</span>' : '') +
              '</div>';
    }
    var catsOpts = [];
    try { catsOpts = await api('/api/categorias/'); } catch (e) { catsOpts = []; }
    html += viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por nombre, descripción, categoría…',
        filters: [
          { name: 'categoria', label: 'Categoría', value: state.categoria, options: optList(catsOpts, 'id', 'nombre') },
          { name: 'disponible', label: 'Disponibilidad', value: state.disponible, options: [
              { value: 'true', label: 'Disponibles' }, { value: 'false', label: 'No disponibles' } ] },
        ],
        buttons: [
          { action: 'crear_categoria', icon: 'category', label: 'Nueva categoría', variant: 'btn-ghost' },
          { action: 'crear', icon: 'add', label: 'Agregar producto' },
        ],
      },
      columns: (colsProd = [
        { label: 'Producto', render: function (p) {
            return '<div class="flex items-center gap-3">' +
                   (p.imagen ? '<img src="' + esc(p.imagen) + '" alt="" class="h-10 w-10 rounded-lg object-cover" loading="lazy">' : '') +
                   '<div><div class="font-semibold text-on-surface">' + esc(p.nombre) + '</div>' +
                   '<div class="text-xs text-on-surface-variant">' + esc(p.categoria_nombre) + '</div></div></div>';
          } },
        { label: 'Precio', render: function (p) {
            return p.precio != null ? money(p.precio) : '<span class="badge badge-info">Consultar</span>';
          } },
        { label: 'Stock', render: function (p) {
            if (p.stock == null) return '—';
            if (p.stock <= 0) return '<span class="badge badge-error">Sin stock</span>';
            var htmlStock = '<span class="font-semibold">' + p.stock + ' und</span>';
            if (p.stock <= STOCK_MINIMO) htmlStock += ' <span class="badge badge-warning">bajo</span>';
            return htmlStock;
          } },
        { label: 'Estado', render: function (p) {
            return p.agotado ? '<span class="badge badge-error">Agotado</span>'
                 : p.disponible ? '<span class="badge badge-success">Disponible</span>'
                 : '<span class="badge badge-warning">Oculto</span>';
          } },
        { label: 'Destacado', render: function (p) { return p.destacado ? '<span class="badge badge-primary">Sí</span>' : '—'; } },
        { label: 'Acciones', render: function (p) {
            var btns = [{ kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar', color: 'primary' }];
            if (canManageAlmacen()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar producto', danger: true });
            return actionBtns(p, btns);
          } },
      ]),
      items: res,
    });
    $('#view').innerHTML = html;
    cssRegister({
      key: 'almacen:productos',
      url: '/api/productos/',
      columns: colsProd,
      fields: ['nombre', 'categoria_nombre', 'descripcion'],
      active: ['categoria', 'disponible'],
    });
  }

  async function openCategoriaForm(item) {
    var fields = [
      { name: 'nombre', label: 'Nombre', type: 'text', required: true, value: item ? item.nombre : '' },
      { name: 'icono', label: 'Icono (Material Symbols)', type: 'text', value: item ? item.icono : 'category',
        hint: 'Nombre de un icono de Material Symbols, ej: ac_unit, propane_tank, handyman.' },
      { name: 'orden', label: 'Orden', type: 'number', min: 1, value: item ? item.orden : 1 },
      { name: 'descripcion', label: 'Descripción', type: 'textarea', span: 2, value: item ? item.descripcion : '' },
    ];
    openModal(item ? 'Editar categoría' : 'Nueva categoría', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear categoría'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/categorias/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/categorias/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Categoría actualizada.' : 'Categoría creada.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  async function openProductoForm(item) {
    var cats = [];
    try { cats = await api('/api/categorias/'); } catch (e) { cats = []; }
    var fields = [
      { name: 'nombre', label: 'Nombre del producto', type: 'text', required: true, value: item ? item.nombre : '' },
      { name: 'categoria', label: 'Categoría', type: 'select', required: true, value: item ? item.categoria : '',
        options: optList(cats, 'id', 'nombre') },
      { name: 'precio', label: 'Precio (RD$)', type: 'number', min: 0.01, step: 0.01,
        value: item && item.precio != null ? item.precio : '', hint: 'Vacío = "Consultar precio".' },
      { name: 'en_oferta', label: 'Producto en oferta', type: 'checkbox', value: item ? !!item.en_oferta : false,
        hint: 'Muestra el precio normal tachado y el precio de oferta en la vitrina.' },
      { name: 'precio_oferta', label: 'Precio de oferta (RD$)', type: 'number', min: 0.01, step: 0.01,
        value: item && item.precio_oferta != null ? item.precio_oferta : '',
        hint: 'Solo se usa si "Producto en oferta" está activado. Vacío = sin oferta.' },
      { name: 'stock', label: 'Stock (unidades)', type: 'number', required: true, min: 0, value: item ? item.stock : 0 },
      { name: 'imagen', label: 'Imagen del producto', type: 'image', span: 2, value: item ? item.imagen : '',
        hint: 'Selecciona una imagen desde tu computadora. Se guarda en /media/productos/.' },
      { name: 'descripcion', label: 'Descripción', type: 'textarea', span: 2, value: item ? item.descripcion : '' },
      { name: 'estado', label: 'Estado', type: 'select', value: item ? (item.disponible ? 'disponible' : 'agotado') : 'disponible',
        options: [{ value: 'disponible', label: 'Disponible' }, { value: 'agotado', label: 'Agotado' }],
        hint: 'Si el stock llega a 0 el producto se muestra como agotado automáticamente.' },
      { name: 'destacado', label: 'Producto destacado', type: 'checkbox', value: item ? !!item.destacado : false },
    ];
    openModal(item ? 'Editar producto' : 'Agregar producto', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear producto'),
      width: '680px',
    });
    wireImageUpload('imagen');
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      data.disponible = data.estado !== 'agotado';
      delete data.estado;
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/productos/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/productos/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Producto actualizado.' : 'Producto creado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function almacenAction(action, id) {
    if (action === 'crear') return openProductoForm(null);
    if (action === 'crear_categoria') return openCategoriaForm(null);
    if (action === 'editar') return getItem('/api/productos/' + id + '/').then(openProductoForm);
    if (action === 'editar_categoria') return getItem('/api/categorias/' + id + '/').then(openCategoriaForm);
    if (action === 'eliminar') {
      if (!confirm('¿Está seguro de que desea eliminar este producto? Esta acción no se puede deshacer.')) return;
      api('/api/productos/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Producto eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
    if (action === 'eliminar_categoria') {
      if (!confirm('¿Eliminar esta categoría? Solo se puede eliminar si no tiene productos asociados.')) return;
      api('/api/categorias/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Categoría eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ------------------------------------------------------------------
   * TIENDA (órdenes de compra y pagos del checkout)
   * ------------------------------------------------------------------ */
  var ORDEN_FLUJO = {
    pendiente: ['confirmado', 'cancelado'],
    confirmado: ['preparando', 'cancelado'],
    preparando: ['enviado', 'cancelado'],
    enviado: ['entregado', 'cancelado'],
    entregado: [],
    cancelado: [],
  };

  var ESTADO_ORDEN_LABEL = {
    pendiente: 'Pendiente', confirmado: 'Confirmado', preparando: 'Preparando',
    enviado: 'Enviado', entregado: 'Entregado', cancelado: 'Cancelado',
  };

  var METODO_PAGO_LABEL = {
    tarjeta: 'Tarjeta', paypal: 'PayPal', billetera: 'Billetera / app',
  };

  var ESTADO_PAGO_LABEL = {
    pendiente: 'Pendiente', aprobado: 'Aprobado', rechazado: 'Rechazado', reembolsado: 'Reembolsado',
  };

  function ultimoPago(orden) {
    return (orden.pagos && orden.pagos.length) ? orden.pagos[0] : null;
  }

  async function renderTienda() {
    sdCache = {};
    cssClear('tienda');
    setViewLoading();
    var state = st('tienda', { tab: 'ordenes', estado: '', metodo: '' });
    var html = tabsHTML(state, [
      { value: 'ordenes', label: 'Órdenes' },
      { value: 'pagos', label: 'Pagos' },
    ]);

    if (state.tab === 'pagos') {
      var colsTPagos;
      var cargarPagosTienda = function () {
        return fetchAll('/api/tienda/ordenes/').then(function (todas) {
          var filas = [];
          todas.forEach(function (o) {
            (o.pagos || []).forEach(function (p) {
              filas.push({
                orden: o.numero,
                cliente: o.cliente_display,
                metodo: p.metodo,
                metodo_display: p.metodo_display,
                estado: p.estado,
                estado_display: p.estado_display,
                monto: p.monto,
                moneda: p.moneda,
                referencia: p.referencia,
                ultimos_digitos: p.ultimos_digitos,
                marca_tarjeta: p.marca_tarjeta,
                fecha: p.created_at,
              });
            });
          });
          return filas;
        });
      };
      var filas;
      try {
        filas = await cargarPagosTienda();
      } catch (err) {
        setViewError(apiErrorMessage(err));
        return;
      }
      if (state.metodo) {
        filas = filas.filter(function (p) { return p.metodo === state.metodo; });
      }
      if (state.search) {
        var q = state.search.toLowerCase();
        filas = filas.filter(function (p) {
          return String(p.orden).toLowerCase().indexOf(q) >= 0 ||
                 String(p.referencia).toLowerCase().indexOf(q) >= 0 ||
                 String(p.cliente).toLowerCase().indexOf(q) >= 0;
        });
      }
      var desde = (state.page - 1) * PAGE_SIZE;
      var pagina = filas.slice(desde, desde + PAGE_SIZE);
      html += viewShell({
        state: state,
        data: { count: filas.length, previous: desde > 0, next: desde + PAGE_SIZE < filas.length },
        toolbar: {
          search: state.search,
          placeholder: 'Buscar por orden o referencia…',
          filters: [
            { name: 'metodo', label: 'Método', value: state.metodo, options: [
                { value: 'tarjeta', label: 'Tarjeta' }, { value: 'paypal', label: 'PayPal' },
                { value: 'billetera', label: 'Billetera / app' } ] },
          ],
        },
        columns: (colsTPagos = [
          { label: 'Orden', render: function (p) { return '<span class="font-semibold">' + esc(p.orden) + '</span>'; } },
          { label: 'Cliente', key: 'cliente' },
          { label: 'Método', render: function (p) { return esc(p.metodo_display); } },
          { label: 'Monto', render: function (p) { return '<span class="font-semibold">' + money(p.monto) + '</span>'; } },
          { label: 'Referencia', key: 'referencia' },
          { label: 'Tarjeta', render: function (p) {
              if (!p.ultimos_digitos) return '—';
              return esc(p.marca_tarjeta) + ' **** ' + esc(p.ultimos_digitos);
            } },
          { label: 'Estado', render: function (p) { return estadoBadge(p.estado, p.estado_display); } },
          { label: 'Fecha', render: function (p) { return fmtDT(p.fecha); } },
        ]),
        items: pagina,
      });
      $('#view').innerHTML = html;
      cssRegister({
        key: 'tienda:pagos',
        columns: colsTPagos,
        fields: ['orden', 'cliente', 'referencia', 'marca_tarjeta', 'metodo_display'],
        active: ['metodo'],
        source: cargarPagosTienda,
      });
      return;
    }

    var data;
    var colsTOrdenes;
    try {
      data = await loadList('/api/tienda/ordenes/', state, ['estado']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    html += viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por número, cliente o correo…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: [
              { value: 'pendiente', label: 'Pendiente' }, { value: 'confirmado', label: 'Confirmado' },
              { value: 'preparando', label: 'Preparando' }, { value: 'enviado', label: 'Enviado' },
              { value: 'entregado', label: 'Entregado' }, { value: 'cancelado', label: 'Cancelado' } ] },
        ],
      },
      columns: (colsTOrdenes = [
        { label: 'Orden', render: function (o) {
            return '<div class="font-semibold text-on-surface">' + esc(o.numero) + '</div>' +
                   '<div class="text-xs text-on-surface-variant">' + fmtDT(o.created_at) + '</div>';
          } },
        { label: 'Cliente', render: function (o) {
            return '<div class="font-medium text-on-surface">' + esc(o.cliente_display) + '</div>' +
                   '<div class="text-xs text-on-surface-variant">' + esc(o.email) + '</div>';
          } },
        { label: 'Método', render: function (o) {
            var p = ultimoPago(o);
            return esc((p && p.metodo_display) || o.metodo_pago || '—');
          } },
        { label: 'Total', render: function (o) { return '<span class="font-semibold">' + money(o.total) + '</span>'; } },
        { label: 'Pago', render: function (o) {
            var p = ultimoPago(o);
            if (!p) return '—';
            return estadoBadge(p.estado, p.estado_display);
          } },
        { label: 'Estado', render: function (o) { return estadoBadge(o.estado, o.estado_display); } },
        { label: 'Acciones', render: function (o) {
            var btns = [
              { kind: 'icon', action: 'ver_orden', icon: 'visibility', title: 'Ver detalle' },
              { kind: 'icon', action: 'estado_orden', icon: 'swap_horiz', title: 'Cambiar estado' },
            ];
            var p = ultimoPago(o);
            if ((isAdmin() || S.user.role === 'supervisor') && p && p.estado === 'aprobado') {
              btns.push({ kind: 'icon', action: 'reembolsar', icon: 'currency_exchange', title: 'Reembolsar', danger: true });
            }
            return actionBtns(o, btns);
          } },
      ]),
      items: data.results || [],
    });
    $('#view').innerHTML = html;
    cssRegister({
      key: 'tienda:ordenes',
      url: '/api/tienda/ordenes/',
      columns: colsTOrdenes,
      fields: ['numero', 'cliente_display', 'email', 'metodo_pago', 'estado_display'],
      active: ['estado'],
    });
  }

  function estadoFormHTML(orden) {
    var opciones = (ORDEN_FLUJO[orden.estado] || []).map(function (s) {
      return { value: s, label: ESTADO_ORDEN_LABEL[s] || s };
    });
    if (!opciones.length) {
      return '<p class="text-sm text-on-surface-variant">La orden en estado ' +
             esc(orden.estado_display || orden.estado) + ' no admite más cambios de estado.</p>';
    }
    var fields = [
      { name: 'estado', label: 'Nuevo estado', type: 'select', required: true, options: opciones },
      { name: 'comentario', label: 'Comentario (opcional)', type: 'textarea', span: 2, hint: 'Visible en el historial de la orden.' },
    ];
    return formHTML(fields);
  }

  function openOrdenDetalle(orden) {
    var items = (orden.items || []).map(function (it) {
      return '<div class="flex items-center gap-3">' +
        (it.imagen ? '<img src="' + esc(it.imagen) + '" alt="" class="h-10 w-10 rounded-lg object-cover" loading="lazy">' : '') +
        '<div class="min-w-0 flex-1"><div class="truncate font-medium text-on-surface">' + esc(it.nombre) + '</div>' +
        '<div class="text-xs text-on-surface-variant">' + it.cantidad + ' × ' + money(it.precio_unitario) + '</div></div>' +
        '<div class="font-semibold text-on-surface">' + money(it.subtotal) + '</div></div>';
    }).join('');
    if (!items) items = '<p class="text-sm text-on-surface-variant">Sin productos.</p>';

    var pagos = (orden.pagos || []).map(function (p) {
      var det = esc(p.metodo_display || METODO_PAGO_LABEL[p.metodo] || p.metodo);
      if (p.ultimos_digitos) det += ' · ' + esc(p.marca_tarjeta) + ' **** ' + esc(p.ultimos_digitos);
      if (p.referencia) det += ' · Ref: ' + esc(p.referencia);
      return '<div class="flex items-center justify-between gap-2 py-2">' +
             '<div class="text-sm text-on-surface-variant">' + det + '</div>' +
             estadoBadge(p.estado, p.estado_display) + '</div>';
    }).join('') || '<p class="text-sm text-on-surface-variant">Sin pagos registrados.</p>';

    var historial = (orden.historial || []).map(function (h) {
      return '<div class="flex items-start justify-between gap-2 py-2">' +
             '<div><div class="text-sm text-on-surface">' + esc(h.estado_anterior || '—') + ' → ' +
             esc(ESTADO_ORDEN_LABEL[h.estado_nuevo] || h.estado_nuevo) + '</div>' +
             (h.comentario ? '<div class="text-xs text-on-surface-variant">' + esc(h.comentario) + '</div>' : '') +
             '</div><div class="text-xs text-on-surface-variant">' + fmtDT(h.fecha) +
             (h.usuario_nombre ? ' · ' + esc(h.usuario_nombre) : '') + '</div></div>';
    }).join('') || '<p class="text-sm text-on-surface-variant">Sin cambios de estado registrados.</p>';

    var body = '' +
      '<div class="mb-4 flex flex-wrap items-center gap-2">' +
        '<span class="badge badge-primary">' + esc(orden.numero) + '</span>' +
        estadoBadge(orden.estado, orden.estado_display) +
      '</div>' +
      '<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">' +
        '<div class="rounded-xl bg-surface-dim p-4">' +
          '<p class="text-xs font-bold uppercase tracking-wide text-on-surface-variant">Cliente</p>' +
          '<p class="mt-1 font-semibold text-on-surface">' + esc(orden.cliente_display || orden.nombre_cliente) + '</p>' +
          '<p class="text-sm text-on-surface-variant">' + esc(orden.email) + '</p>' +
          '<p class="text-sm text-on-surface-variant">' + esc(orden.telefono) + '</p>' +
        '</div>' +
        '<div class="rounded-xl bg-surface-dim p-4">' +
          '<p class="text-xs font-bold uppercase tracking-wide text-on-surface-variant">Entrega</p>' +
          '<p class="mt-1 text-sm text-on-surface">' + esc(orden.direccion_entrega) + '</p>' +
          '<p class="text-sm text-on-surface-variant">' + esc(orden.ciudad_entrega) + '</p>' +
          (orden.referencia_entrega ? '<p class="text-sm text-on-surface-variant">Ref: ' + esc(orden.referencia_entrega) + '</p>' : '') +
        '</div>' +
      '</div>' +
      '<div class="mt-5">' +
        '<p class="text-sm font-bold text-on-surface">Productos</p>' +
        '<div class="mt-2 space-y-1">' + items + '</div>' +
        '<div class="mt-3 space-y-1 border-t border-outline-variant pt-3 text-sm">' +
          '<div class="flex justify-between"><span class="text-on-surface-variant">Subtotal</span><span>' + money(orden.subtotal) + '</span></div>' +
          '<div class="flex justify-between"><span class="text-on-surface-variant">Envío</span><span>' + money(orden.envio) + '</span></div>' +
          '<div class="flex justify-between text-base font-bold text-on-surface"><span>Total</span><span>' + money(orden.total) + '</span></div>' +
        '</div>' +
      '</div>' +
      '<div class="mt-5">' +
        '<p class="text-sm font-bold text-on-surface">Pagos</p>' +
        '<div class="mt-1 divide-y divide-outline-variant">' + pagos + '</div>' +
      '</div>' +
      '<div class="mt-5">' +
        '<p class="text-sm font-bold text-on-surface">Historial de estados</p>' +
        '<div class="mt-1 divide-y divide-outline-variant">' + historial + '</div>' +
      '</div>' +
      (orden.notas ? '<div class="mt-5"><p class="text-sm font-bold text-on-surface">Notas</p>' +
        '<p class="mt-1 text-sm text-on-surface-variant">' + esc(orden.notas) + '</p></div>' : '');

    openModal('Detalle de la orden ' + orden.numero, body, { footer: '' });
  }

  function openCambioEstado(orden) {
    openModal('Cambiar estado · ' + orden.numero, estadoFormHTML(orden), {
      footer: modalFooter('Cancelar', 'Guardar cambio'),
    });
    var form = $('#modalForm');
    if (!form) return;
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        await api('/api/tienda/ordenes/' + orden.id + '/estado/', {
          method: 'PATCH',
          body: JSON.stringify({ estado: data.estado, comentario: data.comentario || '' }),
        });
        toast('Estado de la orden actualizado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function tiendaAction(action, id) {
    if (action === 'ver_orden') {
      getItem('/api/tienda/ordenes/' + id + '/').then(openOrdenDetalle);
      return;
    }
    if (action === 'estado_orden') {
      getItem('/api/tienda/ordenes/' + id + '/').then(openCambioEstado);
      return;
    }
    if (action === 'reembolsar') {
      if (!confirm('¿Reembolsar el último pago aprobado de esta orden?')) return;
      api('/api/tienda/ordenes/' + id + '/reembolsar/', { method: 'POST', body: '{}' })
        .then(function () { toast('Pago reembolsado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ------------------------------------------------------------------
   * SERVICIOS (ÓRDENES DE SERVICIO)
   * ------------------------------------------------------------------ */
  var ESTADOS_SERVICIO = [
    { value: 'pendiente', label: 'Pendiente' }, { value: 'asignada', label: 'Asignada' },
    { value: 'en_proceso', label: 'En proceso' }, { value: 'reprogramada', label: 'Reprogramada' },
    { value: 'finalizada', label: 'Finalizada' }, { value: 'cancelada', label: 'Cancelada' },
  ];

  var TIPOS_SERVICIO = [
    { value: 'instalacion', label: 'Instalación' }, { value: 'reparacion', label: 'Reparación' },
    { value: 'mantenimiento_preventivo', label: 'Mantenimiento preventivo' },
    { value: 'mantenimiento_correctivo', label: 'Mantenimiento correctivo' },
    { value: 'diagnostico', label: 'Diagnóstico' }, { value: 'revision', label: 'Revisión' },
  ];

  async function renderServicios() {
    sdCache = {};
    cssClear('servicios');   // lista completa fresca
    setViewLoading();
    var state = st('servicios', { estado: '', tipo_servicio: '' });
    var data;
    try {
      data = await loadList('/api/servicios/', state, ['estado', 'tipo_servicio']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var canManage = STAFF_ROLES.indexOf(S.user.role) >= 0;
    var canCreateOrder = S.user.role === 'administrador' || S.user.role === 'supervisor';
    var canRequestRepair = S.user.role === 'cliente';
    var html = '';
    if (state.tipo_servicio === 'reparacion') {
      html += '<div class="info-banner"><span class="material-symbols-outlined text-base">build</span>' +
              'Mostrando órdenes de reparación.</div>';
    }
    var columns = [
      { label: 'N°', render: function (o) { return '<span class="font-semibold">' + esc(o.numero) + '</span>'; } },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Equipo', render: function (o) { return o.equipo_nombre ? esc(o.equipo_nombre) : '—'; } },
      { label: 'Técnico', render: function (o) { return o.tecnico_nombre ? esc(o.tecnico_nombre) : '—'; } },
      { label: 'Tipo', render: function (o) { return esc(o.tipo_servicio_display); } },
      { label: 'Fecha', render: function (o) { return fmtDate(o.fecha); } },
      { label: 'Estado', render: function (o) { return estadoBadge(o.estado, o.estado_display); } },
      { label: 'Evid.', render: function (o) { return o.total_evidencias || 0; } },
    ];
    if (canManage) columns.push({ label: 'Acciones', render: function (o) {
          var btns = [
            { kind: 'icon', action: 'ver', icon: 'visibility', title: 'Ver detalle' },
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
            { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(o, btns);
        } });
    else columns.push({ label: 'Acciones', render: function (o) {
          return actionBtns(o, [{ kind: 'icon', action: 'ver', icon: 'visibility', title: 'Ver detalle' }]);
        } });
    html += viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por número, cliente, equipo, diagnóstico…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: ESTADOS_SERVICIO },
          { name: 'tipo_servicio', label: 'Tipo', value: state.tipo_servicio, options: TIPOS_SERVICIO },
        ],
        buttons: canCreateOrder ? [{ action: 'crear', icon: 'add', label: S.user.role === 'supervisor' ? 'Agregar Trabajo' : 'Nueva orden' }]
                                : canRequestRepair ? [{ action: 'crear', icon: 'add', label: 'Solicitar reparación' }]
                                : [],
      },
      columns: columns,
      items: data.results || [],
    });
    $('#view').innerHTML = html;
    clientSideSearch({
      key: 'servicios',
      url: '/api/servicios/',
      columns: columns,
      // Solo búsqueda client-side cuando no hay filtros de estado/tipo activos;
      // si hay un filtro, se mantiene el comportamiento de servidor existente.
      active: function () {
        var s = currentListState();
        return !s || (!s.estado && !s.tipo_servicio);
      },
      filter: function (o, q) {
        q = q.toLowerCase();
        return (o.numero || '').toLowerCase().indexOf(q) >= 0 ||
               (o.cliente_nombre || '').toLowerCase().indexOf(q) >= 0 ||
               (o.equipo_nombre || '').toLowerCase().indexOf(q) >= 0 ||
               (o.tecnico_nombre || '').toLowerCase().indexOf(q) >= 0 ||
               (o.problema_reportado || '').toLowerCase().indexOf(q) >= 0 ||
               (o.diagnostico || '').toLowerCase().indexOf(q) >= 0;
      },
    });
  }

  function serviciosAction(action, id) {
    if (action === 'crear') return openServicioForm(null);
    if (action === 'editar') return getItem('/api/servicios/' + id + '/').then(openServicioForm);
    if (action === 'ver') return getItem('/api/servicios/' + id + '/').then(openServicioDetalle);
    if (action === 'estado') return getItem('/api/servicios/' + id + '/').then(function (o) {
      openEstadoModal('servicios', o, ESTADOS_SERVICIO);
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar esta orden de servicio?')) return;
      api('/api/servicios/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Orden eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  function openServicioDetalle(o) {
    function f(label, value) {
      return '<div class="sm:col-span-2"><p class="text-xs font-semibold uppercase tracking-wide text-on-surface-variant">' +
             esc(label) + '</p><p class="mt-0.5 text-sm text-on-surface whitespace-pre-wrap">' + (value || '—') + '</p></div>';
    }
    var html = '<div class="flex items-center justify-between">' +
               '<div class="text-sm font-bold text-on-surface">' + esc(o.numero) + ' · ' + esc(o.tipo_servicio_display) + '</div>' +
               estadoBadge(o.estado, o.estado_display) + '</div>';
    html += '<div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">';
    html += f('Cliente', o.cliente_nombre);
    html += f('Equipo', o.equipo_nombre);
    html += f('Técnico asignado', o.tecnico_nombre);
    html += f('Fecha', fmtDate(o.fecha));
    html += f('Problema reportado', o.problema_reportado);
    html += f('Diagnóstico', o.diagnostico);
    html += f('Trabajo realizado', o.trabajo_realizado);
    html += f('Observaciones técnicas', o.observaciones);
    if (o.materiales_utilizados && o.materiales_utilizados.length) {
      var matCols = [
        { label: 'Material', key: 'material_nombre' },
        { label: 'Cant.', key: 'cantidad' },
      ];
      if (S.user.role !== 'tecnico') {
        matCols.push({ label: 'Subtotal', render: function (m) { return money(m.subtotal); } });
      }
      html += '<div class="sm:col-span-2"><p class="mb-2 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">Materiales utilizados</p>' +
              buildTable(matCols, o.materiales_utilizados) + '</div>';
    }
    html += '</div>';
    openModal('Orden ' + esc(o.numero), html, {
      width: '720px',
      footer: '<button type="button" class="btn btn-ghost" data-close>Cerrar</button>' +
              (S.user.role === 'cliente' ? '' :
               '<button type="button" class="btn btn-ghost" data-pdf="' + o.id + '"><span class="material-symbols-outlined text-sm">picture_as_pdf</span>PDF</button>' +
               '<button type="button" class="btn btn-primary" id="btnEditarServicio">Editar</button>'),
    });
    var btnEditar = $('#btnEditarServicio');
    if (btnEditar) btnEditar.addEventListener('click', function () { openServicioForm(o); });
    var btnPdf = document.querySelector('[data-pdf]');
    if (btnPdf) btnPdf.addEventListener('click', async function () {
      var id = btnPdf.dataset.pdf;
      var token = localStorage.getItem('refri_access');
      try {
        var res = await fetch(API_BASE + '/api/servicios/' + id + '/pdf/', {
          headers: token ? { 'Authorization': 'Bearer ' + token } : {},
        });
        if (res.status === 401) { toast('Sesión expirada. Vuelve a iniciar sesión.', 'error'); return; }
        if (!res.ok) { toast('No se pudo descargar el PDF.', 'error'); return; }
        var blob = await res.blob();
        var url = URL.createObjectURL(blob);
        window.open(url, '_blank');
      } catch (e) { toast('Error al descargar el PDF.', 'error'); }
    });
  }

  async function openServicioForm(item) {
    var isClient = S.user.role === 'cliente';
    var isTecnico = S.user.role === 'tecnico';
    var equipos = [], tecnicos = [];
    try { equipos = await fetchAll('/api/equipos/'); } catch (e) {}
    function equipoLabel(e) {
      return [e.tipo_nombre, e.marca, e.modelo, e.numero_serie].filter(Boolean).join(' · ');
    }
    var fields;
    if (isClient) {
      fields = [
        { name: 'equipo', label: 'Equipo', type: 'select', value: item ? item.equipo : '',
          options: optList(equipos, 'id', equipoLabel) },
        { name: 'tipo_servicio', label: 'Tipo de servicio', type: 'select', value: item ? item.tipo_servicio : 'reparacion',
          options: TIPOS_SERVICIO },
        { name: 'fecha', label: 'Fecha', type: 'date', required: true, value: item ? item.fecha : new Date().toISOString().slice(0, 10) },
        { name: 'problema_reportado', label: 'Problema reportado', type: 'textarea', span: 2, required: true,
          value: item ? item.problema_reportado : '', placeholder: 'Describe la falla o el servicio que necesitas…' },
      ];
    } else if (isTecnico) {
      fields = [
        { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pendiente', options: ESTADOS_SERVICIO },
        { name: 'diagnostico', label: 'Diagnóstico', type: 'textarea', span: 2, value: item ? item.diagnostico : '' },
        { name: 'trabajo_realizado', label: 'Trabajo realizado', type: 'textarea', span: 2, value: item ? item.trabajo_realizado : '' },
        { name: 'observaciones', label: 'Observaciones técnicas', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
      ];
    } else {
      try { tecnicos = await fetchAll('/api/tecnicos/'); } catch (e) {}
      fields = [
        { name: 'equipo', label: 'Equipo', type: 'select', value: item ? item.equipo : '',
          options: optList(equipos, 'id', equipoLabel) },
        { name: 'tecnico', label: 'Técnico asignado', type: 'select', value: item ? item.tecnico : '',
          options: optList(tecnicos, 'id', 'nombre') },
        { name: 'tipo_servicio', label: 'Tipo de servicio', type: 'select', value: item ? item.tipo_servicio : 'reparacion',
          options: TIPOS_SERVICIO },
        { name: 'fecha', label: 'Fecha', type: 'date', required: true, value: item ? item.fecha : new Date().toISOString().slice(0, 10) },
        { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pendiente', options: ESTADOS_SERVICIO },
        { name: 'problema_reportado', label: 'Problema reportado', type: 'textarea', span: 2, value: item ? item.problema_reportado : '' },
        { name: 'diagnostico', label: 'Diagnóstico', type: 'textarea', span: 2, value: item ? item.diagnostico : '' },
        { name: 'trabajo_realizado', label: 'Trabajo realizado', type: 'textarea', span: 2, value: item ? item.trabajo_realizado : '' },
        { name: 'observaciones', label: 'Observaciones técnicas', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
      ];
    }
    var sinEquipos = isClient && !equipos.length;
    var clienteSearchHTML = '';
    if (!isClient && !isTecnico) {
      var cliVal = item ? item.cliente : '';
      var cliNombre = item ? (item.cliente_nombre || '') : '';
      clienteSearchHTML =
        '<div class="mb-3">' +
          '<label class="field-label" for="f_cliente_search">Buscar cliente</label>' +
          '<div style="position:relative">' +
            '<input id="f_cliente_search" class="adm-input" type="text" placeholder="Escribe nombre o apellido del cliente…" autocomplete="off" value="' + esc(cliNombre) + '" style="width:100%">' +
            '<input id="f_cliente" name="cliente" type="hidden" value="' + esc(cliVal) + '">' +
            '<div id="f_cliente_results" class="hidden" style="position:absolute;top:100%;left:0;right:0;z-index:50;background:#fff;border:1px solid #e2e8f0;border-radius:0.5rem;max-height:240px;overflow-y:auto;box-shadow:0 4px 6px -1px rgb(0 0 0 / 0.1);margin-top:2px"></div>' +
          '</div>' +
          '<p id="f_cliente_hint" class="mt-1 text-xs text-on-surface-variant">' +
            (cliVal ? '<span class="text-success">Cliente seleccionado</span>' : 'Escribe al menos 2 caracteres para buscar') +
          '</p>' +
        '</div>';
    }
    var body = (sinEquipos
      ? '<div class="info-banner mb-3"><span class="material-symbols-outlined text-base">info</span>' +
        '<span class="flex-1">Aún no has registrado equipos. Regístralo desde <strong>Mis equipos</strong> para poder solicitar el servicio.</span>' +
        '<button type="button" class="btn btn-primary" data-ir-mis-equipos>Ir a Mis equipos</button></div>'
      : '') + clienteSearchHTML + formHTML(fields);
    var modal = openModal(item ? 'Editar orden #' + item.numero : (isClient ? 'Solicitar reparación' : S.user.role === 'supervisor' ? 'Nuevo Trabajo' : 'Nueva orden de servicio'), body, {
      width: '720px',
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : (isClient ? 'Enviar solicitud' : S.user.role === 'supervisor' ? 'Crear trabajo' : 'Crear orden')),
    });
    var btnIr = modal.querySelector('[data-ir-mis-equipos]');
    if (btnIr) btnIr.addEventListener('click', function () { closeModal(); go('mis_equipos'); });
    var cliSearch = modal.querySelector('#f_cliente_search');
    var cliHidden = modal.querySelector('#f_cliente');
    var cliResults = modal.querySelector('#f_cliente_results');
    var cliHint = modal.querySelector('#f_cliente_hint');
    if (cliSearch && cliHidden && cliResults) {
      var cliTimer = null;
      cliSearch.addEventListener('input', function () {
        clearTimeout(cliTimer);
        var q = cliSearch.value.trim();
        if (q.length < 2) { cliResults.classList.add('hidden'); return; }
        cliTimer = setTimeout(async function () {
          try {
            var data = await api('/api/clientes/disponibles/?search=' + encodeURIComponent(q));
            var list = Array.isArray(data) ? data : (data.results || []);
            if (!list.length) {
              cliResults.innerHTML = '<div class="px-3 py-2 text-sm text-on-surface-variant">No se encontraron clientes</div>';
              cliResults.classList.remove('hidden');
              return;
            }
            cliResults.innerHTML = list.map(function (c) {
              return '<div class="cli-suggest-item" data-id="' + c.id + '" data-name="' + esc(c.nombre_completo) + '" ' +
                'style="padding:8px 12px;cursor:pointer;font-size:14px;border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:8px">' +
                '<span class="material-symbols-outlined text-sm text-on-surface-variant">person</span>' +
                '<span>' + esc(c.nombre_completo) + '</span>' +
                '<span class="ml-auto text-xs text-on-surface-variant">' + esc(c.ciudad || '') + '</span>' +
              '</div>';
            }).join('');
            cliResults.classList.remove('hidden');
          } catch (e) { /* ignore */ }
        }, 350);
      });
      cliResults.addEventListener('mousedown', function (e) {
        var opt = e.target.closest('.cli-suggest-item');
        if (!opt) return;
        e.preventDefault();
        cliHidden.value = opt.dataset.id;
        cliSearch.value = opt.dataset.name;
        cliResults.classList.add('hidden');
        if (cliHint) cliHint.innerHTML = '<span class="text-success">Cliente seleccionado</span>';
      });
      cliSearch.addEventListener('blur', function () {
        setTimeout(function () { cliResults.classList.add('hidden'); }, 200);
      });
    }
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['equipo', 'tecnico', 'cliente']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/servicios/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/servicios/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Orden actualizada.' : (isClient ? 'Solicitud registrada correctamente.' : S.user.role === 'supervisor' ? 'Trabajo creado.' : 'Orden de servicio creada.'), 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  /* ------------------------------------------------------------------
   * MANTENIMIENTOS
   * ------------------------------------------------------------------ */
  var ESTADOS_MANTENIMIENTO = [
    { value: 'pendiente', label: 'Pendiente' }, { value: 'en_proceso', label: 'En proceso' },
    { value: 'realizado', label: 'Realizado' }, { value: 'cancelado', label: 'Cancelado' },
  ];

  async function renderMantenimientos() {
    sdCache = {};
    cssClear('mantenimientos');
    setViewLoading();
    var state = st('mantenimientos', { estado: '', tipo: '' });
    var flag = state.proximos ? 'proximos' : (state.vencidos ? 'vencidos' : '');
    var url = flag === 'proximos' ? '/api/mantenimientos/proximos/'
            : flag === 'vencidos' ? '/api/mantenimientos/vencidos/'
            : '/api/mantenimientos/';
    var data;
    try {
      data = await loadList(url, state, ['estado', 'tipo']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var html = '';
    if (flag === 'proximos') {
      html += '<div class="info-banner"><span class="material-symbols-outlined text-base">event_available</span>' +
              'Mostrando mantenimientos con próxima fecha dentro de los próximos 30 días.</div>';
    } else if (flag === 'vencidos') {
      html += '<div class="info-banner"><span class="material-symbols-outlined text-base">event_busy</span>' +
              'Mostrando mantenimientos vencidos (próxima fecha anterior a hoy).</div>';
    }
    var canManage = STAFF_ROLES.indexOf(S.user.role) >= 0;
    var isTecnico = S.user.role === 'tecnico';
    var columns = [
      { label: 'Equipo', key: 'equipo_nombre' },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Técnico', render: function (m) { return m.tecnico_nombre ? esc(m.tecnico_nombre) : '—'; } },
      { label: 'Tipo', render: function (m) { return esc(m.tipo_display); } },
      { label: 'Fecha', render: function (m) { return fmtDate(m.fecha); } },
      { label: 'Próxima fecha', render: function (m) { return m.proxima_fecha ? fmtDate(m.proxima_fecha) : '—'; } },
      { label: 'Estado', render: function (m) { return estadoBadge(m.estado, m.estado_display); } },
    ];
    if (!isTecnico) columns.push({ label: 'Costo', render: function (m) { return money(m.costo); } });
    if (canManage) columns.push({ label: 'Acciones', render: function (m) {
          var btns = [
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
            { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(m, btns);
        } });
    html += viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por equipo, cliente, descripción…',
        filters: [
          { name: 'tipo', label: 'Tipo', value: state.tipo, options: [
              { value: 'preventivo', label: 'Preventivo' }, { value: 'correctivo', label: 'Correctivo' } ] },
          { name: 'estado', label: 'Estado', value: state.estado, options: ESTADOS_MANTENIMIENTO },
        ],
        buttons: canManage ? [{ action: 'crear', icon: 'add', label: 'Nuevo mantenimiento' }]
                           : [],
      },
      columns: columns,
      items: data.results || [],
    });
    $('#view').innerHTML = html;
    cssRegister({
      key: 'mantenimientos',
      url: '/api/mantenimientos/',
      columns: columns,
      fields: ['equipo_nombre', 'cliente_nombre', 'tecnico_nombre', 'tipo_display', 'descripcion', 'estado_display'],
      active: ['estado', 'tipo', 'proximos', 'vencidos'],
    });
  }

  function mantenimientosAction(action, id) {
    if (action === 'crear') return openMantenimientoForm(null);
    if (action === 'editar') return getItem('/api/mantenimientos/' + id + '/').then(openMantenimientoForm);
    if (action === 'estado') return getItem('/api/mantenimientos/' + id + '/').then(function (m) {
      openEstadoModal('mantenimientos', m, ESTADOS_MANTENIMIENTO);
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar este mantenimiento?')) return;
      api('/api/mantenimientos/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Mantenimiento eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  async function openMantenimientoForm(item) {
    var isClient = S.user.role === 'cliente';
    var isTecnico = S.user.role === 'tecnico';
    var clientes = [], equipos = [], tecnicos = [];
    try { equipos = await fetchAll('/api/equipos/'); } catch (e) {}
    function equipoLabel(e) {
      return [e.tipo_nombre, e.marca, e.modelo, e.numero_serie].filter(Boolean).join(' · ');
    }
    var fields;
    if (isClient) {
      fields = [
        { name: 'equipo', label: 'Equipo', type: 'select', required: true, value: item ? item.equipo : '',
          options: optList(equipos, 'id', equipoLabel) },
        { name: 'tipo', label: 'Tipo de mantenimiento', type: 'select', value: item ? item.tipo : 'preventivo',
          options: [{ value: 'preventivo', label: 'Preventivo' }, { value: 'correctivo', label: 'Correctivo' }] },
        { name: 'fecha', label: 'Fecha deseada', type: 'date', required: true, value: item ? item.fecha : new Date().toISOString().slice(0, 10) },
        { name: 'descripcion', label: 'Descripción del mantenimiento', type: 'textarea', span: 2, required: true,
          value: item ? item.descripcion : '', placeholder: 'Describe el equipo y el servicio que necesitas…' },
      ];
    } else if (isTecnico) {
      fields = [
        { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pendiente', options: ESTADOS_MANTENIMIENTO },
        { name: 'trabajo_realizado', label: 'Trabajo realizado', type: 'textarea', span: 2, value: item ? item.trabajo_realizado : '' },
        { name: 'observaciones', label: 'Observaciones', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
      ];
    } else {
      try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) {}
      try { tecnicos = await fetchAll('/api/tecnicos/'); } catch (e) {}
      fields = [
        { name: 'equipo', label: 'Equipo', type: 'select', required: true, value: item ? item.equipo : '',
          options: optList(equipos, 'id', equipoLabel) },
        { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: item ? item.cliente : '',
          options: optList(clientes, 'id', 'nombre_completo') },
        { name: 'tecnico', label: 'Técnico responsable', type: 'select', value: item ? item.tecnico : '',
          options: optList(tecnicos, 'id', 'nombre') },
        { name: 'tipo', label: 'Tipo de mantenimiento', type: 'select', value: item ? item.tipo : 'preventivo',
          options: [{ value: 'preventivo', label: 'Preventivo' }, { value: 'correctivo', label: 'Correctivo' }] },
        { name: 'fecha', label: 'Fecha', type: 'date', required: true, value: item ? item.fecha : new Date().toISOString().slice(0, 10) },
        { name: 'proxima_fecha', label: 'Próxima fecha', type: 'date', value: item ? item.proxima_fecha : '' },
        { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pendiente', options: ESTADOS_MANTENIMIENTO },
        { name: 'costo', label: 'Costo', type: 'number', min: 0, step: 0.01, value: item ? item.costo : '0' },
        { name: 'descripcion', label: 'Descripción', type: 'textarea', span: 2, value: item ? item.descripcion : '' },
        { name: 'trabajo_realizado', label: 'Trabajo realizado', type: 'textarea', span: 2, value: item ? item.trabajo_realizado : '' },
        { name: 'observaciones', label: 'Observaciones', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
      ];
    }
    var sinEquipos = isClient && !equipos.length;
    var body = (sinEquipos
      ? '<div class="info-banner mb-3"><span class="material-symbols-outlined text-base">info</span>' +
        '<span class="flex-1">Aún no has registrado equipos. Regístralo desde <strong>Mis equipos</strong> para poder solicitar el servicio.</span>' +
        '<button type="button" class="btn btn-primary" data-ir-mis-equipos>Ir a Mis equipos</button></div>'
      : '') + formHTML(fields);
    var modal = openModal(isClient ? 'Solicitar mantenimiento' : (item ? 'Editar mantenimiento' : 'Nuevo mantenimiento'), body, {
      width: '720px',
      footer: modalFooter('Cancelar', isClient ? 'Enviar solicitud' : (item ? 'Guardar cambios' : 'Crear mantenimiento')),
    });
    var btnIr = modal.querySelector('[data-ir-mis-equipos]');
    if (btnIr) btnIr.addEventListener('click', function () { closeModal(); go('mis_equipos'); });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['tecnico', 'proxima_fecha']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/mantenimientos/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/mantenimientos/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Mantenimiento actualizado.' : (isClient ? 'Solicitud registrada correctamente.' : 'Mantenimiento creado.'), 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  /* ------------------------------------------------------------------
   * EVALUACIONES / CALIFICACIONES
   * ------------------------------------------------------------------ */
  async function renderEvaluaciones() {
    sdCache = {};
    cssClear('evaluaciones');
    setViewLoading();
    if (S.user.role === 'cliente') return renderMisEvaluaciones();
    var state = st('evaluaciones', { calificacion: '' });
    var data;
    try {
      data = await loadList('/api/evaluaciones/', state, ['calificacion']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    function stars(n) {
      var s = '';
      for (var i = 0; i < 5; i++) s += i < n ? '★' : '☆';
      return '<span class="text-warning">' + s + '</span>';
    }
    var columns = [
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Orden', render: function (e) { return e.orden_numero ? esc(e.orden_numero) : '—'; } },
      { label: 'Instalación', render: function (e) { return e.instalacion_id ? '#' + e.instalacion_id : '—'; } },
      { label: 'Calificación', render: function (e) {
          return stars(e.calificacion) + ' <span class="text-xs text-on-surface-variant">' + e.calificacion + '/5</span>';
        } },
      { label: 'Comentario', render: function (e) { return e.comentario ? esc(e.comentario) : '—'; } },
      { label: 'Fecha', render: function (e) { return fmtDT(e.fecha); } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por cliente o comentario…',
        filters: [
          { name: 'calificacion', label: 'Calificación', value: state.calificacion, options: [
              { value: '5', label: '5 estrellas' }, { value: '4', label: '4 estrellas' },
              { value: '3', label: '3 estrellas' }, { value: '2', label: '2 estrellas' },
              { value: '1', label: '1 estrella' } ] },
        ],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'evaluaciones',
      url: '/api/evaluaciones/',
      columns: columns,
      fields: ['cliente_nombre', 'comentario', 'orden_numero', 'instalacion_id'],
      active: ['calificacion'],
    });
  }

  async function renderMisEvaluaciones() {
    var servicios, misEvals;
    try {
      servicios = await fetchAll('/api/servicios/?estado=finalizada');
      misEvals = await fetchAll('/api/evaluaciones/');
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var evaluados = {};
    misEvals.forEach(function (e) {
      if (e.orden) evaluados['o' + e.orden] = true;
      if (e.instalacion) evaluados['i' + e.instalacion] = true;
    });
    var pendientes = servicios.filter(function (o) { return !evaluados['o' + o.id]; });

    var html = '<div class="space-y-5">';

    html += '<div class="panel-card p-5">' +
            '<h3 class="text-sm font-bold tracking-tight text-on-surface">Servicios listos para evaluar</h3>' +
            '<p class="mt-0.5 text-xs text-on-surface-variant">' +
            'Califica el servicio recibido. Solo puedes evaluar servicios finalizados y una sola vez por orden (RN-10).</p>' +
            '<div class="mt-4 space-y-3">';
    if (!pendientes.length) {
      html += '<div class="flex flex-col items-center justify-center py-10 text-center">' +
              '<span class="material-symbols-outlined text-4xl text-outline">task_alt</span>' +
              '<p class="mt-2 text-sm text-on-surface-variant">No tienes servicios finalizados pendientes de evaluar.</p></div>';
    } else {
      html += pendientes.map(function (o) {
        return '<div class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-outline-variant p-4">' +
               '<div class="min-w-0 flex-1">' +
                 '<div class="font-semibold text-on-surface">' + esc(o.numero) + ' · ' +
                 esc(o.tipo_servicio_display || 'Servicio') + '</div>' +
                 '<div class="mt-0.5 text-xs text-on-surface-variant">' +
                 'Fecha: ' + fmtDate(o.fecha) + (o.tecnico_nombre ? ' · Técnico: ' + esc(o.tecnico_nombre) : '') + '</div>' +
               '</div>' +
               '<button class="btn btn-primary" data-action="evaluar" data-id="' + o.id + '">' +
               '<span class="material-symbols-outlined text-sm">star</span>Evaluar</button>' +
               '</div>';
      }).join('');
    }
    html += '</div></div>';

    html += '<div class="panel-card p-5"><h3 class="text-sm font-bold tracking-tight text-on-surface">Mis evaluaciones</h3>' +
            '<div class="mt-4">' +
            buildTable([
              { label: 'Servicio', render: function (e) { return e.orden_numero ? esc(e.orden_numero) : '—'; } },
              { label: 'Calificación', render: function (e) {
                  var s = '';
                  for (var i = 0; i < 5; i++) s += i < e.calificacion ? '★' : '☆';
                  return '<span class="text-warning">' + s + '</span>';
                } },
              { label: 'Comentario', render: function (e) { return e.comentario ? esc(e.comentario) : '—'; } },
              { label: 'Fecha', render: function (e) { return fmtDT(e.fecha); } },
            ], misEvals) +
            '</div></div>';

    html += '</div>';
    $('#view').innerHTML = html;
  }

  function evaluacionesAction(action, id) {
    if (action === 'evaluar') {
      getItem('/api/servicios/' + id + '/').then(openEvalModal);
    }
  }

  function openEvalModal(orden) {
    var fields = [
      { name: 'calificacion', label: 'Calificación', type: 'select', required: true, value: '5', options: [
          { value: '5', label: '5 — Excelente' }, { value: '4', label: '4 — Muy bueno' },
          { value: '3', label: '3 — Bueno' }, { value: '2', label: '2 — Regular' },
          { value: '1', label: '1 — Malo' } ] },
      { name: 'comentario', label: 'Comentario (opcional)', type: 'textarea', span: 2, value: '',
        placeholder: 'Cuéntanos cómo fue el servicio…' },
    ];
    openModal('Evaluar servicio ' + orden.numero, formHTML(fields), {
      width: '560px',
      footer: modalFooter('Cancelar', 'Enviar evaluación'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      data.orden = orden.id;
      data.calificacion = Number(data.calificacion);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        await api('/api/evaluaciones/', { method: 'POST', body: JSON.stringify(data) });
        toast('Evaluación enviada. ¡Gracias por tu opinión!', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  /* ------------------------------------------------------------------
   * REPORTES
   * ------------------------------------------------------------------ */
  async function renderReportes() {
    setViewLoading();
    var d;
    try {
      d = await api('/api/dashboard/');
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var porTecnico = [], instPorMes = [], servPorMes = [], stockBajo = [];
    try {
      porTecnico = await api('/api/dashboard/servicios-por-tecnico/');
      instPorMes = await api('/api/dashboard/instalaciones-por-mes/');
      servPorMes = await api('/api/dashboard/servicios-por-mes/');
      stockBajo = await api('/api/dashboard/materiales-stock-bajo/');
    } catch (e) { /* opcional */ }

    var html = '<div class="space-y-5">';

    html += '<div class="flex flex-wrap items-center gap-2">' +
      '<span class="text-sm font-semibold text-on-surface">Exportar reporte:</span>' +
      '<select id="exportTipo" class="adm-select w-auto">' +
        '<option value="general">General</option><option value="instalaciones">Instalaciones</option>' +
        '<option value="servicios">Servicios</option><option value="materiales">Materiales</option>' +
        '<option value="pagos">Pagos</option>' +
      '</select>' +
      '<button data-export="pdf" class="btn btn-ghost"><span class="material-symbols-outlined text-sm">picture_as_pdf</span>PDF</button>' +
      '<button data-export="xlsx" class="btn btn-ghost"><span class="material-symbols-outlined text-sm">table_view</span>Excel</button>' +
    '</div>';

    html += '<div class="grid grid-cols-2 gap-4 md:grid-cols-4">';
    html += statCard('Instalaciones realizadas', d.instalaciones_realizadas, 'task_alt', 'text-success');
    html += statCard('Servicios completados', d.servicios_completados, 'check_circle', 'text-success');
    html += statCard('Pagos recibidos', money(d.total_pagos), 'payments', 'text-success');
    html += statCard('Calificación promedio', d.calificacion_promedio != null
                     ? Number(d.calificacion_promedio).toFixed(1) : '—', 'star', 'text-warning');
    html += '</div>';

    html += '<div class="grid gap-4 xl:grid-cols-2">';
    html += barChartHTML('Servicios por mes', servPorMes.map(function (r) {
      return { label: r.mes, value: r.total };
    }));
    html += barChartHTML('Instalaciones por mes', instPorMes.map(function (r) {
      return { label: r.mes, value: r.total };
    }));
    html += '</div>';

    html += '<div class="grid gap-4 xl:grid-cols-2">';
    html += '<div class="panel-card p-5"><h3 class="text-sm font-bold tracking-tight text-on-surface">' +
            'Ordenes por técnico</h3><div class="mt-4">' +
            buildTable([
              { label: 'Técnico', render: function (t) { return esc(t.nombre || ('#' + t.tecnico_id)); } },
              { label: 'Total', render: function (t) { return '<span class="badge badge-primary">' + t.total_ordenes + '</span>'; } },
              { label: 'Finalizadas', render: function (t) { return '<span class="badge badge-success">' + t.finalizadas + '</span>'; } },
            ], porTecnico) + '</div></div>';

    html += '<div class="panel-card p-5"><h3 class="text-sm font-bold tracking-tight text-on-surface">' +
            'Materiales con stock bajo</h3><div class="mt-4">' +
            buildTable([
              { label: 'Código', key: 'codigo' },
              { label: 'Material', key: 'nombre' },
              { label: 'Disponible', render: function (m) { return money(m.cantidad_disponible); } },
              { label: 'Mínimo', render: function (m) { return money(m.stock_minimo); } },
            ], stockBajo) + '</div></div>';
    html += '</div>';

    html += '</div>';
    $('#view').innerHTML = html;
    $$('#view [data-export]').forEach(function (b) {
      b.addEventListener('click', function () { exportarReporte(b.dataset.export); });
    });
  }

  /* ------------------------------------------------------------------
   * USUARIOS Y ROLES
   * ------------------------------------------------------------------ */
  async function renderUsuarios() {
    sdCache = {};
    cssClear('usuarios');
    setViewLoading();
    var state = st('usuarios', { role: '' });
    var data;
    try {
      data = await loadList('/api/usuarios/', state, ['role']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Usuario', render: function (u) {
          return '<div class="font-semibold text-on-surface">' + esc(u.username) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">' + esc(u.full_name || '—') + '</div>';
        } },
      { label: 'Correo', key: 'email' },
      { label: 'Rol', render: function (u) { return estadoBadge(u.role, u.role_display); } },
      { label: 'Teléfono', key: 'phone' },
      { label: 'Activo', render: function (u) {
          return u.is_active ? '<span class="badge badge-success">Activo</span>'
                             : '<span class="badge badge-error">Inactivo</span>';
        } },
      { label: 'Creado', render: function (u) { return fmtDate(u.date_joined); } },
      { label: 'Acciones', render: function (u) {
          var btns = [{ kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' }];
          if (canDelete() && u.id !== S.user.id) {
            btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          }
          return actionBtns(u, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por usuario, correo, nombre…',
        filters: [
          { name: 'role', label: 'Rol', value: state.role, options: [
              { value: 'administrador', label: 'Administrador' }, { value: 'supervisor', label: 'Supervisor' },
              { value: 'tecnico', label: 'Técnico' }, { value: 'almacen', label: 'Almacén' },
              { value: 'cliente', label: 'Cliente' } ] },
        ],
        buttons: [{ action: 'crear', icon: 'person_add', label: 'Nuevo usuario' }],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'usuarios',
      url: '/api/usuarios/',
      columns: columns,
      fields: ['username', 'full_name', 'email', 'phone', 'role_display'],
      active: ['role'],
    });
  }

  /* ------------------------------------------------------------------
   * PERFIL
   * ------------------------------------------------------------------ */
  var pendingFoto = null;
  var TIPO_DOC_CHOICES = [
    { value: 'cc', label: 'Cédula' }, { value: 'pasaporte', label: 'Pasaporte' },
    { value: 'rnc', label: 'RNC (empresa)' }, { value: 'nit', label: 'NIT' },
    { value: 'otro', label: 'Otro' },
  ];

  function applyUser(user) {
    if (!user) return;
    S.user = Object.assign({}, S.user || {}, user);
    localStorage.setItem('refri_user', JSON.stringify(S.user));
    renderUser();
  }

  function avatarHTML(p) {
    return p.photo
      ? '<img src="' + esc(p.photo) + '" alt="Foto de perfil">'
      : '<span class="profile-photo-fallback">' + esc(initials(p.full_name || p.username)) + '</span>';
  }

  async function renderPerfil() {
    setViewLoading();
    var data;
    try {
      data = await api('/api/auth/me/perfil/');
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var p = data.perfil || {};
    var role = p.role || S.user.role;
    var isCliente = role === 'cliente';
    var isTecnico = role === 'tecnico';

    var html = '<div class="space-y-5">';

    html += '<div class="panel-card p-6">' +
      '<div class="flex flex-col items-center gap-5 sm:flex-row">' +
        '<div class="profile-photo">' + avatarHTML(p) + '</div>' +
        '<div class="flex-1 text-center sm:text-left">' +
          '<h2 class="text-xl font-bold tracking-tight text-on-surface">' + esc(p.full_name || p.username) + '</h2>' +
          '<p class="mt-0.5 text-sm text-on-surface-variant">@' + esc(p.username) + ' · ' +
            esc(p.role_display || role) + '</p>' +
          '<p class="mt-1 text-xs text-on-surface-variant">' +
            (isCliente ? 'Edita tus datos personales y tu foto de perfil.'
                       : isTecnico ? 'Edita tus datos profesionales y tu foto de perfil.'
                                   : 'Edita tus datos personales y tu foto de perfil.') +
          '</p>' +
          '<div class="mt-4 flex flex-wrap justify-center gap-2 sm:justify-start">' +
            '<button data-action="subir_foto" class="btn btn-primary">' +
              '<span class="material-symbols-outlined text-sm">upload</span>Cambiar foto</button>' +
            (p.photo ? '<button data-action="eliminar_foto" class="btn btn-ghost">' +
              '<span class="material-symbols-outlined text-sm">delete</span>Eliminar foto</button>' : '') +
          '</div>' +
        '</div>' +
      '</div>' +
      '<input id="fotoInput" type="file" accept="image/jpeg,image/png,image/gif,image/webp,image/avif" class="hidden">' +
      '<div id="fotoPreviewWrap" class="mt-4 hidden rounded-xl border border-dashed border-outline bg-surface-container-low p-4 text-center">' +
        '<img id="fotoPreview" class="mx-auto h-28 w-28 rounded-full object-cover" alt="Vista previa">' +
        '<p class="mt-2 text-sm text-on-surface-variant">Vista previa de tu nueva foto de perfil.</p>' +
        '<div class="mt-3 flex justify-center gap-2">' +
          '<button data-action="guardar_foto" class="btn btn-primary">' +
            '<span class="material-symbols-outlined text-sm">save</span>Guardar foto</button>' +
          '<button data-action="cancelar_foto" class="btn btn-ghost">Cancelar</button>' +
        '</div>' +
      '</div>' +
    '</div>';

    var fields = [];
    if (isCliente) {
      fields.push({ name: 'nombre', label: 'Nombre', type: 'text', required: true, value: p.nombre });
      fields.push({ name: 'apellidos', label: 'Apellidos', type: 'text', value: p.apellidos });
      fields.push({ name: 'tipo_documento', label: 'Tipo de documento', type: 'select',
        value: p.tipo_documento || 'cc', options: TIPO_DOC_CHOICES });
      fields.push({ name: 'documento_numero', label: 'Número de documento', type: 'text',
        required: true, value: p.documento_numero });
      fields.push({ name: 'email', label: 'Correo electrónico', type: 'email',
        required: true, value: p.email });
      fields.push({ name: 'telefono', label: 'Teléfono', type: 'tel', value: p.telefono });
      fields.push({ name: 'telefono_alternativo', label: 'Teléfono alternativo', type: 'tel',
        value: p.telefono_alternativo });
      fields.push({ name: 'direccion', label: 'Dirección', type: 'text', span: 2, value: p.direccion });
      fields.push({ name: 'ciudad', label: 'Ciudad', type: 'text', value: p.ciudad });
    } else if (isTecnico) {
      fields.push({ name: 'first_name', label: 'Nombre', type: 'text', required: true, value: p.first_name });
      fields.push({ name: 'last_name', label: 'Apellidos', type: 'text', value: p.last_name });
      fields.push({ name: 'email', label: 'Correo electrónico', type: 'email',
        required: true, value: p.email });
      fields.push({ name: 'telefono', label: 'Teléfono', type: 'tel', value: p.telefono });
      fields.push({ name: 'especialidad', label: 'Especialidad', type: 'text', span: 2, value: p.especialidad });
      fields.push({ name: 'direccion', label: 'Dirección', type: 'text', span: 2, value: p.direccion });
    } else {
      fields.push({ name: 'first_name', label: 'Nombre', type: 'text', required: true, value: p.first_name });
      fields.push({ name: 'last_name', label: 'Apellidos', type: 'text', value: p.last_name });
      fields.push({ name: 'email', label: 'Correo electrónico', type: 'email',
        required: true, value: p.email });
      fields.push({ name: 'phone', label: 'Teléfono', type: 'tel', value: p.phone });
    }

    html += '<form id="perfilForm" class="panel-card p-6">' +
      '<div class="flex items-center gap-2">' +
        '<span class="material-symbols-outlined text-primary">badge</span>' +
        '<h3 class="text-sm font-bold tracking-tight text-on-surface">Información personal</h3>' +
      '</div>' +
      '<div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">' + fields.map(fieldHTML).join('') + '</div>' +
      '<div class="mt-5 flex justify-end">' +
        '<button type="submit" class="btn btn-primary">' +
          '<span class="material-symbols-outlined text-sm">save</span>Guardar cambios</button>' +
      '</div>' +
    '</form>';

    html += '<form id="seguridadForm" class="panel-card p-6">' +
      '<div class="flex items-center gap-2">' +
        '<span class="material-symbols-outlined text-primary">lock</span>' +
        '<h3 class="text-sm font-bold tracking-tight text-on-surface">Seguridad</h3>' +
      '</div>' +
      '<p class="mt-1 text-xs text-on-surface-variant">Cambia tu contraseña verificando la contraseña actual. Al cambiarla deberás volver a iniciar sesión.</p>' +
      '<p id="seguridadMsg" class="mt-4 hidden rounded-lg px-3 py-2 text-sm"></p>' +
      '<div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">' +
        '<div class="sm:col-span-2">' +
          '<label class="field-label" for="segActual">Contraseña actual</label>' +
          '<input id="segActual" class="input" type="password" placeholder="••••••••" autocomplete="current-password" required>' +
        '</div>' +
        '<div>' +
          '<label class="field-label" for="segNueva">Nueva contraseña</label>' +
          '<input id="segNueva" class="input" type="password" placeholder="Mínimo 8 caracteres" autocomplete="new-password" required>' +
        '</div>' +
        '<div>' +
          '<label class="field-label" for="segNueva2">Confirmar nueva contraseña</label>' +
          '<input id="segNueva2" class="input" type="password" placeholder="Repite la contraseña" autocomplete="new-password" required>' +
        '</div>' +
      '</div>' +
      '<p class="mt-2 text-xs text-slate-500">Mínimo 8 caracteres. Evita contraseñas solo numéricas o muy comunes.</p>' +
      '<div class="mt-5 flex justify-end">' +
        '<button type="submit" class="btn btn-primary">' +
          '<span class="material-symbols-outlined text-sm">lock_reset</span>Cambiar contraseña</button>' +
      '</div>' +
    '</form>';

    html += '</div>';
    $('#view').innerHTML = html;

    $('#fotoInput').addEventListener('change', function (e) {
      var file = e.target.files && e.target.files[0];
      if (!file) return;
      if (!/^image\/(jpeg|png|gif|webp|avif)$/.test(file.type)) {
        toast('Formato no permitido (JPG, PNG, GIF, WEBP o AVIF).', 'error');
        e.target.value = '';
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        toast('La imagen supera el tamaño máximo de 5 MB.', 'error');
        e.target.value = '';
        return;
      }
      pendingFoto = file;
      $('#fotoPreview').src = (window.URL || window.webkitURL).createObjectURL(file);
      $('#fotoPreviewWrap').classList.remove('hidden');
      $('#fotoPreviewWrap').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });

    $('#perfilForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = e.target.querySelector('[type=submit]');
      var data = getFormData(e.target);
      setBusy(btn, true);
      api('/api/auth/me/perfil/', { method: 'PATCH', body: JSON.stringify(data) })
        .then(function (r) {
          applyUser(r.perfil);
          toast(r.message || 'Perfil actualizado correctamente.', 'success');
          reloadCurrent();
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); })
        .then(function () { setBusy(btn, false); });
    });

    $('#seguridadForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var msg = $('#seguridadMsg');
      var actual = $('#segActual').value;
      var nueva = $('#segNueva').value;
      var nueva2 = $('#segNueva2').value;
      function setMsg(text, ok) {
        msg.classList.remove('hidden', 'text-red-700', 'bg-red-50', 'border', 'border-red-200',
          'text-emerald-700', 'bg-emerald-50', 'border-emerald-200');
        if (!text) return;
        msg.textContent = text;
        msg.classList.add(ok
          ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
          : 'text-red-700 bg-red-50 border border-red-200');
      }
      if (!actual) { setMsg('Ingresa tu contraseña actual.', false); return; }
      if (nueva.length < 8) { setMsg('La nueva contraseña debe tener al menos 8 caracteres.', false); return; }
      if (/^\d+$/.test(nueva)) { setMsg('La nueva contraseña no puede ser solo números.', false); return; }
      if (nueva !== nueva2) { setMsg('Las contraseñas nuevas no coinciden.', false); return; }
      setMsg('', false);
      msg.classList.add('hidden');
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      api('/api/auth/password/cambiar/', {
        method: 'POST',
        body: JSON.stringify({ password_actual: actual, nueva_password: nueva, confirmar_nueva_password: nueva2 }),
      })
        .then(function (r) {
          clearSession();
          window.location.href = '/';
        })
        .catch(function (err) {
          setMsg(apiErrorMessage(err), false);
          setBusy(btn, false);
        });
    });
  }

  function guardarFoto() {
    var file = pendingFoto;
    if (!file) { toast('Primero selecciona una imagen.', 'error'); return; }
    var fd = new FormData();
    fd.append('foto', file);
    var btn = $('#view [data-action="guardar_foto"]');
    setBusy(btn, true);
    apiUpload('/api/auth/me/foto/', fd)
      .then(function (r) {
        applyUser(r.user);
        pendingFoto = null;
        var inp = $('#fotoInput');
        if (inp) inp.value = '';
        var wrap = $('#fotoPreviewWrap');
        if (wrap) wrap.classList.add('hidden');
        toast(r.message || 'Foto de perfil actualizada.', 'success');
        reloadCurrent();
      })
      .catch(function (err) {
        var d = err && err.data;
        if (!d && err && err.body) {
          var texto = String(err.body).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
          d = texto ? { detail: 'Error HTTP ' + err.status + ': ' + texto.slice(0, 300) } : { detail: 'Error HTTP ' + err.status };
        }
        toast(apiErrorMessage(Object.assign({}, err, { data: d || null })), 'error');
      })
      .then(function () { setBusy(btn, false); });
  }

  function perfilAction(action, id) {
    if (action === 'subir_foto') {
      var inp = $('#fotoInput');
      if (inp) inp.click();
      return;
    }
    if (action === 'cancelar_foto') {
      pendingFoto = null;
      var inp = $('#fotoInput');
      if (inp) inp.value = '';
      var wrap = $('#fotoPreviewWrap');
      if (wrap) wrap.classList.add('hidden');
      return;
    }
    if (action === 'guardar_foto') return guardarFoto();
    if (action === 'eliminar_foto') {
      if (!confirm('¿Eliminar tu foto de perfil?')) return;
      api('/api/auth/me/foto/', { method: 'POST', body: JSON.stringify({ eliminar: true }) })
        .then(function (r) {
          applyUser(r.user);
          toast(r.message || 'Foto de perfil eliminada.', 'success');
          reloadCurrent();
        })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }
  var VISITA_ESTADOS = [
    { value: 'programada', label: 'Programada' },
    { value: 'en_curso', label: 'En curso' },
    { value: 'realizada', label: 'Realizada' },
    { value: 'cancelada', label: 'Cancelada' },
  ];

  async function renderVisitas() {
    sdCache = {};
    cssClear('visitas');
    setViewLoading();
    var state = st('visitas', { estado: '' });
    var data;
    try {
      data = await loadList('/api/visitas/', state, ['estado']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Visita', render: function (v) {
          return '<div class="font-semibold text-on-surface">' + esc(v.numero) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">' + esc(v.motivo || '—') + '</div>';
        } },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Orden', render: function (v) { return v.orden_numero ? esc(v.orden_numero) : '—'; } },
      { label: 'Técnico', render: function (v) { return v.tecnico_nombre ? esc(v.tecnico_nombre) : '—'; } },
      { label: 'Fecha', render: function (v) { return fmtDate(v.fecha); } },
      { label: 'Hora', render: function (v) { return v.hora ? esc(String(v.hora).slice(0, 5)) : '—'; } },
      { label: 'Dirección', render: function (v) { return v.direccion ? esc(v.direccion) : '—'; } },
      { label: 'Estado', render: function (v) { return estadoBadge(v.estado, v.estado_display); } },
      { label: 'Acciones', render: function (v) {
          var btns = [
            { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(v, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por número, cliente, motivo…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: VISITA_ESTADOS },
        ],
        buttons: [{ action: 'crear', icon: 'add', label: 'Nueva visita' }],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'visitas',
      url: '/api/visitas/',
      columns: columns,
      fields: ['numero', 'motivo', 'cliente_nombre', 'orden_numero', 'tecnico_nombre', 'direccion', 'estado_display'],
      active: ['estado'],
    });
  }

  function visitasAction(action, id) {
    if (action === 'crear') return openVisitaForm(null);
    if (action === 'editar') return getItem('/api/visitas/' + id + '/').then(openVisitaForm);
    if (action === 'estado') return getItem('/api/visitas/' + id + '/').then(function (v) {
      openEstadoModal('visitas', v, VISITA_ESTADOS);
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar esta visita técnica?')) return;
      api('/api/visitas/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Visita eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  async function openVisitaForm(item) {
    var clientes = [], ordenes = [], tecnicos = [];
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) { clientes = []; }
    try { ordenes = await fetchAll('/api/servicios/'); } catch (e) { ordenes = []; }
    try { tecnicos = await fetchAll('/api/tecnicos/'); } catch (e) { tecnicos = []; }
    var fields = [
      { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: item ? item.cliente : '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'orden', label: 'Orden de servicio', type: 'select', value: item ? item.orden : '',
        options: optList(ordenes, 'id', function (o) {
          return o.numero + ' · ' + o.cliente_nombre + ' · ' + (o.tipo_servicio_display || '');
        }) },
      { name: 'tecnico', label: 'Técnico asignado', type: 'select', value: item ? item.tecnico : '',
        options: optList(tecnicos, 'id', 'nombre') },
      { name: 'fecha', label: 'Fecha', type: 'date', required: true, value: item ? item.fecha : new Date().toISOString().slice(0, 10) },
      { name: 'hora', label: 'Hora', type: 'time', value: item ? (item.hora || '').slice(0, 5) : '' },
      { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'programada', options: VISITA_ESTADOS },
      { name: 'direccion', label: 'Dirección de la visita', type: 'text', span: 2, value: item ? item.direccion : '',
        placeholder: 'Dirección donde se realizará la visita (por defecto la del cliente).' },
      { name: 'motivo', label: 'Motivo de la visita', type: 'textarea', span: 2, value: item ? item.motivo : '',
        placeholder: 'Ej: Diagnóstico del equipo, medición de espacio, cotización in situ…' },
      { name: 'observaciones', label: 'Observaciones', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
    ];
    openModal(item ? 'Editar visita técnica' : 'Nueva visita técnica', formHTML(fields), {
      width: '720px',
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Registrar visita'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['orden', 'tecnico', 'hora']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/visitas/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/visitas/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Visita actualizada.' : 'Visita registrada.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  /* ------------------------------------------------------------------
   * COTIZACIONES (RF-17)
   * ------------------------------------------------------------------ */
  var COT_ESTADOS = [
    { value: 'pendiente', label: 'Pendiente' },
    { value: 'aprobada', label: 'Aprobada' },
    { value: 'rechazada', label: 'Rechazada' },
    { value: 'vencida', label: 'Vencida' },
  ];

  async function renderCotizaciones() {
    sdCache = {};
    cssClear('cotizaciones');
    setViewLoading();
    var state = st('cotizaciones', { estado: '' });
    var data;
    try {
      data = await loadList('/api/cotizaciones/', state, ['estado']);
    } catch (err) {
      setViewError(apiErrorMessage(err));
      return;
    }
    var columns = [
      { label: 'Cotización', render: function (c) {
          return '<div class="font-semibold text-on-surface">' + esc(c.numero) + '</div>' +
                 '<div class="text-xs text-on-surface-variant">' + fmtDate(c.fecha) + '</div>';
        } },
      { label: 'Cliente', key: 'cliente_nombre' },
      { label: 'Solicitud', render: function (c) { return c.solicitud_numero ? '#' + c.solicitud_numero : '—'; } },
      { label: 'Técnico', render: function (c) { return c.tecnico_nombre ? esc(c.tecnico_nombre) : '—'; } },
      { label: 'Subtotal', render: function (c) { return money(c.subtotal); } },
      { label: 'Total', render: function (c) { return '<span class="font-semibold text-on-surface">' + money(c.total) + '</span>'; } },
      { label: 'Estado', render: function (c) { return estadoBadge(c.estado, c.estado_display); } },
      { label: 'Acciones', render: function (c) {
          var btns = [
            { kind: 'icon', action: 'ver', icon: 'visibility', title: 'Ver detalle' },
            { kind: 'icon', action: 'estado', icon: 'swap_horiz', title: 'Cambiar estado' },
            { kind: 'icon', action: 'editar', icon: 'edit', title: 'Editar' },
          ];
          if (canDelete()) btns.push({ kind: 'icon', action: 'eliminar', icon: 'delete', title: 'Eliminar', danger: true });
          return actionBtns(c, btns);
        } },
    ];
    $('#view').innerHTML = viewShell({
      state: state,
      data: data,
      toolbar: {
        search: state.search,
        placeholder: 'Buscar por número, cliente, notas…',
        filters: [
          { name: 'estado', label: 'Estado', value: state.estado, options: COT_ESTADOS },
        ],
        buttons: [{ action: 'crear', icon: 'add', label: 'Nueva cotización' }],
      },
      columns: columns,
      items: data.results || [],
    });
    cssRegister({
      key: 'cotizaciones',
      url: '/api/cotizaciones/',
      columns: columns,
      fields: ['numero', 'cliente_nombre', 'tecnico_nombre', 'notas', 'estado_display'],
      active: ['estado'],
    });
  }

  function cotizacionesAction(action, id) {
    if (action === 'crear') return openCotizacionForm(null);
    if (action === 'ver') return getItem('/api/cotizaciones/' + id + '/').then(openCotizacionDetalle);
    if (action === 'editar') return getItem('/api/cotizaciones/' + id + '/').then(openCotizacionForm);
    if (action === 'estado') return getItem('/api/cotizaciones/' + id + '/').then(function (c) {
      openEstadoModal('cotizaciones', c, COT_ESTADOS);
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar esta cotización?')) return;
      api('/api/cotizaciones/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Cotización eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  async function openCotizacionForm(item) {
    var clientes = [], solicitudes = [], tecnicos = [];
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) { clientes = []; }
    try { solicitudes = await fetchAll('/api/solicitudes/'); } catch (e) { solicitudes = []; }
    try { tecnicos = await fetchAll('/api/tecnicos/'); } catch (e) { tecnicos = []; }

    var detalles = item && item.detalles ? item.detalles.map(function (d) {
      return { descripcion: d.descripcion, cantidad: String(d.cantidad), precio_unitario: String(d.precio_unitario) };
    }) : [];

    var fields = [
      { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: item ? item.cliente : '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'solicitud', label: 'Solicitud relacionada', type: 'select', value: item ? item.solicitud : '',
        options: optList(solicitudes, 'id', function (s) { return '#' + s.id + ' · ' + s.tipo_equipo_solicitado; }) },
      { name: 'tecnico', label: 'Técnico que cotiza', type: 'select', value: item ? item.tecnico : '',
        options: optList(tecnicos, 'id', 'nombre') },
      { name: 'validez_dias', label: 'Días de validez', type: 'number', min: 1, value: item ? item.validez_dias : '30' },
      { name: 'descuento', label: 'Descuento (DOP)', type: 'number', min: 0, step: 0.01, value: item ? String(item.descuento) : '0' },
      { name: 'notas', label: 'Notas', type: 'textarea', span: 2, value: item ? item.notas : '' },
    ];

    var body = formHTML(fields);
    body += '<div class="col-span-full mt-1 border-t border-outline-variant pt-3">' +
            '<div class="flex items-center justify-between">' +
              '<p class="font-semibold text-sm text-on-surface">Conceptos</p>' +
              '<button type="button" id="addDetalle" class="btn btn-primary">' +
                '<span class="material-symbols-outlined text-sm">add</span>Agregar concepto</button>' +
            '</div>' +
            '<div id="detallesWrap" class="mt-3 space-y-2"></div>' +
            '<div class="mt-3 flex flex-wrap items-center justify-end gap-6 border-t border-outline-variant pt-3">' +
              '<div class="text-sm text-on-surface-variant">Subtotal: <span id="detSubtotal" class="font-semibold text-on-surface">' + money(0) + '</span></div>' +
              '<div class="text-sm text-on-surface-variant">Total: <span id="detTotal" class="font-semibold text-primary">' + money(0) + '</span></div>' +
            '</div>' +
          '</div>';

    var modal = openModal(item ? 'Editar cotización' : 'Nueva cotización', body, {
      width: '860px',
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear cotización'),
    });

    var wrap = $('#detallesWrap');
    var subtotalEl = $('#detSubtotal');
    var totalEl = $('#detTotal');

    function detalleRowHTML(d) {
      return '<div class="detalle-row flex items-start gap-2">' +
        '<input type="text" class="adm-input det-desc flex-1" placeholder="Descripción del concepto" value="' + esc(d.descripcion) + '">' +
        '<input type="number" class="adm-input det-cant w-24" min="0" step="0.01" value="' + esc(d.cantidad) + '" placeholder="Cant.">' +
        '<input type="number" class="adm-input det-precio w-32" min="0" step="0.01" value="' + esc(d.precio_unitario) + '" placeholder="Precio unit.">' +
        '<button type="button" class="btn btn-ghost p-1.5 det-del" title="Quitar concepto">' +
          '<span class="material-symbols-outlined text-base text-error">delete</span></button>' +
      '</div>';
    }

    function renderRows() {
      wrap.innerHTML = detalles.map(detalleRowHTML).join('');
      recalcTotales();
    }

    function recalcTotales() {
      var subtotal = 0;
      $$('.detalle-row', wrap).forEach(function (row) {
        var cant = parseFloat($('.det-cant', row).value) || 0;
        var prec = parseFloat($('.det-precio', row).value) || 0;
        subtotal += cant * prec;
      });
      var desc = parseFloat($('#f_descuento').value) || 0;
      var total = Math.max(0, subtotal - desc);
      if (subtotalEl) subtotalEl.textContent = money(subtotal);
      if (totalEl) totalEl.textContent = money(total);
    }

    $('#addDetalle').addEventListener('click', function () {
      detalles.push({ descripcion: '', cantidad: '1', precio_unitario: '' });
      renderRows();
    });

    wrap.addEventListener('input', function (e) {
      var row = e.target.closest('.detalle-row');
      if (!row) return;
      var idx = Array.prototype.indexOf.call(wrap.children, row);
      if (idx < 0) return;
      if (e.target.classList.contains('det-desc')) detalles[idx].descripcion = e.target.value;
      else if (e.target.classList.contains('det-cant')) detalles[idx].cantidad = e.target.value;
      else if (e.target.classList.contains('det-precio')) detalles[idx].precio_unitario = e.target.value;
      recalcTotales();
    });

    wrap.addEventListener('click', function (e) {
      var btn = e.target.closest('.det-del');
      if (!btn) return;
      var row = btn.closest('.detalle-row');
      var idx = Array.prototype.indexOf.call(wrap.children, row);
      if (idx >= 0) detalles.splice(idx, 1);
      renderRows();
    });

    var descInput = $('#f_descuento');
    if (descInput) descInput.addEventListener('input', recalcTotales);

    renderRows();

    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['solicitud', 'tecnico']);
      var items = [];
      detalles.forEach(function (d) {
        var desc = (d.descripcion || '').trim();
        if (!desc) return;
        var cant = parseFloat(d.cantidad);
        var prec = parseFloat(d.precio_unitario);
        if (!isFinite(cant)) cant = 1;
        if (!isFinite(prec) || prec < 0) return;
        items.push({ descripcion: desc, cantidad: cant, precio_unitario: prec });
      });
      if (!data.cliente) { toast('Selecciona un cliente.', 'error'); return; }
      if (!items.length) { toast('Agrega al menos un concepto con descripción y precio.', 'error'); return; }
      if (!data.validez_dias) data.validez_dias = 30;
      if (data.descuento == null) data.descuento = 0;
      data.detalles = items;
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/cotizaciones/' + item.id + '/', { method: 'PUT', body: JSON.stringify(data) });
        else await api('/api/cotizaciones/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Cotización actualizada.' : 'Cotización creada.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function openCotizacionDetalle(c) {
    var body = '<div class="space-y-4">';
    body += '<div class="grid grid-cols-2 gap-3 text-sm">' +
      '<div><p class="text-xs text-on-surface-variant">Número</p>' +
      '<p class="font-semibold text-on-surface">' + esc(c.numero) + '</p></div>' +
      '<div><p class="text-xs text-on-surface-variant">Fecha</p>' +
      '<p class="font-semibold text-on-surface">' + fmtDate(c.fecha) + '</p></div>' +
      '<div><p class="text-xs text-on-surface-variant">Cliente</p>' +
      '<p class="font-semibold text-on-surface">' + esc(c.cliente_nombre) + '</p></div>' +
      '<div><p class="text-xs text-on-surface-variant">Técnico</p>' +
      '<p class="font-semibold text-on-surface">' + (c.tecnico_nombre ? esc(c.tecnico_nombre) : '—') + '</p></div>' +
      '<div><p class="text-xs text-on-surface-variant">Validez</p>' +
      '<p class="font-semibold text-on-surface">' + c.validez_dias + ' días</p></div>' +
      '<div><p class="text-xs text-on-surface-variant">Estado</p>' + estadoBadge(c.estado, c.estado_display) + '</div>' +
    '</div>';
    body += buildTable([
      { label: 'Descripción', key: 'descripcion' },
      { label: 'Cantidad', key: 'cantidad' },
      { label: 'Precio unitario', render: function (d) { return money(d.precio_unitario); } },
      { label: 'Total', render: function (d) { return money(d.total); } },
    ], c.detalles || []);
    body += '<div class="flex flex-wrap items-center justify-end gap-6 text-sm">' +
      '<span class="text-on-surface-variant">Subtotal: <span class="font-semibold text-on-surface">' + money(c.subtotal) + '</span></span>' +
      '<span class="text-on-surface-variant">Descuento: <span class="font-semibold text-on-surface">' + money(c.descuento) + '</span></span>' +
      '<span class="text-on-surface-variant">Total: <span class="font-semibold text-primary">' + money(c.total) + '</span></span>' +
    '</div>';
    if (c.notas) {
      body += '<div class="text-sm"><p class="text-xs text-on-surface-variant">Notas</p>' +
              '<p class="text-on-surface">' + esc(c.notas) + '</p></div>';
    }
    body += '</div>';
    openModal('Cotización ' + c.numero, body, {
      width: '780px',
      footer: '<button type="button" class="btn btn-ghost" data-close>Cerrar</button>',
    });
  }

  /* ------------------------------------------------------------------
   * Acciones por sección
   * ------------------------------------------------------------------ */
  function currentListState() {
    return listState[S.section] || null;
  }

  function reloadCurrent() {
    var fn = renderers[S.section];
    if (fn) fn();
  }

  async function getItem(url) {
    return api(url);
  }

  /* ---------- CLIENTES ---------- */
  async function openClientesForm(item) {
    var fields = [
      { name: 'tipo', label: 'Tipo', type: 'select', required: true, value: item ? item.tipo : 'persona',
        options: [{ value: 'persona', label: 'Persona natural' }, { value: 'empresa', label: 'Empresa' }] },
      { name: 'nombre', label: 'Nombre', type: 'text', required: true, value: item ? item.nombre : '' },
      { name: 'apellidos', label: 'Apellidos', type: 'text', value: item ? item.apellidos : '' },
      { name: 'tipo_documento', label: 'Tipo de documento', type: 'select', required: true, value: item ? item.tipo_documento : 'cc',
        options: [{ value: 'cc', label: 'Cédula' }, { value: 'pasaporte', label: 'Pasaporte' },
                  { value: 'rnc', label: 'RNC (empresa)' }, { value: 'nit', label: 'NIT' },
                  { value: 'otro', label: 'Otro' }] },
      { name: 'documento_numero', label: 'Número de documento', type: 'text', required: true, value: item ? item.documento_numero : '' },
      { name: 'email', label: 'Correo', type: 'email', required: true, value: item ? item.email : '' },
      { name: 'telefono', label: 'Teléfono', type: 'tel', value: item ? item.telefono : '' },
      { name: 'telefono_alternativo', label: 'Teléfono alternativo', type: 'tel', value: item ? item.telefono_alternativo : '' },
      { name: 'direccion', label: 'Dirección', type: 'text', span: 2, value: item ? item.direccion : '' },
      { name: 'ciudad', label: 'Ciudad', type: 'text', value: item ? item.ciudad : '' },
      { name: 'notas', label: 'Notas', type: 'textarea', span: 2, value: item ? item.notas : '' },
    ];
    if (item) {
      fields.push({ name: 'fecha_registro', label: 'Fecha de registro', type: 'text', disabled: true,
        value: fmtDT(item.fecha_registro), span: 2 });
    }
    fields.push({ name: 'divider_cuenta', label: 'Cuenta de acceso', type: 'divider' });
    if (item && item.user) {
      fields.push({ name: 'usuario_acceso', label: 'Usuario de acceso', type: 'text', disabled: true, value: item.username || '' });
      fields.push({ name: 'cuenta_password', label: 'Nueva contraseña (opcional)', type: 'password', value: '',
        hint: 'Solo si deseas cambiar la contraseña.' });
    } else {
      fields.push({ name: 'cuenta_username', label: 'Usuario de acceso', type: 'text', value: item && item.username ? item.username : '',
        hint: 'Déjalo vacío para no crear cuenta.' });
      fields.push({ name: 'cuenta_password', label: 'Contraseña', type: 'password', value: '',
        hint: 'Requerida para crear la cuenta de acceso.' });
    }
    openModal(item ? 'Editar cliente' : 'Nuevo cliente', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear cliente'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/clientes/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(getFormData(e.target)) });
        else await api('/api/clientes/', { method: 'POST', body: JSON.stringify(getFormData(e.target)) });
        toast(item ? 'Cliente actualizado.' : 'Cliente creado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function clientesAction(action, id) {
    if (action === 'crear') return openClientesForm(null);
    if (action === 'editar') return getItem('/api/clientes/' + id + '/').then(openClientesForm);
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar este cliente? Esta acción no se puede deshacer.')) return;
      api('/api/clientes/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Cliente eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  // Detalle de solo lectura del cliente (se abre al hacer clic en la fila).
  function openClienteDetail(c) {
    var fila = function (label, valor) {
      return '<div class="flex justify-between gap-6"><span class="text-on-surface-variant">' + esc(label) +
             '</span><span class="font-semibold text-right">' + (valor == null || valor === '' ? '—' : valor) + '</span></div>';
    };
    var html = '<div class="space-y-2 text-sm">' +
      fila('Tipo', c.tipo === 'empresa' ? 'Empresa' : 'Persona natural') +
      (c.apellidos ? fila('Apellidos', esc(c.apellidos)) : '') +
      fila('Documento', (c.tipo_documento_display ? esc(c.tipo_documento_display) + ': ' : '') + esc(c.documento_numero)) +
      fila('Correo', esc(c.email_contacto || c.email)) +
      fila('Teléfono', esc(c.telefono)) +
      fila('Teléfono alternativo', esc(c.telefono_alternativo)) +
      fila('Dirección', esc(c.direccion)) +
      fila('Ciudad', esc(c.ciudad)) +
      fila('Equipos', String(c.total_equipos != null ? c.total_equipos : 0)) +
      fila('Fecha de registro', fmtDT(c.fecha_registro)) +
      (c.username ? fila('Usuario de acceso', esc(c.username)) : '') +
      '</div>';
    if (c.notas) {
      html += '<div class="mt-4 border-t border-outline-variant pt-3 text-sm"><span class="text-on-surface-variant">Notas</span>' +
              '<p class="mt-1">' + esc(c.notas) + '</p></div>';
    }
    if (c.direcciones && c.direcciones.length) {
      html += '<div class="mt-4"><h4 class="mb-2 text-sm font-bold text-on-surface">Direcciones de instalación</h4>' +
              buildTable([
                { label: 'Etiqueta', key: 'etiqueta' },
                { label: 'Dirección', key: 'direccion' },
                { label: 'Ciudad', key: 'ciudad' },
                { label: 'Referencia', key: 'referencia' },
              ], c.direcciones) + '</div>';
    }
    openModal('Cliente: ' + esc(c.nombre_completo), html, {
      width: '560px',
      footer: '<button class="btn btn-primary" data-close>Cerrar</button>',
    });
  }

  /* ---------- USUARIOS (compartido con técnicos) ---------- */
  var ROLES = [
    { value: 'administrador', label: 'Administrador' },
    { value: 'supervisor', label: 'Supervisor' },
    { value: 'tecnico', label: 'Técnico' },
    { value: 'almacen', label: 'Almacén' },
    { value: 'cliente', label: 'Cliente' },
  ];

  function openUserModal(user, opts) {
    opts = opts || {};
    var roleFixed = opts.roleFixed || null;
    var fields = [
      { name: 'username', label: 'Usuario', type: 'text', required: true, value: user ? user.username : '', disabled: !!user },
      { name: 'email', label: 'Correo', type: 'email', required: true, value: user ? user.email : '' },
      { name: 'first_name', label: 'Nombre', type: 'text', value: user ? user.first_name : '' },
      { name: 'last_name', label: 'Apellidos', type: 'text', value: user ? user.last_name : '' },
      { name: 'phone', label: 'Teléfono', type: 'tel', value: user ? user.phone : '' },
      { name: 'role', label: 'Rol', type: 'select', required: true,
        value: user ? user.role : (roleFixed || 'cliente'), disabled: !!roleFixed, options: ROLES },
      { name: 'is_active', label: 'Usuario activo', type: 'checkbox', value: user ? !!user.is_active : true },
      { name: 'password', label: 'Contraseña', type: 'password', required: !user,
        value: '', placeholder: user ? 'Dejar vacía para no cambiar' : 'Mínimo 8 caracteres' },
    ];
    openModal(opts.title || (user ? 'Editar usuario' : 'Nuevo usuario'), formHTML(fields), {
      footer: modalFooter('Cancelar', user ? 'Guardar cambios' : 'Crear usuario'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var form = e.target;
      var data = getFormData(form);
      if (roleFixed) data.role = roleFixed;
      var btn = form.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (user) {
          if (!data.password) delete data.password;
          await api('/api/usuarios/' + user.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        } else {
          await api('/api/usuarios/', { method: 'POST', body: JSON.stringify(data) });
        }
        toast(user ? 'Usuario actualizado.' : 'Usuario creado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  /* ---------- TÉCNICOS ---------- */
  function openTecnicoForm(t) {
    var supervisorPromise = (isAdmin() || isSupervisor()) ? fetchAll('/api/supervisores/') : Promise.resolve([]);
    supervisorPromise.then(function (supervisores) {
      var fields = [
        { name: 'supervisor', label: 'Supervisor', type: 'select', value: t.supervisor || '',
          options: [{ value: '', label: 'Sin supervisor' }].concat(optList(supervisores, 'id', 'nombre')) },
        { name: 'especialidad', label: 'Especialidad', type: 'text', span: 2, value: t.especialidad },
        { name: 'telefono', label: 'Teléfono', type: 'tel', value: t.telefono },
        { name: 'direccion', label: 'Dirección', type: 'text', value: t.direccion },
        { name: 'disponible', label: 'Disponible para asignaciones', type: 'checkbox', value: !!t.disponible },
      ];
      if (isAdmin()) {
        fields.push({ name: 'password', label: 'Nueva contraseña', type: 'password', value: '',
          placeholder: 'Dejar vacía para no cambiar' });
      }
      openModal('Editar perfil del técnico', formHTML(fields), {
        footer: modalFooter('Cancelar', 'Guardar cambios'),
      });
      $('#modalForm').addEventListener('submit', async function (e) {
        e.preventDefault();
        var btn = e.target.querySelector('[type=submit]');
        setBusy(btn, true);
        try {
          var data = getFormData(e.target, ['supervisor']);
          var pw = data.password || '';
          delete data.password;
          await api('/api/tecnicos/' + t.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
          if (pw) {
            await api('/api/usuarios/' + t.user + '/', { method: 'PATCH', body: JSON.stringify({ password: pw }) });
          }
          toast('Perfil del técnico actualizado.', 'success');
          closeModal();
          reloadCurrent();
        } catch (err) { toast(apiErrorMessage(err), 'error'); }
        finally { setBusy(btn, false); }
      });
    });
  }

  function openSupervisorForm(s) {
    var fields = [
      { name: 'telefono', label: 'Teléfono', type: 'tel', value: s.telefono },
    ];
    if (isAdmin()) {
      fields.push({ name: 'password', label: 'Nueva contraseña', type: 'password', value: '',
        placeholder: 'Dejar vacía para no cambiar' });
    }
    openModal('Editar perfil del supervisor', formHTML(fields), {
      footer: modalFooter('Cancelar', 'Guardar cambios'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        var data = getFormData(e.target);
        var pw = data.password || '';
        delete data.password;
        await api('/api/supervisores/' + s.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        if (pw) {
          await api('/api/usuarios/' + s.user + '/', { method: 'PATCH', body: JSON.stringify({ password: pw }) });
        }
        toast('Perfil del supervisor actualizado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function openTecnicoDetail(t) {
    var fila = function (label, valor) {
      return '<div class="flex justify-between gap-6"><span class="text-on-surface-variant">' + esc(label) +
             '</span><span class="font-semibold text-right">' + (valor == null || valor === '' ? '—' : valor) + '</span></div>';
    };
    var html = '<div class="space-y-2 text-sm">' +
      fila('Técnico', esc(t.nombre)) +
      fila('Usuario', '@' + esc(t.username)) +
      fila('Correo', esc(t.email)) +
      fila('Rol', esc(t.rol || 'Técnico')) +
      fila('Especialidad', esc(t.especialidad)) +
      fila('Teléfono', esc(t.telefono)) +
      fila('Dirección', esc(t.direccion)) +
      fila('Supervisor', t.supervisor_nombre ? esc(t.supervisor_nombre) : 'Sin asignar') +
      fila('Disponible', t.disponible ? 'Disponible' : 'Ocupado') +
      '</div>';
    openModal('Técnico: ' + esc(t.nombre), html, {
      width: '560px',
      footer: '<button class="btn btn-primary" data-close>Cerrar</button>',
    });
  }

  function openSupervisorDetail(s) {
    var fila = function (label, valor) {
      return '<div class="flex justify-between gap-6"><span class="text-on-surface-variant">' + esc(label) +
             '</span><span class="font-semibold text-right">' + (valor == null || valor === '' ? '—' : valor) + '</span></div>';
    };
    var html = '<div class="space-y-2 text-sm">' +
      fila('Supervisor', esc(s.nombre)) +
      fila('Usuario', '@' + esc(s.username)) +
      fila('Correo', esc(s.email)) +
      fila('Rol', esc(s.rol || 'Supervisor')) +
      fila('Teléfono', esc(s.telefono)) +
      fila('Técnicos a cargo', String(s.tecnicos_count != null ? s.tecnicos_count : 0)) +
      fila('Registro', (s.created_at ? fmtDT(s.created_at) : '—')) +
      '</div>';
    openModal('Supervisor: ' + esc(s.nombre), html, {
      width: '560px',
      footer: '<button class="btn btn-primary" data-close>Cerrar</button>',
    });
  }

  function tecnicoToUser(t) {
    var parts = (t.nombre || '').split(/\s+/);
    var first = parts.shift() || t.username;
    return {
      id: t.user, username: t.username, email: t.email,
      first_name: first, last_name: parts.join(' '), role: 'tecnico', is_active: true,
    };
  }

  function supervisorToUser(s) {
    var name = s.nombre || '';
    var parts = name.split(' ');
    var first = parts.shift() || '';
    return {
      id: s.user, username: s.username, email: s.email,
      first_name: first, last_name: parts.join(' '), role: 'supervisor', is_active: true,
    };
  }

  function supervisoresAction(action, id) {
    if (action === 'crear') return openUserModal(null, { roleFixed: 'supervisor', title: 'Agregar supervisor' });
    if (action === 'editar') return getItem('/api/supervisores/' + id + '/').then(openSupervisorForm);
    if (action === 'editar_usuario') return getItem('/api/supervisores/' + id + '/').then(function (s) {
      openUserModal(supervisorToUser(s), { title: 'Editar usuario del supervisor' });
    });
    if (action === 'eliminar') {
      if (!confirm('¿Está seguro de que desea eliminar este supervisor? Esta acción no se puede deshacer.')) return;
      api('/api/supervisores/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Supervisor eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  function tecnicosAction(action, id) {
    if (action === 'crear') return openUserModal(null, { roleFixed: 'tecnico', title: 'Agregar técnico' });
    if (action === 'crear_trabajo') return openServicioForm(null);
    if (action === 'editar') return getItem('/api/tecnicos/' + id + '/').then(openTecnicoForm);
    if (action === 'editar_usuario') return getItem('/api/tecnicos/' + id + '/').then(function (t) {
      openUserModal(tecnicoToUser(t), { title: 'Editar usuario del técnico' });
    });
    if (action === 'eliminar') {
      if (!confirm('¿Está seguro de que desea eliminar este técnico? Esta acción no se puede deshacer.')) return;
      api('/api/tecnicos/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Técnico eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ---------- EQUIPOS ---------- */
  async function openEquiposForm(item) {
    var clientes, tipos;
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) { clientes = []; }
    try { tipos = await fetchAll('/api/tipos-equipo/'); } catch (e) { tipos = []; }
    var fields = [
      { name: 'cliente', label: 'Cliente propietario', type: 'select', required: true, value: item ? item.cliente : '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'tipo', label: 'Tipo de equipo', type: 'select', required: true, value: item ? item.tipo : '',
        options: optList(tipos, 'id', 'nombre') },
      { name: 'marca', label: 'Marca', type: 'text', required: true, value: item ? item.marca : '' },
      { name: 'modelo', label: 'Modelo', type: 'text', required: true, value: item ? item.modelo : '' },
      { name: 'numero_serie', label: 'No. de serie', type: 'text', required: true, value: item ? item.numero_serie : '' },
      { name: 'capacidad', label: 'Capacidad', type: 'text', value: item ? item.capacidad : '', placeholder: 'Ej: 12000 BTU' },
      { name: 'refrigerante', label: 'Refrigerante', type: 'text', value: item ? item.refrigerante : '', placeholder: 'Ej: R-410A' },
      { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'disponible',
        options: [{ value: 'disponible', label: 'Disponible' }, { value: 'instalado', label: 'Instalado' },
                  { value: 'averiado', label: 'Averiado' }, { value: 'en_reparacion', label: 'En reparación' },
                  { value: 'retirado', label: 'Retirado' }] },
      { name: 'fecha_instalacion', label: 'Fecha de instalación', type: 'date', value: item ? item.fecha_instalacion : '' },
      { name: 'ubicacion', label: 'Ubicación', type: 'text', value: item ? item.ubicacion : '' },
      { name: 'descripcion', label: 'Descripción', type: 'textarea', span: 2, value: item ? item.descripcion : '' },
    ];
    openModal(item ? 'Editar equipo' : 'Nuevo equipo', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear equipo'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['fecha_instalacion']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/equipos/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/equipos/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Equipo actualizado.' : 'Equipo creado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  async function openTiposModal() {
    var tipos = [];
    try { tipos = await fetchAll('/api/tipos-equipo/'); } catch (e) { tipos = []; }
    var body =
      formHTML([
        { name: 'nombre', label: 'Nombre del tipo', type: 'text', required: true, value: '' },
        { name: 'descripcion', label: 'Descripción', type: 'textarea', span: 2, value: '' },
      ]) +
      '<div class="mt-5"><h3 class="mb-2 text-sm font-bold tracking-tight text-on-surface">Tipos existentes</h3>' +
      '<div id="tiposList" class="space-y-2">' +
      (tipos.length ? tipos.map(function (t) {
        return '<div class="flex items-center gap-2 rounded-lg border border-outline-variant px-3 py-2">' +
               '<div class="min-w-0 flex-1"><div class="truncate text-sm font-semibold text-on-surface">' + esc(t.nombre) + '</div>' +
               '<div class="truncate text-xs text-on-surface-variant">' + esc(t.descripcion || 'Sin descripción') +
               ' · ' + t.total_equipos + ' equipos</div></div>' +
               '<button class="btn btn-ghost p-1.5" data-tipos="edit" data-id="' + t.id + '" title="Editar">' +
               '<span class="material-symbols-outlined text-base">edit</span></button>' +
               (canDelete() ? '<button class="btn btn-ghost p-1.5 hover:!bg-red-50 hover:!text-error" data-tipos="del" data-id="' + t.id + '" title="Eliminar">' +
               '<span class="material-symbols-outlined text-base">delete</span></button>' : '') +
               '</div>';
      }).join('') : '<p class="text-sm text-on-surface-variant">No hay tipos registrados.</p>') +
      '</div></div>';

    openModal('Tipos de equipo', body, { footer: modalFooter('Cerrar', 'Guardar tipo') });

    var form = $('#modalForm');
    var editingId = null;

    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(form);
      var btn = form.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (editingId) await api('/api/tipos-equipo/' + editingId + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/tipos-equipo/', { method: 'POST', body: JSON.stringify(data) });
        toast(editingId ? 'Tipo actualizado.' : 'Tipo creado.', 'success');
        closeModal();
        openTiposModal();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });

    $('#tiposList').addEventListener('click', function (ev) {
      var b = ev.target.closest('[data-tipos]');
      if (!b) return;
      var t = tipos.filter(function (x) { return x.id === Number(b.dataset.id); })[0];
      if (!t) return;
      if (b.dataset.tipos === 'edit') {
        editingId = t.id;
        form.querySelector('[name=nombre]').value = t.nombre;
        form.querySelector('[name=descripcion]').value = t.descripcion || '';
        form.querySelector('[name=nombre]').focus();
      } else if (b.dataset.tipos === 'del') {
        if (!confirm('¿Eliminar el tipo "' + t.nombre + '"?')) return;
        api('/api/tipos-equipo/' + t.id + '/', { method: 'DELETE' })
          .then(function () { toast('Tipo eliminado.', 'success'); closeModal(); openTiposModal(); })
          .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
      }
    });
  }

  function equiposAction(action, id) {
    if (action === 'crear') return openEquiposForm(null);
    if (action === 'tipos') return openTiposModal();
    if (action === 'historial') return openEquipoHistorial(id);
    if (action === 'editar') return getItem('/api/equipos/' + id + '/').then(openEquiposForm);
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar este equipo?')) return;
      api('/api/equipos/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Equipo eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  async function openEquipoHistorial(id) {
    var h;
    try { h = await api('/api/equipos/' + id + '/historial/'); }
    catch (err) { toast(apiErrorMessage(err), 'error'); return; }
    var eq = h.equipo || {};
    var garantiaBadge = h.garantia_activa ? '<span class="badge badge-success">Garantía vigente</span>'
                       : (h.garantia_hasta ? '<span class="badge badge-neutral">Garantía vencida</span>' : '');
    var body = '' +
      '<div class="mb-4 flex flex-wrap items-center gap-2">' +
        '<span class="badge badge-primary">' + esc(eq.marca) + ' ' + esc(eq.modelo) + '</span>' +
        estadoBadge(eq.estado, eq.estado_display) + garantiaBadge +
      '</div>' +
      '<div class="det-grid">' +
        '<div><div class="det-label">No. de serie</div><div class="det-value">' + esc(eq.numero_serie) + '</div></div>' +
        '<div><div class="det-label">Cliente</div><div class="det-value">' + esc(h.cliente || '—') + '</div></div>' +
        '<div><div class="det-label">Tipo</div><div class="det-value">' + esc(eq.tipo_nombre || '—') + '</div></div>' +
        '<div><div class="det-label">Garantía</div><div class="det-value">' +
          (h.garantia_meses ? h.garantia_meses + ' meses' : '—') +
          (h.garantia_hasta ? ' · hasta ' + fmtDate(h.garantia_hasta) : '') + '</div></div>' +
      '</div>' +
      (h.observaciones ? '<p class="mt-3 text-sm text-on-surface-variant">' + esc(h.observaciones) + '</p>' : '') +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Instalaciones (' + h.instalaciones.length + ')</h4>' +
        buildTable([
          { label: '#', render: function (x) { return '<span class="font-semibold">' + x.id + '</span>'; } },
          { label: 'Fecha', render: function (x) { return fmtDT(x.fecha_instalacion || x.fecha_programada); } },
          { label: 'Técnico', key: 'tecnico' },
          { label: 'Estado', render: function (x) { return estadoBadge(x.estado, x.estado_display); } },
          { label: 'Evid.', render: function (x) { return x.evidencias.length; } },
          { label: 'Firmas', render: function (x) { return x.firmas.length; } },
          { label: 'Materiales', render: function (x) { return x.materiales.length; } },
        ], h.instalaciones) + '</div>' +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Reparaciones / servicios (' + h.reparaciones.length + ')</h4>' +
        buildTable([
          { label: 'Orden', render: function (x) { return '<span class="font-semibold">' + esc(x.numero) + '</span>'; } },
          { label: 'Tipo', render: function (x) { return esc(x.tipo_servicio_display); } },
          { label: 'Fecha', render: function (x) { return fmtDate(x.fecha); } },
          { label: 'Estado', render: function (x) { return estadoBadge(x.estado, x.estado_display); } },
          { label: 'Técnico', key: 'tecnico' },
          { label: 'Materiales', render: function (x) { return x.materiales.length; } },
        ], h.reparaciones) + '</div>' +
      '<div class="mt-5"><h4 class="mb-2 text-sm font-bold text-on-surface">Mantenimientos (' + h.mantenimientos.length + ')</h4>' +
        buildTable([
          { label: 'Tipo', render: function (x) { return esc(x.tipo_display); } },
          { label: 'Fecha', render: function (x) { return fmtDate(x.fecha); } },
          { label: 'Próximo', render: function (x) { return fmtDate(x.proxima_fecha); } },
          { label: 'Estado', render: function (x) { return estadoBadge(x.estado, x.estado_display); } },
          { label: 'Técnico', key: 'tecnico' },
          { label: 'Costo', render: function (x) { return money(x.costo); } },
        ], h.mantenimientos) + '</div>';
    openModal('Historial del equipo', body, {
      footer: '<button type="button" class="btn btn-primary" data-close>Cerrar</button>',
      width: '860px',
    });
  }

  /* ---------- SOLICITUDES ---------- */
  async function openSolicitudForm(item) {
    var clientes = [];
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) { clientes = []; }
    var fields = [
      { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: item ? item.cliente : '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'tipo_equipo_solicitado', label: 'Tipo de equipo solicitado', type: 'text', required: true,
        value: item ? item.tipo_equipo_solicitado : '' },
      { name: 'prioridad', label: 'Prioridad', type: 'select', value: item ? item.prioridad : 'media',
        options: [{ value: 'baja', label: 'Baja' }, { value: 'media', label: 'Media' },
                  { value: 'alta', label: 'Alta' }, { value: 'urgente', label: 'Urgente' }] },
      { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pendiente',
        options: [{ value: 'pendiente', label: 'Pendiente' }, { value: 'aprobada', label: 'Aprobada' },
                  { value: 'reprogramada', label: 'Reprogramada' }, { value: 'rechazada', label: 'Rechazada' },
                  { value: 'completada', label: 'Completada' }] },
      { name: 'fecha_deseada', label: 'Fecha deseada', type: 'date', value: item ? item.fecha_deseada : '' },
      { name: 'descripcion', label: 'Descripción del requerimiento', type: 'textarea', span: 2,
        value: item ? item.descripcion : '' },
      { name: 'observaciones', label: 'Observaciones', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
    ];
    openModal(item ? 'Editar solicitud' : 'Nueva solicitud', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear solicitud'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['fecha_deseada']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/solicitudes/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/solicitudes/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Solicitud actualizada.' : 'Solicitud creada.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function openEstadoModal(resource, item, estados) {
    var fields = [
      { name: 'estado', label: 'Nuevo estado', type: 'select', required: true, value: item.estado, options: estados },
    ];
    var body = formHTML(fields);
    if (resource === 'instalaciones') {
      body += '<p class="text-xs text-on-surface-variant">Nota: para finalizar una instalación se requiere al menos una ' +
              'evidencia fotográfica (RN-05).</p>';
    }
    openModal('Cambiar estado #' + item.id, body, {
      footer: modalFooter('Cancelar', 'Cambiar estado'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (resource === 'instalaciones') {
          await api('/api/instalaciones/' + item.id + '/cambiar_estado/', { method: 'PATCH', body: JSON.stringify(data) });
        } else if (resource === 'servicios') {
          await api('/api/servicios/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        } else if (resource === 'mantenimientos') {
          await api('/api/mantenimientos/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        } else if (resource === 'visitas') {
          await api('/api/visitas/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        } else if (resource === 'cotizaciones') {
          await api('/api/cotizaciones/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        } else {
          await api('/api/solicitudes/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        }
        toast('Estado actualizado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function solicitudesAction(action, id) {
    if (action === 'crear') return openSolicitudForm(null);
    if (action === 'editar') return getItem('/api/solicitudes/' + id + '/').then(openSolicitudForm);
    if (action === 'estado') return getItem('/api/solicitudes/' + id + '/').then(function (s) {
      openEstadoModal('solicitudes', s, [
        { value: 'pendiente', label: 'Pendiente' }, { value: 'aprobada', label: 'Aprobada' },
        { value: 'reprogramada', label: 'Reprogramada' }, { value: 'rechazada', label: 'Rechazada' },
        { value: 'completada', label: 'Completada' }]);
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar esta solicitud?')) return;
      api('/api/solicitudes/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Solicitud eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ---------- INSTALACIONES ---------- */
  async function openInstalacionForm(item) {
    var clientes, equipos, tecnicos, solicitudes;
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) { clientes = []; }
    try { equipos = await fetchAll('/api/equipos/'); } catch (e) { equipos = []; }
    try { tecnicos = await fetchAll('/api/tecnicos/'); } catch (e) { tecnicos = []; }
    try { solicitudes = await fetchAll('/api/solicitudes/'); } catch (e) { solicitudes = []; }

    var fields = [
      { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: item ? item.cliente : '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'equipo', label: 'Equipo', type: 'select', value: item ? item.equipo : '',
        options: optList(equipos, 'id', function (e) { return e.marca + ' ' + e.modelo + ' · ' + e.numero_serie; }) },
      { name: 'tecnico', label: 'Técnico responsable', type: 'select', value: item ? item.tecnico : '',
        options: optList(tecnicos, 'id', 'nombre') },
      { name: 'solicitud', label: 'Solicitud relacionada', type: 'select', value: item ? item.solicitud : '',
        options: optList(solicitudes, 'id', function (s) { return '#' + s.id + ' · ' + s.tipo_equipo_solicitado; }) },
      { name: 'fecha_programada', label: 'Fecha programada', type: 'datetime-local', value: item ? dtLocal(item.fecha_programada) : '',
        hint: 'Selecciona la fecha y hora desde el calendario.' },
      { name: 'fecha_instalacion', label: 'Fecha de instalación', type: 'datetime-local', value: item ? dtLocal(item.fecha_instalacion) : '',
        hint: 'Selecciona la fecha y hora desde el calendario.' },
      { name: 'prioridad', label: 'Prioridad', type: 'select', value: item ? item.prioridad : 'media',
        options: [{ value: 'baja', label: 'Baja' }, { value: 'media', label: 'Media' },
                  { value: 'alta', label: 'Alta' }, { value: 'urgente', label: 'Urgente' }] },
      { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pendiente',
        options: [{ value: 'pendiente', label: 'Pendiente' }, { value: 'asignada', label: 'Asignada' },
                  { value: 'en_proceso', label: 'En proceso' }, { value: 'finalizada', label: 'Finalizada' },
                  { value: 'cancelada', label: 'Cancelada' }, { value: 'reprogramada', label: 'Reprogramada' }] },
      { name: 'direccion', label: 'Dirección', type: 'text', required: true, span: 2, value: item ? item.direccion : '' },
      { name: 'ciudad', label: 'Ciudad', type: 'text', value: item ? item.ciudad : '' },
      { name: 'latitud', label: 'Latitud', type: 'number', step: '0.0000001', value: item && item.latitud != null ? item.latitud : '',
        hint: 'Se llena automáticamente al geocodificar la dirección.' },
      { name: 'longitud', label: 'Longitud', type: 'number', step: '0.0000001', value: item && item.longitud != null ? item.longitud : '',
        hint: 'Se llena automáticamente al geocodificar la dirección.' },
      { name: 'observaciones', label: 'Observaciones', type: 'textarea', span: 2, value: item ? item.observaciones : '' },
    ];
    openModal(item ? 'Editar instalación' : 'Nueva instalación',
      formHTML(fields) +
      '<div class="col-span-full mt-1 flex flex-wrap items-center gap-2">' +
        '<button id="btnGeocode" type="button" class="btn btn-ghost"><span class="material-symbols-outlined text-sm">location_searching</span>Geocodificar dirección</button>' +
        '<button id="btnSlotsForm" type="button" class="btn btn-ghost"><span class="material-symbols-outlined text-sm">schedule</span>Sugerir horarios libres</button>' +
      '</div>' +
      '<div id="slotFormList" class="col-span-full mt-2 flex flex-wrap gap-2"></div>' +
      '<p class="col-span-full mt-2 text-xs text-on-surface-variant">' +
      'Sugerencias de la agenda inteligente (RN-03): bloques de 30 min entre 08:00 y 18:00, sin conflictos con otras instalaciones del técnico.</p>',
      {
        footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear instalación'),
        width: '720px',
      });

    $('#btnGeocode').addEventListener('click', function () {
      var dir = $('#modalForm [name=direccion]').value.trim();
      var ciudad = $('#modalForm [name=ciudad]').value.trim();
      if (!dir) { toast('Escribe la dirección primero.', 'error'); return; }
      var q = encodeURIComponent(dir + (ciudad ? ', ' + ciudad : '') + ', República Dominicana');
      $('#btnGeocode').dataset.label = $('#btnGeocode').textContent;
      $('#btnGeocode').textContent = 'Buscando…';
      fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=do&accept-language=es-DO&q=' + q)
        .then(function (r) { return r.json(); })
        .then(function (res) {
          if (!res || !res.length) { toast('No se encontró la dirección. Llena las coordenadas manualmente.', 'error'); return; }
          $('#modalForm [name=latitud]').value = res[0].lat;
          $('#modalForm [name=longitud]').value = res[0].lon;
          toast('Coordenadas obtenidas: ' + Number(res[0].lat).toFixed(5) + ', ' + Number(res[0].lon).toFixed(5), 'success');
        })
        .catch(function () { toast('No se pudo geocodificar. Verifica tu conexión.', 'error'); })
        .finally(function () { $('#btnGeocode').textContent = $('#btnGeocode').dataset.label; });
    });

    $('#btnSlotsForm').addEventListener('click', function () {
      var tecnico = $('#modalForm [name=tecnico]').value;
      var fecha = $('#modalForm [name=fecha_programada]').value;
      if (!tecnico) { toast('Selecciona el técnico responsable.', 'error'); return; }
      if (!fecha) { toast('Selecciona la fecha programada.', 'error'); return; }
      var qs = '?fecha=' + fecha.slice(0, 10) + '&duracion_minutos=120&tecnico=' + tecnico;
      if (item) qs += '&instalacion=' + item.id;
      $('#slotFormList').innerHTML = '<span class="text-sm text-on-surface-variant">Consultando horarios…</span>';
      api('/api/instalaciones/disponibilidad/' + qs)
        .then(function (r) {
          var slots = r.slots || [];
          if (!slots.length) { $('#slotFormList').innerHTML = '<span class="text-sm text-error">Sin horarios libres ese día.</span>'; return; }
          $('#slotFormList').innerHTML = slots.map(function (s) {
            return '<button type="button" class="slot-chip" data-slot="' + s.inicio + '">' + fmtDT(s.inicio) + '</button>';
          }).join('');
          $('#slotFormList').querySelectorAll('.slot-chip').forEach(function (c) {
            c.addEventListener('click', function () {
              $('#slotFormList').querySelectorAll('.slot-chip').forEach(function (x) { x.classList.remove('active'); });
              c.classList.add('active');
              $('#modalForm [name=fecha_programada]').value = dtLocal(c.dataset.slot);
            });
          });
        })
        .catch(function (err) { $('#slotFormList').innerHTML = '<span class="text-sm text-error">' + esc(apiErrorMessage(err)) + '</span>'; });
    });

    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['equipo', 'tecnico', 'solicitud', 'fecha_programada', 'fecha_instalacion', 'latitud', 'longitud']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/instalaciones/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/instalaciones/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Instalación actualizada.' : 'Instalación creada.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function instalacionesAction(action, id) {
    if (action === 'crear') return openInstalacionForm(null);
    if (action === 'agenda') { go('agenda'); return; }
    if (action === 'ver') return openInstalacionDetalle(id);
    if (action === 'reprogramar') return getItem('/api/instalaciones/' + id + '/').then(reprogramarInstalacion);
    if (action === 'editar') return getItem('/api/instalaciones/' + id + '/').then(openInstalacionForm);
    if (action === 'estado') return getItem('/api/instalaciones/' + id + '/').then(function (i) {
      openEstadoModal('instalaciones', i, ESTADOS_INSTALACION);
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar esta instalación?')) return;
      api('/api/instalaciones/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Instalación eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ---------- PAGOS / FACTURAS ---------- */
  async function openPagoForm(item) {
    var clientes = [], ordenes = [], instalaciones = [];
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) {}
    try { ordenes = await fetchAll('/api/servicios/'); } catch (e) {}
    try { instalaciones = await fetchAll('/api/instalaciones/'); } catch (e) {}
    var fields = [
      { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: item ? item.cliente : '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'orden', label: 'Orden de servicio', type: 'select', value: item ? item.orden : '',
        options: optList(ordenes, 'id', function (o) { return '#' + o.numero + ' · ' + (o.cliente_nombre || ''); }) },
      { name: 'instalacion', label: 'Instalación', type: 'select', value: item ? item.instalacion : '',
        options: optList(instalaciones, 'id', function (i) { return '#' + i.id + ' · ' + (i.cliente_nombre || ''); }) },
      { name: 'monto', label: 'Monto', type: 'number', required: true, min: 0.01, step: 0.01,
        value: item ? item.monto : '' },
      { name: 'es_abono', label: 'Es un abono parcial', type: 'checkbox', value: item ? !!item.es_abono : false },
      { name: 'metodo', label: 'Método de pago', type: 'select', value: item ? item.metodo : 'efectivo',
        options: [{ value: 'efectivo', label: 'Efectivo' }, { value: 'tarjeta', label: 'Tarjeta' },
                  { value: 'transferencia', label: 'Transferencia' }, { value: 'cheque', label: 'Cheque' }] },
      { name: 'fecha', label: 'Fecha', type: 'date', required: true, value: item ? item.fecha : new Date().toISOString().slice(0, 10) },
      { name: 'referencia', label: 'Referencia', type: 'text', value: item ? item.referencia : '' },
      { name: 'estado', label: 'Estado', type: 'select', value: item ? item.estado : 'pagado',
        options: [{ value: 'pendiente', label: 'Pendiente' }, { value: 'pagado', label: 'Pagado' },
                  { value: 'fallido', label: 'Fallido' }] },
    ];
    openModal(item ? 'Editar pago' : 'Nuevo pago', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Registrar pago'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['orden', 'instalacion']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/pagos/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/pagos/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Pago actualizado.' : 'Pago registrado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  async function openFacturaForm() {
    var clientes = [], ordenes = [];
    try { clientes = await fetchAll('/api/clientes/disponibles/'); } catch (e) {}
    try { ordenes = await fetchAll('/api/servicios/'); } catch (e) {}
    var fields = [
      { name: 'cliente', label: 'Cliente', type: 'select', required: true, value: '',
        options: optList(clientes, 'id', 'nombre_completo') },
      { name: 'orden', label: 'Orden de servicio', type: 'select', value: '',
        options: optList(ordenes, 'id', function (o) { return '#' + o.numero + ' · ' + (o.cliente_nombre || ''); }) },
      { name: 'iva', label: 'IVA', type: 'number', min: 0, step: 0.01, value: '0' },
      { name: 'notas', label: 'Notas', type: 'textarea', span: 2, value: '' },
    ];
    openModal('Nueva factura', formHTML(fields), {
      footer: modalFooter('Cancelar', 'Crear factura'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target, ['orden']);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        await api('/api/facturas/', { method: 'POST', body: JSON.stringify(data) });
        toast('Factura creada.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function openFacturaDetail(f) {
    var html = '<div class="space-y-2 text-sm">' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Número</span><span class="font-semibold">' + esc(f.numero) + '</span></div>' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Cliente</span><span class="font-semibold">' + esc(f.cliente_nombre) + '</span></div>' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Orden</span><span>' + esc(f.orden_numero || '—') + '</span></div>' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Fecha</span><span>' + fmtDate(f.fecha) + '</span></div>' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">Subtotal</span><span>' + money(f.subtotal) + '</span></div>' +
      '<div class="flex justify-between"><span class="text-on-surface-variant">IVA</span><span>' + money(f.iva) + '</span></div>' +
      '<div class="flex justify-between border-t border-outline-variant pt-2"><span class="font-semibold">Total</span><span class="font-bold text-primary">' + money(f.total) + '</span></div>' +
      (f.notas ? '<div class="border-t border-outline-variant pt-2"><span class="text-on-surface-variant">Notas</span><p class="mt-1">' + esc(f.notas) + '</p></div>' : '') +
      '</div>';
    if (f.pagos_detalle && f.pagos_detalle.length) {
      html += '<div class="mt-4"><h4 class="mb-2 text-sm font-bold text-on-surface">Pagos asociados</h4>' +
              buildTable([
                { label: 'Fecha', render: function (p) { return fmtDate(p.fecha); } },
                { label: 'Monto', render: function (p) { return money(p.monto); } },
                { label: 'Estado', render: function (p) { return estadoBadge(p.estado, p.estado_display); } },
              ], f.pagos_detalle) + '</div>';
    }
    openModal('Detalle de factura ' + f.numero, html, {
      footer: '<button class="btn btn-primary" data-close>Cerrar</button>',
    });
  }

  function pagosAction(action, id) {
    if (action === 'crear') return openPagoForm(null);
    if (action === 'nueva_factura') return openFacturaForm();
    if (action === 'ver_factura') return getItem('/api/facturas/' + id + '/').then(openFacturaDetail);
    if (action === 'eliminar_factura') {
      if (!confirm('¿Eliminar esta factura?')) return;
      api('/api/facturas/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Factura eliminada.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
    if (action === 'editar') return getItem('/api/pagos/' + id + '/').then(openPagoForm);
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar este pago?')) return;
      api('/api/pagos/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Pago eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ---------- INVENTARIO ---------- */
  async function openMaterialForm(item) {
    var fields = [
      { name: 'nombre', label: 'Nombre', type: 'text', required: true, value: item ? item.nombre : '' },
      { name: 'codigo', label: 'Código', type: 'text', required: true, value: item ? item.codigo : '' },
      { name: 'categoria', label: 'Categoría', type: 'text', value: item ? item.categoria : '' },
      { name: 'unidad_medida', label: 'Unidad de medida', type: 'select', value: item ? item.unidad_medida : 'unidad',
        options: [{ value: 'unidad', label: 'Unidad' }, { value: 'metro', label: 'Metro' },
                  { value: 'litro', label: 'Litro' }, { value: 'galon', label: 'Galón' },
                  { value: 'kilogramo', label: 'Kilogramo' }, { value: 'libra', label: 'Libra' },
                  { value: 'paquete', label: 'Paquete' }] },
      { name: 'cantidad_disponible', label: 'Cantidad disponible', type: 'number', required: true, min: 0, step: 0.01,
        value: item ? item.cantidad_disponible : '0' },
      { name: 'stock_minimo', label: 'Stock mínimo', type: 'number', min: 0, step: 0.01,
        value: item ? item.stock_minimo : '0' },
      { name: 'precio', label: 'Precio', type: 'number', min: 0, step: 0.01, value: item ? item.precio : '0' },
      { name: 'descripcion', label: 'Descripción', type: 'textarea', span: 2, value: item ? item.descripcion : '' },
    ];
    openModal(item ? 'Editar material' : 'Nuevo material', formHTML(fields), {
      footer: modalFooter('Cancelar', item ? 'Guardar cambios' : 'Crear material'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        if (item) await api('/api/materiales/' + item.id + '/', { method: 'PATCH', body: JSON.stringify(data) });
        else await api('/api/materiales/', { method: 'POST', body: JSON.stringify(data) });
        toast(item ? 'Material actualizado.' : 'Material creado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function openEntradaModal(m) {
    var fields = [
      { name: 'tipo', label: 'Tipo de movimiento', type: 'select', value: 'entrada',
        hint: 'Entrada: suma stock. Ajuste: fija la cantidad exacta.',
        options: [{ value: 'entrada', label: 'Entrada' }, { value: 'ajuste', label: 'Ajuste' }] },
      { name: 'cantidad', label: 'Cantidad', type: 'number', required: true, min: 0.01, step: 0.01, value: '' },
      { name: 'motivo', label: 'Motivo', type: 'text', span: 2, value: '' },
    ];
    openModal('Entrada / ajuste — ' + m.nombre, formHTML(fields), {
      footer: modalFooter('Cancelar', 'Registrar'),
    });
    $('#modalForm').addEventListener('submit', async function (e) {
      e.preventDefault();
      var data = getFormData(e.target);
      var btn = e.target.querySelector('[type=submit]');
      setBusy(btn, true);
      try {
        await api('/api/materiales/' + m.id + '/entrada/', { method: 'POST', body: JSON.stringify(data) });
        toast('Movimiento registrado.', 'success');
        closeModal();
        reloadCurrent();
      } catch (err) { toast(apiErrorMessage(err), 'error'); }
      finally { setBusy(btn, false); }
    });
  }

  function inventarioAction(action, id) {
    if (action === 'crear') return openMaterialForm(null);
    if (action === 'editar') return getItem('/api/materiales/' + id + '/').then(openMaterialForm);
    if (action === 'entrada') return getItem('/api/materiales/' + id + '/').then(openEntradaModal);
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar este material?')) return;
      api('/api/materiales/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Material eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ---------- USUARIOS ---------- */
  function usuariosAction(action, id) {
    if (action === 'crear') return openUserModal(null, {});
    if (action === 'editar') return getItem('/api/usuarios/' + id + '/').then(function (u) {
      openUserModal(u, {});
    });
    if (action === 'eliminar') {
      if (!confirm('¿Eliminar este usuario?')) return;
      api('/api/usuarios/' + id + '/', { method: 'DELETE' })
        .then(function () { toast('Usuario eliminado.', 'success'); reloadCurrent(); })
        .catch(function (err) { toast(apiErrorMessage(err), 'error'); });
    }
  }

  /* ------------------------------------------------------------------
   * Despacho de acciones
   * ------------------------------------------------------------------ */
  function onAction(action, id) {
    switch (S.section) {
      case 'clientes': return clientesAction(action, id);
      case 'supervisores': return supervisoresAction(action, id);
      case 'tecnicos': return tecnicosAction(action, id);
      case 'equipos': return equiposAction(action, id);
      case 'mis_equipos': return misEquiposAction(action, id);
      case 'solicitudes': return solicitudesAction(action, id);
      case 'instalaciones': return instalacionesAction(action, id);
      case 'servicios': return serviciosAction(action, id);
      case 'mantenimientos': return mantenimientosAction(action, id);
      case 'evaluaciones': return evaluacionesAction(action, id);
      case 'visitas': return visitasAction(action, id);
      case 'cotizaciones': return cotizacionesAction(action, id);
      case 'agenda': return agendaAction(action, id);
      case 'pagos': return pagosAction(action, id);
      case 'inventario': return inventarioAction(action, id);
      case 'almacen': return almacenAction(action, id);
      case 'usuarios': return usuariosAction(action, id);
      case 'tienda': return tiendaAction(action, id);
      case 'perfil': return perfilAction(action, id);
      default: break;
    }
  }

  var renderers = {
    dashboard: renderDashboard,
    clientes: renderClientes,
    supervisores: renderSupervisores,
    tecnicos: renderTecnicos,
    equipos: renderEquipos,
    mis_equipos: renderMisEquipos,
    solicitudes: renderSolicitudes,
    instalaciones: renderInstalaciones,
    servicios: renderServicios,
    mantenimientos: renderMantenimientos,
    evaluaciones: renderEvaluaciones,
    visitas: renderVisitas,
    cotizaciones: renderCotizaciones,
    agenda: renderAgenda,
    pagos: renderPagos,
    inventario: renderInventario,
    almacen: renderAlmacen,
    reportes: renderReportes,
    usuarios: renderUsuarios,
    tienda: renderTienda,
    perfil: renderPerfil,
  };

  /* ------------------------------------------------------------------
   * Navegación y secciones
   * ------------------------------------------------------------------ */
  var SECTIONS = {
    dashboard: { title: 'Dashboard', icon: 'dashboard', subtitle: 'Resumen general del sistema', roles: ['administrador', 'supervisor', 'almacen'] },
    clientes: { title: 'Clientes', icon: 'group', subtitle: 'Registro de clientes', roles: ['administrador', 'supervisor'] },
    supervisores: { title: 'Supervisores', icon: 'supervisor_account', subtitle: 'Gestión de supervisores', roles: ['administrador'] },
    tecnicos: { title: 'Técnicos', icon: 'engineering', subtitle: 'Personal técnico de campo', roles: ['administrador', 'supervisor'] },
    equipos: { title: 'Productos / Equipos', icon: 'ac_unit', subtitle: 'Equipos de refrigeración y tipos', roles: ['administrador', 'supervisor'] },
    mis_equipos: { title: 'Mis equipos', icon: 'ac_unit', subtitle: 'Equipos registrados por ti', roles: ['cliente'] },
    solicitudes: { title: 'Solicitudes', icon: 'assignment', subtitle: 'Solicitudes de instalación', roles: ['administrador', 'supervisor'] },
    instalaciones: { title: 'Instalaciones', icon: 'home_repair_service', subtitle: 'Agenda de instalaciones', roles: ['administrador', 'supervisor', 'tecnico'] },
    servicios: { title: 'Servicios', icon: 'handyman', subtitle: 'Órdenes de trabajo y servicio', roles: ['administrador', 'supervisor', 'tecnico', 'cliente'] },
    mantenimientos: { title: 'Mantenimientos', icon: 'build', subtitle: 'Preventivos y correctivos de equipos', roles: ['administrador', 'supervisor', 'tecnico', 'cliente'] },
    evaluaciones: { title: 'Calificaciones', icon: 'star', subtitle: 'Evaluaciones de satisfacción del cliente', roles: ['administrador', 'supervisor', 'cliente'] },
    visitas: { title: 'Visitas técnicas', icon: 'home_pin', subtitle: 'Visitas técnicas programadas', roles: ['administrador', 'supervisor', 'tecnico'] },
    cotizaciones: { title: 'Cotizaciones', icon: 'request_quote', subtitle: 'Cotizaciones de instalación', roles: ['administrador', 'supervisor'] },
    agenda: { title: 'Agenda', icon: 'calendar_month', subtitle: 'Calendario y mapa de instalaciones', roles: ['administrador', 'supervisor', 'tecnico'] },
    pagos: { title: 'Pagos', icon: 'payments', subtitle: 'Pagos, abonos y facturas', roles: ['administrador', 'supervisor', 'almacen'] },
    inventario: { title: 'Inventario', icon: 'inventory_2', subtitle: 'Materiales y movimientos', roles: ['administrador', 'supervisor', 'almacen'] },
    almacen: { title: 'Almacén', icon: 'storefront', subtitle: 'Productos y categorías de la vitrina', roles: ['administrador', 'supervisor', 'almacen'] },
    tienda: { title: 'Tienda', icon: 'shopping_bag', subtitle: 'Órdenes de compra y pagos del checkout', roles: ['administrador', 'supervisor', 'almacen'] },
    reportes: { title: 'Reportes', icon: 'bar_chart', subtitle: 'Indicadores y desempeño', roles: ['administrador'] },
    usuarios: { title: 'Usuarios y Roles', icon: 'manage_accounts', subtitle: 'Cuentas y permisos del sistema', roles: ['administrador'] },
    perfil: { title: 'Mi perfil', icon: 'person', subtitle: 'Foto de perfil y datos personales', roles: ['administrador', 'supervisor', 'tecnico', 'almacen', 'cliente'] },
  };

  var SIDEBAR_GROUPS = [
    { label: 'Principal', icon: 'home', keys: ['dashboard', 'clientes', 'supervisores', 'tecnicos', 'mis_equipos'], collapsed: false },
    { label: 'Operaciones', icon: 'engineering', keys: ['equipos', 'solicitudes', 'instalaciones', 'servicios', 'agenda'], collapsed: false },
    { label: 'Mantenimiento', icon: 'build', keys: ['mantenimientos', 'visitas', 'evaluaciones'], collapsed: false },
    { label: 'Ventas', icon: 'point_of_sale', keys: ['cotizaciones', 'pagos', 'tienda'], collapsed: false },
    { label: 'Almacén', icon: 'warehouse', keys: ['inventario', 'almacen'], collapsed: false },
    { label: 'Sistema', icon: 'settings', keys: ['reportes', 'usuarios', 'perfil'], collapsed: false },
  ];

  function buildNav() {
    var role = S.user.role;
    var html = '';
    SIDEBAR_GROUPS.forEach(function (group, idx) {
      var items = [];
      group.keys.forEach(function (key) {
        var s = SECTIONS[key];
        if (!s || s.roles.indexOf(role) < 0) return;
        items.push(
          '<button class="nav-item" data-nav="' + key + '" data-tooltip="' + esc(s.title) + '">' +
          '<span class="material-symbols-outlined">' + s.icon + '</span>' +
          '<span>' + esc(s.title) + '</span></button>'
        );
      });
      if (items.length === 0) return;
      var expanded = group.collapsed !== true;
      html += '<div class="nav-group" data-group="' + idx + '">' +
        '<button class="nav-group-label" aria-expanded="' + expanded + '">' +
        '<span class="material-symbols-outlined">' + group.icon + '</span>' +
        '<span>' + group.label + '</span>' +
        '<span class="material-symbols-outlined nav-group-arrow">expand_more</span></button>' +
        '<div class="nav-group-items' + (expanded ? '' : ' collapsed') + '">' + items.join('') + '</div></div>';
    });
    $('#navList').innerHTML = html;
  }

  function initGroupToggles() {
    try {
      var saved = JSON.parse(localStorage.getItem('sidebar_groups') || '{}');
      SIDEBAR_GROUPS.forEach(function (g, i) {
        if (saved[i] !== undefined) g.collapsed = !!saved[i];
      });
    } catch (e) {}
    function toggleGroup(label) {
      var group = label.closest('.nav-group');
      if (!group) return;
      var idx = parseInt(group.dataset.group, 10);
      var items = group.querySelector('.nav-group-items');
      if (!items) return;
      var willCollapse = label.getAttribute('aria-expanded') !== 'false';
      label.setAttribute('aria-expanded', String(!willCollapse));
      SIDEBAR_GROUPS[idx].collapsed = willCollapse;
      if (willCollapse) {
        items.style.height = items.scrollHeight + 'px';
        items.offsetHeight;
        items.classList.add('collapsed');
        items.style.height = '0';
      } else {
        items.classList.remove('collapsed');
        items.style.height = items.scrollHeight + 'px';
        items.addEventListener('transitionend', function handler() {
          items.style.height = '';
          items.removeEventListener('transitionend', handler);
        });
      }
      try {
        var state = {};
        SIDEBAR_GROUPS.forEach(function (g, i) { state[i] = g.collapsed; });
        localStorage.setItem('sidebar_groups', JSON.stringify(state));
      } catch (e) {}
    }
    $('#navList').addEventListener('click', function (e) {
      var label = e.target.closest('.nav-group-label');
      if (label) toggleGroup(label);
    });
  }

  function closeSidebar() {
    $('#sidebar').classList.remove('translate-x-0');
    $('#sidebar').classList.add('-translate-x-full');
    $('#sidebarOverlay').classList.add('hidden');
  }

  function openSidebar() {
    $('#sidebar').classList.remove('-translate-x-full');
    $('#sidebar').classList.add('translate-x-0');
    $('#sidebarOverlay').classList.remove('hidden');
  }

  function toggleSidebar() {
    var sidebar = $('#sidebar');
    var main = $('#mainContent');
    var toggleIcon = sidebar.querySelector('#sidebarToggle .material-symbols-outlined');
    if (sidebar.classList.contains('sidebar-closed')) {
      sidebar.classList.remove('sidebar-closed');
      main.classList.remove('lg:pl-[72px]');
      main.classList.add('lg:pl-64');
      if (toggleIcon) toggleIcon.textContent = 'menu';
      try { localStorage.setItem('sidebar_closed', '0'); } catch (e) {}
    } else {
      sidebar.classList.add('sidebar-closed');
      main.classList.remove('lg:pl-64');
      main.classList.add('lg:pl-[72px]');
      if (toggleIcon) toggleIcon.textContent = 'menu_open';
      try { localStorage.setItem('sidebar_closed', '1'); } catch (e) {}
    }
  }

  function firstAllowedSection() {
    var role = S.user.role;
    return Object.keys(SECTIONS).find(function (k) {
      return SECTIONS[k].roles.indexOf(role) >= 0;
    }) || '';
  }

  function go(section) {
    var target = SECTIONS[section] && SECTIONS[section].roles.indexOf(S.user.role) >= 0
      ? section : firstAllowedSection();
    if (!target) {
      $('#app').classList.add('hidden');
      $('#bootScreen').classList.add('hidden');
      var denied = $('#deniedScreen');
      denied.classList.remove('hidden');
      denied.classList.add('flex');
      return;
    }
    S.section = target;
    $('#pageTitle').textContent = SECTIONS[target].title;
    $('#pageSubtitle').textContent = SECTIONS[target].subtitle;
    $$('#navList .nav-item').forEach(function (n) {
      n.classList.toggle('active', n.dataset.nav === target);
    });
    try { history.replaceState(null, '', '#/' + target); } catch (e) { /* hash opcional */ }
    closeSidebar();
    var fn = renderers[target];
    if (fn) fn();
  }

  function renderUser() {
    var u = S.user;
    var av = $('#userAvatar');
    if (u && u.photo) {
      av.innerHTML = '<img src="' + esc(u.photo) + '" alt="' + esc(u.full_name || u.username) +
                     '" class="h-full w-full rounded-full object-cover">';
    } else {
      av.textContent = initials(u.full_name || u.username);
    }
    $('#userName').textContent = u.full_name || u.username;
    $('#userRole').textContent = u.role_display || u.role || '';
  }

  /* ------------------------------------------------------------------
   * Eventos globales
   * ------------------------------------------------------------------ */
  $('#navList').addEventListener('click', function (e) {
    var btn = e.target.closest('[data-nav]');
    if (btn) go(btn.dataset.nav);
  });

  $('#menuBtn').addEventListener('click', openSidebar);
  $('#sidebarClose').addEventListener('click', closeSidebar);
  $('#sidebarToggle').addEventListener('click', function () {
    if (window.innerWidth >= 1024) {
      toggleSidebar();
    } else {
      closeSidebar();
    }
  });
  $('#sidebarOverlay').addEventListener('click', closeSidebar);
  $('#userCard').addEventListener('click', function () { go('perfil'); });
  $('#refreshBtn').addEventListener('click', function () { reloadCurrent(); });

  var sdCache = {};
  var sdCacheTimer = null;

  var SD_CONFIG = {
    clientes:      { url: '/api/clientes/disponibles/?search=', nameField: 'nombre_completo', subField: 'documento_numero', emptyText: 'No se encontraron clientes' },
    tecnicos:      { url: '/api/tecnicos/disponibles/?search=', nameField: 'nombre', subField: 'especialidad', emptyText: 'No se encontraron técnicos' },
    supervisores:  { url: '/api/supervisores/?search=', nameField: 'nombre', subField: 'email', emptyText: 'No se encontraron supervisores' },
    equipos:       { url: '/api/equipos/?search=', nameField: 'cliente_nombre', subField: 'marca', emptyText: 'No se encontraron equipos' },
    solicitudes:   { url: '/api/solicitudes/?search=', nameField: 'cliente_nombre', subField: 'tipo_equipo_solicitado', emptyText: 'No se encontraron solicitudes' },
    instalaciones: { url: '/api/instalaciones/?search=', nameField: 'cliente_nombre', subField: 'equipo_nombre', emptyText: 'No se encontraron instalaciones' },
    servicios:     { url: '/api/servicios/?search=', nameField: 'numero', subField: 'cliente_nombre', emptyText: 'No se encontraron servicios' },
    mantenimientos:{ url: '/api/mantenimientos/?search=', nameField: 'equipo_nombre', subField: 'cliente_nombre', emptyText: 'No se encontraron mantenimientos' },
    evaluaciones:  { url: '/api/evaluaciones/?search=', nameField: 'cliente_nombre', subField: 'calificacion', emptyText: 'No se encontraron calificaciones' },
    usuarios:      { url: '/api/usuarios/?search=', nameField: 'full_name', subField: 'email', emptyText: 'No se encontraron usuarios' },
    visitas:       { url: '/api/visitas/?search=', nameField: 'numero', subField: 'cliente_nombre', emptyText: 'No se encontraron visitas' },
    cotizaciones:  { url: '/api/cotizaciones/?search=', nameField: 'numero', subField: 'cliente_nombre', emptyText: 'No se encontraron cotizaciones' },
    pagos: {
      facturas: { url: '/api/facturas/?search=', nameField: 'numero', subField: 'cliente_nombre', emptyText: 'No se encontraron facturas' },
      pagos:    { url: '/api/pagos/?search=', nameField: 'cliente_nombre', subField: 'referencia', emptyText: 'No se encontraron pagos' }
    },
    inventario: {
      materiales:  { url: '/api/materiales/?search=', nameField: 'nombre', subField: 'codigo', emptyText: 'No se encontraron materiales' },
      movimientos: { url: '/api/movimientos/?search=', nameField: 'material_nombre', subField: 'motivo', emptyText: 'No se encontraron movimientos' }
    },
    almacen: {
      productos:  { url: '/api/productos/?search=', nameField: 'nombre', subField: 'categoria', emptyText: 'No se encontraron productos' },
      categorias: { url: '/api/categorias/?search=', nameField: 'nombre', subField: 'descripcion', emptyText: 'No se encontraron categorías' },
      historial:  { url: '/api/movimientos/?search=', nameField: 'material_nombre', subField: 'motivo', emptyText: 'No se encontraron registros' }
    },
    tienda: {
      ordenes: { url: '/api/tienda/ordenes/?search=', nameField: 'numero', subField: 'nombre_cliente', emptyText: 'No se encontraron órdenes' },
      pagos:   { url: '/api/tienda/ordenes/?search=', nameField: 'numero', subField: 'nombre_cliente', emptyText: 'No se encontraron pagos' }
    }
  };

  function sdConfig() {
    var sec = SD_CONFIG[S.section];
    if (!sec) return null;
    if (sec.url) return sec;
    var s = currentListState();
    var tab = (s && s.tab) || Object.keys(sec)[0];
    return sec[tab] || null;
  }

  function sdCacheKey() {
    var sec = SD_CONFIG[S.section];
    if (!sec) return null;
    if (sec.url) return S.section;
    var s = currentListState();
    var tab = (s && s.tab) || Object.keys(sec)[0];
    return S.section + ':' + tab;
  }

  function sdFetchAll(baseUrl, search) {
    var token = localStorage.getItem('refri_access');
    var headers = token ? { 'Authorization': 'Bearer ' + token } : {};
    var out = [];
    var page = 1;
    function fetchPage() {
      var sep = baseUrl.indexOf('?') >= 0 ? '&' : '?';
      var url = baseUrl + sep + 'page=' + page;
      if (search) url += '&search=' + encodeURIComponent(search);
      return fetch(url, { headers: headers })
        .then(function (r) { return r.ok ? r.json() : { results: [] }; })
        .then(function (data) {
          var results = Array.isArray(data) ? data : (data.results || []);
          out = out.concat(results);
          var next = Array.isArray(data) ? null : data.next;
          if (next && results.length && page < 10) {
            page++;
            return fetchPage();
          }
          return out;
        });
    }
    return fetchPage();
  }

  /* ------------------------------------------------------------------
   * Búsqueda client-side genérica y extensible.
   *
   * Registrar un motor por sección:
   *   clientSideSearch({
   *     key: 'clientes',              // clave de cache (por sección/tab)
   *     url: '/api/clientes/',        // endpoint de la LISTA COMPLETA (sin search ni page)
   *     columns: columns,             // mismas columnas que usa el renderer de la tabla
   *     filter: function (item, q) { return bool; }
   *   });
   *
   * Comportamiento:
   *   - La lista completa se cachea UNA sola vez (nunca una lista filtrada).
   *   - Al escribir se filtra en memoria y se re-renderiza SOLO el tbody
   *     (no toca #view, no recarga la página, no cierra el teclado móvil).
   *   - Al vaciar el campo (val.trim() === '') se muestran TODOS de inmediato.
   *   - Nunca dispara reloadCurrent() al escribir.
   * ------------------------------------------------------------------ */
  var CSS_REGISTRY = {};
  var cssCache = {};

  function clientSideSearch(spec) {
    if (spec && spec.key) CSS_REGISTRY[spec.key] = spec;
  }

  // Clave del motor según la sección activa (+ tab cuando la sección es tabulada),
  // igual criterio que sdCacheKey() para que coincidan caché y registro.
  function cssKey() {
    var sec = SD_CONFIG[S.section];
    if (!sec) return S.section;
    if (sec.url) return S.section;
    var s = currentListState();
    var tab = (s && s.tab) || Object.keys(sec)[0];
    return S.section + ':' + tab;
  }

  function cssSpec() {
    return CSS_REGISTRY[cssKey()] || null;
  }

  function cssFullList(spec) {
    if (cssCache[spec.key]) return Promise.resolve(cssCache[spec.key]);
    var p = spec.source ? Promise.resolve(spec.source())
                        : sdFetchAll(API_BASE + spec.url);
    return p.then(function (list) {
      cssCache[spec.key] = list;   // siempre la lista completa, nunca filtrada
      return list;
    });
  }

  // Invalida la caché completa de una sección (todas sus pestañas).
  function cssClear(section) {
    Object.keys(cssCache).forEach(function (k) {
      if (k === section || k.indexOf(section + ':') === 0) delete cssCache[k];
    });
  }

  // Predicado de coincidencia genérico sobre una lista de campos.
  function cssMatcher(fields) {
    return function (item, q) {
      q = q.toLowerCase();
      for (var i = 0; i < fields.length; i++) {
        var v = item[fields[i]];
        if (v === null || v === undefined) continue;
        v = String(v);
        if (v.toLowerCase().indexOf(q) >= 0) return true;
      }
      return false;
    };
  }

  // Registro abreviado y reutilizable:
  //   cssRegister({ key, url, columns, fields: [...], active: [filtros...] | fn, source: fn|null })
  // - active: lista de filtros de estado/tipo que desactivan la búsqueda client-side
  //   (si están activos se conserva el comportamiento de servidor existente y no se rompen).
  function cssRegister(opts) {
    var spec = { key: opts.key, url: opts.url, columns: opts.columns };
    if (typeof opts.filter === 'function') spec.filter = opts.filter;
    else spec.filter = cssMatcher(opts.fields || []);
    if (typeof opts.active === 'function') spec.active = opts.active;
    else if (Array.isArray(opts.active)) {
      var keys = opts.active;
      spec.active = function () {
        var s = currentListState();
        if (!s) return true;
        return keys.every(function (f) { return !s[f]; });
      };
    }
    if (typeof opts.source === 'function') spec.source = opts.source;
    clientSideSearch(spec);
  }

  function renderCssBody(spec, full) {
    var input = $('#view [data-search]');
    var q = input ? input.value.trim() : '';
    var items = q ? full.filter(function (it) { return spec.filter(it, q); })
                   : full;   // vacío → TODOS los registros, de inmediato
    var body = $('#view [data-list-body]');
    if (body) body.innerHTML = tableRows(spec.columns, items);
    // Reemplazo el pie de paginación por un contador local (sin recargar nada).
    var ov = body ? body.closest('.overflow-x-auto') : null;
    var foot = ov ? ov.nextElementSibling : null;
    if (foot && foot.querySelector('[data-action="page"]')) {
      foot.innerHTML = '<div class="flex items-center justify-between gap-2 px-4 py-3">' +
        '<span class="text-xs text-on-surface-variant">' + items.length + ' registros</span></div>';
    }
  }

  function renderSearchDropdown(drop, list, query, cfg) {
    cfg = cfg || sdConfig();
    var q = query.toLowerCase();
    // Las sugerencias existen solo mientras se escribe una búsqueda.
    // Sin texto o sin coincidencias → se ocultan por completo (nada congelado).
    if (!q) {
      drop.innerHTML = '';
      drop.classList.add('hidden');
      return;
    }
    var filtered = list.filter(function (c) {
      return (c[cfg.nameField] || '').toLowerCase().indexOf(q) >= 0 ||
             String(c[cfg.subField] || '').toLowerCase().indexOf(q) >= 0 ||
             (c.email || '').toLowerCase().indexOf(q) >= 0;
    });
    if (!filtered.length) {
      drop.innerHTML = '';
      drop.classList.add('hidden');
      return;
    }
    drop.innerHTML = filtered.map(function (c) {
      return '<button type="button" data-sd-id="' + c.id + '">' +
        '<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-container text-[11px] font-bold text-primary">' +
          esc((c[cfg.nameField] || '?').charAt(0).toUpperCase()) + '</span>' +
        '<span class="min-w-0 flex-1 truncate"><span class="sd-name">' + esc(c[cfg.nameField]) + '</span>' +
          (c[cfg.subField] ? ' <span class="sd-sub">' + esc(c[cfg.subField]) + '</span>' : '') + '</span></button>';
    }).join('');
    drop.classList.remove('hidden');
  }

  function filterSearchDropdown(drop, query, cfg) {
    cfg = cfg || sdConfig();
    var key = sdCacheKey();
    var list = (key && sdCache[key]) || sdCache;
    if (!Array.isArray(list)) list = [];
    var q = query.toLowerCase();
    var filtered = q ? list.filter(function (c) {
      return (c[cfg.nameField] || '').toLowerCase().indexOf(q) >= 0 ||
             String(c[cfg.subField] || '').toLowerCase().indexOf(q) >= 0 ||
             (c.email || '').toLowerCase().indexOf(q) >= 0;
    }) : list;
    if (!filtered.length) {
      drop.innerHTML = '<div class="sd-empty">' + esc(cfg.emptyText) + '</div>';
    } else {
      drop.innerHTML = filtered.map(function (c) {
        return '<button type="button" data-sd-id="' + c.id + '">' +
          '<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-container text-[11px] font-bold text-primary">' +
            esc((c[cfg.nameField] || '?').charAt(0).toUpperCase()) + '</span>' +
          '<span class="min-w-0 flex-1 truncate"><span class="sd-name">' + esc(c[cfg.nameField]) + '</span>' +
            (c[cfg.subField] ? ' <span class="sd-sub">' + esc(c[cfg.subField]) + '</span>' : '') + '</span></button>';
      }).join('');
    }
    drop.classList.remove('hidden');
  }

  // Acción existente que se ejecuta al hacer clic en una fila, según la sección y
  // pestaña activa. 'detail' = detalle de solo lectura propio. null = sin flujo.
  function rowClickResolution() {
    var sec = S.section;
    var stt = currentListState();
    var tab = stt ? stt.tab : null;
    switch (sec) {
      case 'clientes':
      case 'tecnicos':
      case 'supervisores':
        return 'detail';
      case 'equipos': return 'historial';
      case 'mis_equipos': return 'editar';
      case 'solicitudes': return 'editar';
      case 'instalaciones': return 'ver';
      case 'servicios': return 'ver';
      case 'mantenimientos': return 'editar';
      case 'visitas': return 'editar';
      case 'cotizaciones': return 'ver';
      case 'usuarios': return 'editar';
      case 'inventario': return tab === 'movimientos' ? null : 'editar';
      case 'almacen': return tab === 'productos' ? 'editar' : tab === 'categorias' ? 'editar_categoria' : null;
      case 'pagos': return tab === 'facturas' ? 'ver_factura' : tab === 'pagos' ? 'editar' : null;
      case 'tienda': return tab === 'ordenes' ? 'ver_orden' : null;
      default: return null;
    }
  }

  $('#view').addEventListener('click', function (e) {
    var icon = e.target.closest('[data-search-icon]');
    if (icon) {
      var wrap = icon.closest('.relative');
      var input = wrap ? wrap.querySelector('[data-search]') : null;
      var drop = wrap ? wrap.querySelector('[data-search-dropdown]') : null;
      if (!input || !drop) return;
      e.preventDefault();
      clearTimeout(searchTimer);
      var cfg = sdConfig();
      var key = sdCacheKey();
      if (!cfg || !key) { drop.classList.add('hidden'); return; }
      if (drop.classList.contains('hidden')) {
        if (sdCache[key] && sdCache[key].length) {
          renderSearchDropdown(drop, sdCache[key], input.value, cfg);
          input.focus();
        } else {
          drop.innerHTML = '<div class="sd-empty">Cargando…</div>';
          drop.classList.remove('hidden');
          sdFetchAll(API_BASE + cfg.url.split('?')[0]).then(function (list) {
            sdCache[key] = list;
            if (drop.classList.contains('hidden')) return;
            renderSearchDropdown(drop, list, input.value, cfg);
          }).catch(function () {
            drop.innerHTML = '<div class="sd-empty">Error al cargar</div>';
          });
          input.focus();
        }
      } else {
        drop.classList.add('hidden');
        input.focus();
      }
      return;
    }
    if (!e.target.closest('[data-search-dropdown]')) {
      var d = document.querySelector('#view [data-search-dropdown]');
      if (d) d.classList.add('hidden');
    }
    var cliItem = e.target.closest('[data-search-dropdown] [data-sd-id]');
    if (cliItem) {
      var wrap = cliItem.closest('.relative');
      var input = wrap ? wrap.querySelector('[data-search]') : null;
      var drop = wrap ? wrap.querySelector('[data-search-dropdown]') : null;
      if (input) {
        var cName = '';
        var cId = cliItem.dataset.sdId;
        var nameEl = cliItem.querySelector('.sd-name');
        if (nameEl) cName = nameEl.textContent;
        input.value = cName;
        if (drop) drop.classList.add('hidden');
        var s = currentListState();
        if (s) { s.search = cName; s.page = 1; reloadCurrent(); }
      }
      return;
    }
    var mod = e.target.closest('[data-module]');
    if (mod) { goToModule(mod.dataset.module); return; }

    // Clic en la fila → muestra la información del registro reutilizando la acción
    // existente de esa sección (ver / detalle / historial / editar).
    // Excluye clics sobre botones de acción (Editar/Eliminar/Ver…) que siguen igual.
    if (!e.target.closest('[data-action]')) {
      var row = e.target.closest('#view [data-list-body] tr[data-id]');
      if (row && row.dataset.id) {
        var rAction = rowClickResolution();
        var rId = Number(row.dataset.id);
        if (rAction === 'detail') {
          // Detalles de solo lectura propios (Clientes / Técnicos / Supervisores).
          e.preventDefault();
          var url = (S.section === 'clientes') ? '/api/clientes/'
                  : (S.section === 'tecnicos') ? '/api/tecnicos/'
                  : '/api/supervisores/';
          getItem(url + rId + '/').then(function (item) {
            if (S.section === 'clientes') openClienteDetail(item);
            else if (S.section === 'tecnicos') openTecnicoDetail(item);
            else openSupervisorDetail(item);
          });
          return;
        }
        if (rAction) {
          e.preventDefault();
          onAction(rAction, rId);
          return;
        }
      }
    }

    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    var action = btn.dataset.action;
    var id = btn.dataset.id;
    if (action === 'page') {
      var s = currentListState();
      if (!s) return;
      s.page = Math.max(1, (s.page || 1) + (btn.dataset.page === 'prev' ? -1 : 1));
      reloadCurrent();
      return;
    }
    if (action === 'tab') {
      var st = currentListState();
      if (st) st.tab = btn.dataset.tab;
      reloadCurrent();
      return;
    }
    if (action === 'retry') { reloadCurrent(); return; }
    onAction(action, id, btn);
  });

  var searchTimer = null;
  $('#view').addEventListener('input', function (e) {
    if (!e.target.matches('[data-search]')) return;
    var val = e.target.value;

    var spec = cssSpec();
    if (spec && (!spec.active || spec.active())) {
      // Búsqueda client-side: filtra la tabla en memoria sin recargar #view,
      // sin recargar la página y sin cerrar el teclado móvil.
      clearTimeout(searchTimer);
      var s = currentListState();
      if (s) {
        s.search = val;
        if (val.trim() === '') s.page = 1;
      }
      cssFullList(spec).then(function (full) {
        if (e.target.value !== val) return;   // la entrada cambió mientras cargaba
        renderCssBody(spec, full);
        var cfg = sdConfig();
        var key = sdCacheKey();
        var wrap = e.target.closest('.relative');
        var drop = wrap ? wrap.querySelector('[data-search-dropdown]') : null;
        if (drop && cfg && key) renderSearchDropdown(drop, full, val.trim(), cfg);
      });
      return;
    }

    var cfg = sdConfig();
    var key = sdCacheKey();
    var wrap = e.target.closest('.relative');
    var drop = wrap ? wrap.querySelector('[data-search-dropdown]') : null;
    if (drop && cfg && key) {
      var full = sdCache[key];
      if (val.trim() === '') {
        var stt = currentListState();
        if (stt) { stt.search = ''; stt.page = 1; }
      }
      if (Array.isArray(full) && full.length) {
        renderSearchDropdown(drop, full, val.trim(), cfg);
      } else {
        drop.innerHTML = '<div class="sd-empty">Cargando…</div>';
        drop.classList.remove('hidden');
        clearTimeout(sdCacheTimer);
        sdCacheTimer = setTimeout(function () {
          sdFetchAll(API_BASE + cfg.url.split('?')[0]).then(function (list) {
            if (key) sdCache[key] = list;
            if (drop.classList.contains('hidden')) return;
            renderSearchDropdown(drop, list, val.trim(), cfg);
          }).catch(function () {});
        }, 300);
      }
    }
  });

  $('#view').addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.matches('[data-search]')) e.preventDefault();
    if (e.key === 'Escape' && e.target.matches('[data-search]')) {
      var drop = e.target.closest('.relative');
      if (drop) {
        var dd = drop.querySelector('[data-search-dropdown]');
        if (dd) dd.classList.add('hidden');
      }
    }
  });

  $('#view').addEventListener('change', function (e) {
    if (!e.target.matches('[data-filter]')) return;
    var s = currentListState();
    if (!s) return;
    s[e.target.dataset.filter] = e.target.value;
    s.page = 1;
    reloadCurrent();
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeModal();
      closeSidebar();
    }
  });

  $('#logoutBtn').addEventListener('click', async function () {
    var token = localStorage.getItem('refri_access');
    var refresh = localStorage.getItem('refri_refresh');
    try {
      await api('/api/auth/logout/', {
        method: 'POST',
        headers: token ? { 'Authorization': 'Bearer ' + token } : {},
        body: JSON.stringify({ refresh: refresh || '' }),
      });
    } catch (e) { /* las credenciales se limpian igual */ }
    clearSession();
    window.location.href = '/';
  });

  $('#year').textContent = new Date().getFullYear();

  /* ------------------------------------------------------------------
   * Arranque
   * ------------------------------------------------------------------ */
  async function boot() {
    if (!localStorage.getItem('refri_access')) { forceLogin(); return; }
    try {
      var cached = JSON.parse(localStorage.getItem('refri_user'));
      if (cached) S.user = cached;
    } catch (e) { /* sin caché */ }
    try {
      var me = await api('/api/auth/me/');
      S.user = me.user;
      localStorage.setItem('refri_user', JSON.stringify(me.user));
    } catch (e) {
      return; // api() ya redirige al expirar la sesión
    }
    if (!S.user) {
      $('#bootScreen').classList.add('hidden');
      var denied = $('#deniedScreen');
      denied.classList.remove('hidden');
      denied.classList.add('flex');
      return;
    }
    renderUser();
    buildNav();
    initGroupToggles();
    $$('#navList .nav-group-items.collapsed').forEach(function (el) {
      el.style.height = '0';
    });
    setupNotificaciones();
    try {
      if (localStorage.getItem('sidebar_closed') === '1' && window.innerWidth >= 1024) {
        var sb = $('#sidebar');
        sb.classList.add('sidebar-closed');
        $('#mainContent').classList.remove('lg:pl-64');
        $('#mainContent').classList.add('lg:pl-[72px]');
        var ti = sb.querySelector('#sidebarToggle .material-symbols-outlined');
        if (ti) ti.textContent = 'menu_open';
      }
    } catch (e) {}
    $('#bootScreen').classList.add('hidden');
    $('#app').classList.remove('hidden');
    var hash = location.hash || '';
    var qsIndex = hash.indexOf('?');
    var query = qsIndex >= 0 ? hash.slice(qsIndex + 1) : '';
    var cleanHash = qsIndex >= 0 ? hash.slice(0, qsIndex) : hash;
    if (query) {
      var sec = cleanHash.replace(/^#\//, '').replace(/\/.*$/, '');
      if (sec) {
        var params = {};
        query.split('&').forEach(function (pair) {
          var kv = pair.split('=');
          if (kv[0]) params[decodeURIComponent(kv[0])] = decodeURIComponent(kv[1] || '');
        });
        listState[sec] = Object.assign({ page: 1, search: '' }, listState[sec], params);
      }
    }
    var editMatch = cleanHash.match(/^#\/almacen\/editar\/(\d+)/);
    var initial = cleanHash.replace(/^#\//, '').replace(/almacen\/editar\/\d+/, 'almacen');
    go(initial || 'dashboard');
    if (editMatch) {
      getItem('/api/productos/' + editMatch[1] + '/')
        .then(function (p) { openProductoForm(p); })
        .catch(function () { toast('No se pudo abrir el producto.', 'error'); });
    }
  }

  boot();
})();
