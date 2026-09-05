/* ==========================================================================
   RefriMaster — Sesión del usuario y perfil del cliente (compartido)
   - Renderiza la barra de sesión (#sessionArea) en todas las páginas.
   - Habilita el acceso al perfil (#modal-profile) cuando el modal existe.
   - Lógica extraída de main.js para reutilizarse en Productos y Carrito.
   ========================================================================== */
(function () {
  'use strict';

  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 window.location.origin;

  var STAFF_ROLES = ['administrador', 'supervisor', 'tecnico', 'almacen'];

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
    if (!el) return;
    el.textContent = message;
    el.className = 'toast show' + (type ? ' ' + type : '');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { el.className = 'toast'; }, 3600);
  }

  function apiAuth(path, options) {
    options = options || {};
    var token = localStorage.getItem('refri_access');
    return fetch(API_BASE + path, {
      ...options,
      headers: {
        ...(options.headers || {}),
        ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
      },
    });
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

  /* ---------- Modales (perfil) ---------- */
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

  /* ---------- Perfil del cliente ---------- */
  function setProfMsg(text, type) {
    var el = $('#profMsg');
    if (!el) return;
    if (!text) {
      el.classList.add('hidden');
      el.textContent = '';
      return;
    }
    el.textContent = text;
    el.classList.remove('hidden', 'text-red-700', 'bg-red-50', 'border', 'border-red-200',
      'text-emerald-700', 'bg-emerald-50', 'border-emerald-200');
    if (type === 'success') {
      el.classList.add('text-emerald-700', 'bg-emerald-50', 'border', 'border-emerald-200');
    } else {
      el.classList.add('text-red-700', 'bg-red-50', 'border', 'border-red-200');
    }
  }

  function profileAvatar(photo) {
    var img = $('#profAvatar');
    var letter = $('#profAvatarLetter');
    if (!img || !letter) return;
    if (photo) {
      img.src = photo;
      img.classList.remove('hidden');
      letter.classList.add('hidden');
    } else {
      img.classList.add('hidden');
      letter.classList.remove('hidden');
    }
  }

  async function openProfileModal(user) {
    var token = localStorage.getItem('refri_access');
    if (!token) return;
    try {
      var res = await apiAuth('/api/auth/me/perfil/');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      var p = (data && data.perfil) || {};
      if ($('#profFirst')) $('#profFirst').value = p.nombre || p.first_name || '';
      if ($('#profLast')) $('#profLast').value = p.apellidos || p.last_name || '';
      profileAvatar(p.photo || null);
      if ($('#profUserInfo')) {
        $('#profUserInfo').textContent = (p.username || '') + (p.role ? ' · ' + (p.role_display || p.role) : '');
      }
      // "Mis compras" solo se muestra al rol cliente (seguridad: el endpoint
      // /api/tienda/mis-compras/ ya devuelve 403 para otros roles).
      var misCompras = $('#misComprasLink');
      if (misCompras) misCompras.classList.toggle('hidden', p.role !== 'cliente');
      setProfMsg('', '');
      openModal('profile');
    } catch (e) {
      toast('No se pudo cargar tu perfil.', 'error');
    }
  }

  function bindProfileClose() {
    $$('#modal-profile [data-close="profile"]').forEach(function (btn) {
      btn.addEventListener('click', function () { closeModal('profile'); });
    });
  }

  /* ---------- Sesión del usuario ---------- */
  function applySession(user) {
    var area = $('#sessionArea');
    if (!area) return;
    var loginBtns = $('#loginBtns');
    var loginTriggers = $$('[data-open="login"]');
    var panelBtn = (user && STAFF_ROLES.indexOf(user.role) >= 0)
      ? '<a href="/admin-dashboard/" class="rounded-lg bg-primary px-4 py-2 font-label-md text-white transition-colors hover:bg-primary-hover">Panel</a>'
      : '';
    // El perfil (avatar clicable + "Mis compras") se habilita donde existe el
    // modal de perfil (#modal-profile).
    var hasProfile = !!$('#modal-profile');

    // Sin sesión y sin botones de login (Almacén/Carrito): se conserva el
    // enlace de inicio de sesión original de esas páginas.
    if (!user && !loginBtns) {
      area.innerHTML = '<a href="/" class="inline-flex items-center gap-2 rounded-xl border-2 border-primary/25 px-4 py-2 font-label-md font-bold text-primary transition-all hover:border-primary hover:bg-primary-container active:scale-95"><span class="material-symbols-outlined text-base">login</span>Iniciar Sesión</a>';
      area.classList.remove('hidden');
      area.classList.add('flex');
      return;
    }

    // Sin sesión en páginas con botones de login: no se toca la sesión,
    // se conservan visibles los botones de iniciar sesión / registrarse.
    if (!user) return;

    // Solo la foto/avatar del usuario, sin "Hola, {nombre}". Circular, pequeño,
    // con anillo semitransparente (ring-primary/30), sombra suave y hover sutil.
    // El clic abre el perfil igual que en Inicio (#modal-profile); si no hay
    // foto se muestra un avatar de respaldo con el icono person.
    var avatar = '<button type="button" data-open="profile" title="Abrir mi perfil" class="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary-container font-bold text-primary ring-2 ring-primary/30 shadow-sm transition-all duration-200 hover:scale-[1.05] hover:ring-primary">' +
      (user && user.photo
        ? '<img src="' + esc(user.photo) + '" alt="Mi perfil" class="h-full w-full object-cover">'
        : '<span class="material-symbols-outlined text-base">person</span>') +
      '</button>';
    area.innerHTML = panelBtn + avatar +
      '<button id="logoutBtn" class="rounded-lg border border-outline-variant px-2.5 py-1.5 font-label-md text-on-surface transition-colors hover:bg-surface-dim md:px-4 md:py-2">Cerrar sesión</button>';
    area.classList.remove('hidden');
    area.classList.add('flex');
    if (loginBtns) loginBtns.classList.add('hidden');
    loginTriggers.forEach(function (btn) { btn.classList.add('hidden'); });
    if (hasProfile) {
      $$('#sessionArea [data-open="profile"]').forEach(function (btn) {
        btn.addEventListener('click', function () { openProfileModal(user); });
      });
    }
    var logoutBtn = $('#logoutBtn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', async function () {
        var token = localStorage.getItem('refri_access');
        var refresh = localStorage.getItem('refri_refresh');
        try {
          await apiAuth('/api/auth/logout/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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

  /* ---------- Formularios del perfil ---------- */
  var profNameForm = $('#profNameForm');
  if (profNameForm) {
    profNameForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var first = $('#profFirst').value.trim();
      var last = $('#profLast').value.trim();
      if (!first) { setProfMsg('El nombre no puede estar vacío.', 'error'); return; }
      setBusy('#profNameBtn', true);
      try {
        var res = await apiAuth('/api/auth/me/perfil/', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ first_name: first, last_name: last }),
        });
        var data = await res.json();
        if (!res.ok) throw new Error('HTTP ' + res.status);
        var u = (data && data.perfil) || {};
        var nuevoUser = Object.assign({}, JSON.parse(localStorage.getItem('refri_user') || '{}'),
          { first_name: first, last_name: last, full_name: ((u.nombre || first) + ' ' + (u.apellidos || last)).trim() || (u.username || '') });
        localStorage.setItem('refri_user', JSON.stringify(nuevoUser));
        setProfMsg('Nombre actualizado correctamente.', 'success');
        applySession(nuevoUser);
      } catch (err) {
        setProfMsg('No se pudo actualizar el nombre. Verifica los datos.', 'error');
      } finally {
        setBusy('#profNameBtn', false);
      }
    });
  }

  var profPhotoForm = $('#profPhotoForm');
  if (profPhotoForm) {
    profPhotoForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var input = $('#profPhotoInput');
      if (!input || !input.files || !input.files.length) {
        setProfMsg('Selecciona una imagen para subir.', 'error');
        return;
      }
      var archivo = input.files[0];
      if (archivo.size > 5 * 1024 * 1024) {
        setProfMsg('La imagen supera el tamaño máximo de 5 MB.', 'error');
        return;
      }
      setBusy('#profPhotoBtn', true);
      try {
        var fd = new FormData();
        fd.append('foto', archivo);
        var res = await apiAuth('/api/auth/me/foto/', { method: 'POST', body: fd });
        var texto = await res.text();
        var data = null;
        try { data = texto ? JSON.parse(texto) : null; } catch (e) { data = null; }
        if (!res.ok) {
          var motivo = (data && (data.error || data.detail))
            ? data.error || data.detail
            : ('Error ' + res.status);
          throw new Error(motivo);
        }
        if (data && data.user && data.user.photo) {
          var nuevoUser = Object.assign({}, JSON.parse(localStorage.getItem('refri_user') || '{}'),
            { photo: data.user.photo });
          localStorage.setItem('refri_user', JSON.stringify(nuevoUser));
          profileAvatar(data.user.photo);
          applySession(nuevoUser);
        }
        setProfMsg('Foto de perfil actualizada.', 'success');
      } catch (err) {
        setProfMsg('No se pudo subir la foto: ' + (err && err.message ? err.message : 'error inesperado.'), 'error');
      } finally {
        setBusy('#profPhotoBtn', false);
      }
    });
  }

  var profPassForm = $('#profPassForm');
  if (profPassForm) {
    profPassForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      var actual = $('#profPassActual').value;
      var nueva = $('#profPassNueva').value;
      var conf = $('#profPassConf').value;
      if (!actual || !nueva || !conf) {
        setProfMsg('Completa todos los campos de contraseña.', 'error');
        return;
      }
      if (nueva.length < 8) {
        setProfMsg('La nueva contraseña debe tener al menos 8 caracteres.', 'error');
        return;
      }
      if (/^\d+$/.test(nueva)) {
        setProfMsg('La nueva contraseña no puede ser solo números.', 'error');
        return;
      }
      if (nueva !== conf) {
        setProfMsg('Las contraseñas nuevas no coinciden.', 'error');
        return;
      }
      setBusy('#profPassBtn', true);
      try {
        var res = await apiAuth('/api/auth/password/cambiar/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            password_actual: actual,
            nueva_password: nueva,
            confirmar_nueva_password: conf,
          }),
        });
        var data = await res.json();
        if (!res.ok) throw new Error('HTTP ' + res.status);
        $('#profPassForm').reset();
        setProfMsg(data.message || 'Contraseña cambiada correctamente.', 'success');
      } catch (err) {
        var msg = 'No se pudo cambiar la contraseña. La contraseña actual debe ser correcta.';
        setProfMsg(msg, 'error');
      } finally {
        setBusy('#profPassBtn', false);
      }
    });
  }

  /* ---------- Arranque ---------- */
  function init() {
    if ($('#modal-profile')) bindProfileClose();
    try {
      var raw = localStorage.getItem('refri_user');
      applySession(raw ? JSON.parse(raw) : null);
    } catch (e) {
      applySession(null);
    }
  }

  /* ---------- API pública ---------- */
  window.RefriSession = {
    applySession: applySession,
    init: init,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
