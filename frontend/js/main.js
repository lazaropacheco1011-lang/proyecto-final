/* ==========================================================================
   RefriMaster — Lógica de la landing page
   - Modales de inicio de sesión, registro y solicitud de demo (API Django)
   - Menú móvil, sesión del usuario y notificaciones (toast)
   ========================================================================== */

(function () {
  'use strict';

  /* ------------------------------------------------------------------
   * Configuración de la API
   * Por defecto apunta al backend local (Django runserver).
   * Se puede sobreescribir con ?api=https://dominio en la URL.
   * ------------------------------------------------------------------ */
  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 window.location.origin;

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

  async function api(path, options) {
    options = options || {};
    var res = await fetch(API_BASE + path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
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

  function setBusy(sel, busy) {
    var btn = $(sel);
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

  function setFormMessage(sel, text, type) {
    var el = $(sel);
    if (!el) return;
    if (!text) {
      el.classList.add('hidden');
      el.textContent = '';
      return;
    }
    el.textContent = text;
    el.classList.remove(
      'hidden',
      'text-red-700', 'bg-red-50', 'border', 'border-red-200',
      'text-emerald-700', 'bg-emerald-50', 'border-emerald-200'
    );
    if (type === 'success') {
      el.classList.add('text-emerald-700', 'bg-emerald-50', 'border', 'border-emerald-200');
    } else {
      el.classList.add('text-red-700', 'bg-red-50', 'border', 'border-red-200');
    }
  }

  /* ---------- Modales ---------- */
  function openModal(name) {
    var m = $('#modal-' + name);
    if (!m) return;
    m.classList.remove('hidden');
    m.classList.add('flex');
    document.body.style.overflow = 'hidden';
    var first = m.querySelector('input');
    if (first) setTimeout(function () { first.focus(); }, 60);
  }

  function closeModal(name) {
    var m = $('#modal-' + name);
    if (!m) return;
    m.classList.add('hidden');
    m.classList.remove('flex');
    document.body.style.overflow = '';
  }

  function closeAll() {
    closeModal('login');
    closeModal('register');
    closeModal('recover');
    closeModal('reset');
  }

  $$('[data-open]').forEach(function (btn) {
    btn.addEventListener('click', function () { openModal(btn.dataset.open); });
  });

  $$('[data-close]').forEach(function (btn) {
    btn.addEventListener('click', function () { closeModal(btn.dataset.close); });
  });

  $$('[data-switch]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      closeAll();
      openModal(btn.dataset.switch);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });

  /* ---------- Sesión del usuario ---------- */
  var STAFF_ROLES = ['administrador', 'supervisor', 'tecnico', 'almacen'];

  function applySession(user) {
    var area = $('#sessionArea');
    var loginBtns = $('#loginBtns');
    var loginTriggers = $$('[data-open="login"]');
    var name = (user && (user.full_name || user.username)) || 'Usuario';
    var panelBtn = (user && STAFF_ROLES.indexOf(user.role) >= 0)
      ? '<a href="/admin-dashboard/" class="rounded-lg bg-primary px-4 py-2 font-label-md text-white transition-colors hover:bg-primary-hover">Panel</a>'
      : '';
    var avatar = (user && user.photo)
      ? '<a href="/admin-dashboard/" title="Ir a mi perfil" class="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary-container font-bold text-primary ring-2 ring-primary/30">' +
        '<img src="' + esc(user.photo) + '" alt="" class="h-full w-full object-cover"></a>'
      : '';
    area.innerHTML = panelBtn + avatar +
      '<span class="hidden font-body-md font-medium text-on-surface-variant md:inline">Hola, ' + esc(name) + '</span>' +
      '<button id="logoutBtn" class="rounded-lg border border-outline-variant px-4 py-2 font-label-md text-on-surface transition-colors hover:bg-surface-dim">Cerrar sesión</button>';
    area.classList.remove('hidden');
    area.classList.add('flex');
    if (loginBtns) loginBtns.classList.add('hidden');
    loginTriggers.forEach(function (btn) { btn.classList.add('hidden'); });
    var logoutBtn = $('#logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async function () {
        var token = localStorage.getItem('refri_access');
        var refresh = localStorage.getItem('refri_refresh');
        try {
          await api('/api/auth/logout/', {
            method: 'POST',
            headers: token ? { 'Authorization': 'Bearer ' + token } : {},
            body: JSON.stringify({ refresh: refresh || '' }),
          });
        } catch (e) { /* el token se limpia igual */ }
        localStorage.removeItem('refri_access');
        localStorage.removeItem('refri_refresh');
        localStorage.removeItem('refri_user');
        area.classList.add('hidden');
        area.classList.remove('flex');
        area.innerHTML = '';
        if (loginBtns) loginBtns.classList.remove('hidden');
        loginTriggers.forEach(function (btn) { btn.classList.remove('hidden'); });
        toast('Sesión cerrada correctamente.', 'success');
      });
    }
  }

  (function initSession() {
    try {
      var raw = localStorage.getItem('refri_user');
      if (raw) applySession(JSON.parse(raw));
    } catch (e) { /* sin sesión */ }
  })();

  /* ---------- Login ---------- */
  $('#loginForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var username = $('#loginUser').value.trim();
    var password = $('#loginPass').value;
    if (!username || !password) {
      setFormMessage('#loginMsg', 'Ingresa usuario y contraseña.', 'error');
      return;
    }
    setFormMessage('#loginMsg', '', '');
    setBusy('#loginBtn', true);
    try {
      var data = await api('/api/auth/login/', {
        method: 'POST',
        body: JSON.stringify({ username: username, password: password }),
      });
      localStorage.setItem('refri_access', data.access);
      localStorage.setItem('refri_refresh', data.refresh);
      localStorage.setItem('refri_user', JSON.stringify(data.user));
      applySession(data.user);
      loadRealStats();
      closeModal('login');
      toast('¡Bienvenido, ' + (data.user.full_name || data.user.username) + '!', 'success');
      var checkoutReturn = null;
      try { checkoutReturn = localStorage.getItem('refri_checkout_return'); localStorage.removeItem('refri_checkout_return'); } catch (e) { /* ok */ }
      if (checkoutReturn) {
        window.location.href = checkoutReturn;
      } else if (data.user && STAFF_ROLES.indexOf(data.user.role) >= 0) {
        window.location.href = '/admin-dashboard/';
      }
    } catch (err) {
      setFormMessage('#loginMsg', apiErrorMessage(err), 'error');
    } finally {
      setBusy('#loginBtn', false);
    }
  });

  /* ---------- Registro ---------- */
  $('#registerForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var payload = {
      username: $('#regUser').value.trim(),
      email: $('#regEmail').value.trim(),
      password: $('#regPass').value,
      first_name: $('#regFirst').value.trim(),
      last_name: $('#regLast').value.trim(),
      phone: $('#regPhone').value.trim(),
      tipo_documento: $('#regDocType').value,
      documento: $('#regDoc').value.trim(),
      direccion: $('#regDirec').value.trim(),
      role: 'cliente',
    };
    if (!payload.username || !payload.email || !payload.password) {
      setFormMessage('#registerMsg', 'Usuario, correo y contraseña son obligatorios.', 'error');
      return;
    }
    if (!payload.documento) {
      setFormMessage('#registerMsg', 'El número de documento es obligatorio.', 'error');
      return;
    }
    if (payload.password.length < 8) {
      setFormMessage('#registerMsg', 'La contraseña debe tener al menos 8 caracteres.', 'error');
      return;
    }
    if (/^\d+$/.test(payload.password)) {
      setFormMessage('#registerMsg', 'La contraseña no puede ser solo números.', 'error');
      return;
    }
    setFormMessage('#registerMsg', '', '');
    setBusy('#registerBtn', true);
    try {
      var data = await api('/api/auth/register/', { method: 'POST', body: JSON.stringify(payload) });
      localStorage.setItem('refri_access', data.access);
      localStorage.setItem('refri_refresh', data.refresh);
      localStorage.setItem('refri_user', JSON.stringify(data.user));
      applySession(data.user);
      loadRealStats();
      closeModal('register');
      toast('Cuenta creada. ¡Bienvenido, ' + (data.user.full_name || data.user.username) + '!', 'success');
      var checkoutReturn = null;
      try { checkoutReturn = localStorage.getItem('refri_checkout_return'); localStorage.removeItem('refri_checkout_return'); } catch (e) { /* ok */ }
      if (checkoutReturn) {
        window.location.href = checkoutReturn;
      }
    } catch (err) {
      setFormMessage('#registerMsg', apiErrorMessage(err), 'error');
    } finally {
      setBusy('#registerBtn', false);
    }
  });

  /* ---------- Recuperar contraseña ---------- */
  $('#recoverForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var email = $('#recoverEmail').value.trim();
    if (!email) {
      setFormMessage('#recoverMsg', 'Ingresa tu correo electrónico.', 'error');
      return;
    }
    setFormMessage('#recoverMsg', '', '');
    setBusy('#recoverBtn', true);
    try {
      var data = await api('/api/auth/password/recuperar/', {
        method: 'POST',
        body: JSON.stringify({ email: email }),
      });
      setFormMessage('#recoverMsg', data.detail || data.message ||
        'Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.', 'success');
    } catch (err) {
      setFormMessage('#recoverMsg', apiErrorMessage(err), 'error');
    } finally {
      setBusy('#recoverBtn', false);
    }
  });

  /* ---------- Restablecer contraseña (token del correo) ---------- */
  function resetMode(token, email) {
    $('#resetToken').value = token || '';
    $('#resetForm').classList.remove('hidden');
    $('#resetDone').classList.add('hidden');
    $('#resetMsg').classList.add('hidden');
    if (email) {
      $('#resetEmailHint').textContent = 'Restablece la contraseña de ' + email + '.';
    } else {
      $('#resetEmailHint').textContent = 'Define tu nueva contraseña.';
    }
    setFormMessage('#resetMsg', '', '');
    openModal('reset');
    closeModal('recover');
  }

  $('#resetForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var token = $('#resetToken').value;
    var p1 = $('#resetPass').value;
    var p2 = $('#resetPass2').value;
    if (!token) {
      setFormMessage('#resetMsg', 'El enlace de recuperación es inválido o ha caducado.', 'error');
      return;
    }
    if (p1.length < 8) {
      setFormMessage('#resetMsg', 'La contraseña debe tener al menos 8 caracteres.', 'error');
      return;
    }
    if (/^\d+$/.test(p1)) {
      setFormMessage('#resetMsg', 'La contraseña no puede ser solo números.', 'error');
      return;
    }
    if (p1 !== p2) {
      setFormMessage('#resetMsg', 'Las contraseñas no coinciden.', 'error');
      return;
    }
    setFormMessage('#resetMsg', '', '');
    setBusy('#resetBtn', true);
    try {
      await api('/api/auth/password/restablecer/', {
        method: 'POST',
        body: JSON.stringify({ token: token, password: p1, password2: p2 }),
      });
      $('#resetForm').classList.add('hidden');
      $('#resetDone').classList.remove('hidden');
      var q = new URLSearchParams(window.location.search);
      q.delete('reset');
      q.delete('correo');
      var qs = q.toString();
      window.history.replaceState({}, '', window.location.pathname + (qs ? '?' + qs : ''));
    } catch (err) {
      setFormMessage('#resetMsg', apiErrorMessage(err), 'error');
    } finally {
      setBusy('#resetBtn', false);
    }
  });

  (function initPasswordReset() {
    var params = new URLSearchParams(window.location.search);
    var token = params.get('reset');
    if (token) resetMode(token, params.get('correo'));
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

  /* ---------- Año del footer ---------- */
  var yearEl = $('#year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  /* ---------- Efecto de scroll del navbar ---------- */
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

  /* ---------- Tarjetas del catálogo → producto en /productos/ ---------- */
  $$('[data-producto-link]').forEach(function (card) {
    card.addEventListener('click', function (e) {
      var id = card.dataset.productoLink;
      if (id) window.location.href = '/productos/?producto=' + encodeURIComponent(id);
    });
  });

  /* ---------- Estadísticas reales (si hay sesión y permisos) ---------- */
  function setStat(valueEl, suffixEl, value) {
    if (value == null) return;
    if (valueEl) valueEl.textContent = new Intl.NumberFormat('es-DO').format(value);
    if (suffixEl) suffixEl.textContent = '';
  }

  async function loadRealStats() {
    var token = localStorage.getItem('refri_access');
    if (!token) return;
    try {
      var res = await fetch(API_BASE + '/api/dashboard/', {
        headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
      });
      if (!res.ok) return;
      var d = await res.json();
      setStat($('#statInstalaciones'), $('#statInstalacionesSuf'), d.total_instalaciones);
      setStat($('#statClientes'), $('#statClientesSuf'), d.total_clientes);
      setStat($('#statTecnicos'), $('#statTecnicosSuf'), d.total_tecnicos);
      setStat($('#statProyectos'), $('#statProyectosSuf'), d.instalaciones_realizadas);
    } catch (e) { /* sin datos reales: se mantienen los valores por defecto */ }
  }
  /* ---------- Formulario de contacto ---------- */
  var contactForm = $('#contactForm');
  if (contactForm) {
    contactForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var nombre = $('#ctNombre').value.trim();
      var correo = $('#ctCorreo').value.trim();
      var telefono = $('#ctTelefono').value.trim();
      var asunto = $('#ctAsunto').value;
      var mensaje = $('#ctMensaje').value.trim();
      if (!nombre || !correo || !mensaje) {
        setFormMessage('#ctMsg', 'Completa tu nombre, correo y mensaje.', 'error');
        return;
      }
      setFormMessage('#ctMsg', '', '');
      var body = 'Nombre: ' + nombre + '\n' +
        'Correo: ' + correo + '\n' +
        (telefono ? 'Teléfono: ' + telefono + '\n' : '') +
        'Asunto: ' + asunto + '\n' +
        '\n' + mensaje;
      var mailto = 'mailto:' + EMPRESA.email +
        '?subject=' + encodeURIComponent('Consulta de contacto: ' + asunto + ' — ' + nombre) +
        '&body=' + encodeURIComponent(body);
      window.open(mailto, '_blank');
      contactForm.reset();
      setFormMessage('#ctMsg', 'Se abrirá tu gestor de correo con la consulta lista para enviar. ¡Gracias por contactarnos!', 'success');
    });
  }

  /* ---------- Calculadora de BTU/h ---------- */
  var BTU_MAX_REF = 48000;
  var BTU_AJUSTES = {
    sol: { baja: 0, media: 0.05, alta: 0.10 },
    tipo: { habitacion: 0, sala: 0.05, oficina: 0.10, comercio: 0.15, cocina: 0.20, otro: 0 },
  };

  function calcularBTU(datos) {
    var area = datos.largo * datos.ancho;
    var base = area * 600 * (datos.alto / 2.5);
    var factor = 1 + BTU_AJUSTES.sol[datos.sol] + BTU_AJUSTES.tipo[datos.tipo];
    var btu = base * factor + datos.personas * 600 + datos.ventanas * 600;
    return Math.max(1000, Math.round(btu / 500) * 500);
  }

  function formatBTU(n) {
    return new Intl.NumberFormat('es-DO', { maximumFractionDigits: 0 }).format(n);
  }

  function btuGaugePct(btu) {
    return Math.min(100, Math.max(5, (btu / BTU_MAX_REF) * 100));
  }

  function parseBTU(nombre) {
    var m = String(nombre).match(/(\d+(?:[.,]\d{3})*)\s*BTU/i);
    if (!m) return null;
    var num = parseFloat(m[1].replace(/\./g, ''));
    return { btu: num, token: m[1] };
  }

  function bestMatch(btu, products) {
    var parsed = [];
    products.forEach(function (p) {
      var b = parseBTU(p.nombre);
      if (b) parsed.push({ product: p, btu: b.btu, token: b.token });
    });
    if (!parsed.length) return null;
    var best = parsed[0];
    parsed.forEach(function (cand) {
      var dc = Math.abs(cand.btu - btu);
      var db = Math.abs(best.btu - btu);
      if (dc < db || (dc === db && cand.btu > best.btu)) best = cand;
    });
    return best;
  }

  function fetchAllPages(url) {
    var out = [];
    function next(page) {
      return api(url + (url.indexOf('?') >= 0 ? '&' : '?') + 'page=' + page).then(function (d) {
        out = out.concat(d.results || []);
        if (d.next) return next(page + 1);
        return out;
      });
    }
    return next(1);
  }

  var btuAC = null;
  function ensureAC() {
    if (btuAC) return Promise.resolve(btuAC);
    return api('/api/categorias/').then(function (cats) {
      var cat = null;
      for (var i = 0; i < cats.length; i++) {
        if (/aire acondicionado/i.test(cats[i].nombre)) { cat = cats[i]; break; }
      }
      if (!cat) { btuAC = { cat: null, products: null }; return btuAC; }
      return fetchAllPages('/api/productos/?categoria=' + encodeURIComponent(cat.id)).then(function (products) {
        btuAC = { cat: cat, products: products };
        return btuAC;
      });
    }).catch(function () {
      btuAC = { cat: null, products: null };
      return btuAC;
    });
  }

  function resolveBtuLink(btu) {
    return ensureAC().then(function (data) {
      if (!data.cat || !data.products) {
        return { href: '/productos/?search=' + encodeURIComponent('aire acondicionado'), matchName: null };
      }
      var m = bestMatch(btu, data.products);
      if (!m) {
        return { href: '/productos/?categoria=' + encodeURIComponent(data.cat.id), matchName: null };
      }
      return {
        href: '/productos/?categoria=' + encodeURIComponent(data.cat.id) + '&search=' + encodeURIComponent(m.token),
        matchName: m.product.nombre,
      };
    });
  }

  var btuForm = $('#btuForm');
  if (btuForm) {
    btuForm.addEventListener('submit', function (e) {
      e.preventDefault();
      function readNum(sel, min, max, label) {
        var raw = $(sel).value.trim();
        if (raw === '') return { err: 'Completa ' + label + '.' };
        var v = parseFloat(raw);
        if (isNaN(v)) return { err: label + ' debe ser un número.' };
        if (v < min) return { err: label + ' no puede ser menor que ' + min + '.' };
        if (v > max) return { err: label + ' no puede ser mayor que ' + max + '.' };
        return { v: v };
      }

      var largo = readNum('#btuLargo', 0.5, 60, 'El largo del espacio');
      var ancho = readNum('#btuAncho', 0.5, 60, 'El ancho del espacio');
      var alto = readNum('#btuAlto', 1.5, 10, 'La altura del techo');
      var personas = readNum('#btuPersonas', 0, 200, 'La cantidad de personas');
      var ventanas = readNum('#btuVentanas', 0, 50, 'La cantidad de ventanas');

      var invalidos = [largo, ancho, alto, personas, ventanas].filter(function (r) { return r.err; });
      if (invalidos.length) {
        setFormMessage('#btuMsg', invalidos[0].err, 'error');
        return;
      }

      var btu = calcularBTU({
        largo: largo.v, ancho: ancho.v, alto: alto.v,
        personas: personas.v, ventanas: ventanas.v,
        sol: $('#btuSol').value, tipo: $('#btuTipo').value,
      });

      setFormMessage('#btuMsg', '', '');
      $('#btuEmpty').classList.add('hidden');
      var result = $('#btuResultContent');
      result.classList.remove('hidden');
      result.classList.add('flex');
      $('#btuValor').innerHTML = formatBTU(btu) + ' <span class="text-2xl font-bold">BTU/h</span>';
      $('#btuGauge').style.width = btuGaugePct(btu) + '%';
      result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

      var eqText = $('#btuEquiposText');
      var link = $('#btuVer');
      eqText.textContent = 'Buscando equipos disponibles…';
      resolveBtuLink(btu).then(function (r) {
        link.href = r.href;
        if (r.matchName) {
          eqText.innerHTML = 'Coincide con: <strong>' + esc(r.matchName) + '</strong>';
        } else {
          eqText.textContent = 'Te mostramos los equipos de aire acondicionado disponibles en la vitrina.';
        }
      });
    });
  }

  loadRealStats();

  if (new URLSearchParams(location.search).get('open_login') === '1') {
    openModal('login');
  }
})();
