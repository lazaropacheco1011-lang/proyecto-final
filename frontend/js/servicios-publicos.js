/* ==========================================================================
   RefriMaster — Páginas públicas de Mantenimiento y Reparaciones
   - Botones "Solicitar servicio/reparación"
   - Si no hay sesión: mensaje de cuenta requerida con "Registrarme"/"Iniciar sesión"
   - Si hay sesión (cliente): formulario que crea una solicitud vía API
   ========================================================================== */

(function () {
  'use strict';

  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 window.location.origin;

  function $(sel) {
    return document.querySelector(sel);
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

  function api(path, options) {
    options = options || {};
    var token = localStorage.getItem('refri_access');
    var headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return fetch(API_BASE + path, Object.assign({}, options, { headers: headers }))
      .then(function (res) {
        return res.json().catch(function () { return null; }).then(function (data) {
          if (!res.ok) {
            var err = new Error('API error ' + res.status);
            err.status = res.status;
            err.data = data;
            throw err;
          }
          return data;
        });
      });
  }

  function apiErrorMessage(err) {
    var d = err && err.data;
    if (!d) return 'No fue posible completar la petición. Verifica tu conexión.';
    if (typeof d === 'string') return d;
    if (typeof d === 'object') {
      if (typeof d.message === 'string' && d.message) return d.message;
      if (typeof d.detail === 'string' && d.detail) return d.detail;
      var keys = Object.keys(d);
      for (var i = 0; i < keys.length; i++) {
        if (keys[i] === 'status') continue;
        var first = d[keys[i]];
        if (Array.isArray(first) && first.length) return first[0];
        if (typeof first === 'string') return first;
      }
    }
    return 'No fue posible completar la petición. Verifica tu conexión.';
  }

  function openModal(id) {
    var m = $(id);
    if (!m) return;
    m.classList.remove('hidden');
    m.classList.add('flex');
    document.body.style.overflow = 'hidden';
  }

  function closeModal(id) {
    var m = $(id);
    if (!m) return;
    m.classList.add('hidden');
    m.classList.remove('flex');
    var abiertos = document.querySelectorAll('.fixed.inset-0:not(.hidden)');
    if (!abiertos.length) document.body.style.overflow = '';
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

  function setMsg(sel, text, type) {
    var el = $(sel);
    if (!el) return;
    if (!text) {
      el.classList.add('hidden');
      el.textContent = '';
      return;
    }
    el.textContent = text;
    el.classList.remove(
      'hidden', 'text-red-700', 'bg-red-50', 'border', 'border-red-200',
      'text-emerald-700', 'bg-emerald-50', 'border-emerald-200'
    );
    if (type === 'success') {
      el.classList.add('text-emerald-700', 'bg-emerald-50', 'border', 'border-emerald-200');
    } else {
      el.classList.add('text-red-700', 'bg-red-50', 'border', 'border-red-200');
    }
  }

  /* ---------- Solicitar servicio / reparación ---------- */
  function abrirSolicitud(servicio, equipo) {
    var token = localStorage.getItem('refri_access');
    if (!token) {
      $('#requiereCuentaMsg').textContent =
        'Para solicitar este servicio necesitas una cuenta. Regístrate o inicia sesión para continuar.';
      openModal('#modal-requiere-cuenta');
      return;
    }
    $('#solTipo').value = equipo || '';
    $('#solDescripcion').value = '';
    $('#solFecha').value = '';
    $('#solPrioridad').value = 'media';
    setMsg('#solMsg', '', '');
    $('#solForm').classList.remove('hidden');
    $('#solDone').classList.add('hidden');
    var titulo = $('#solTitulo');
    if (titulo) titulo.textContent = servicio === 'reparacion'
      ? 'Solicitar reparación' : 'Solicitar servicio de mantenimiento';
    openModal('#modal-solicitud');
  }

  var btns = document.querySelectorAll('.solicitar-btn');
  for (var i = 0; i < btns.length; i++) {
    btns[i].addEventListener('click', function () {
      abrirSolicitud(
        this.getAttribute('data-servicio') || 'mantenimiento',
        this.getAttribute('data-equipo') || ''
      );
    });
  }

  var btnRegistrar = $('#requiereRegistrarme');
  if (btnRegistrar) {
    btnRegistrar.addEventListener('click', function () {
      closeModal('#modal-requiere-cuenta');
      openModal('#modal-register');
    });
  }
  var btnIniciar = $('#requiereIniciar');
  if (btnIniciar) {
    btnIniciar.addEventListener('click', function () {
      closeModal('#modal-requiere-cuenta');
      openModal('#modal-login');
    });
  }

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    closeModal('#modal-requiere-cuenta');
    closeModal('#modal-solicitud');
  });

  /* ---------- Envío del formulario de solicitud ---------- */
  var solForm = $('#solForm');
  if (solForm) {
    solForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var tipo = $('#solTipo').value.trim();
      var descripcion = $('#solDescripcion').value.trim();
      var prioridad = $('#solPrioridad').value;
      var fecha = $('#solFecha').value;
      if (!tipo) {
        setMsg('#solMsg', 'Indica el tipo de equipo o el servicio que necesitas.', 'error');
        return;
      }
      setMsg('#solMsg', '', '');
      var btn = $('#solBtn');
      setBusy(btn, true);
      api('/api/clientes/')
        .then(function (data) {
          var lista = data && data.results ? data.results : data;
          var clienteId = Array.isArray(lista) && lista.length ? lista[0].id : null;
          if (!clienteId) {
            throw new Error('No encontramos un perfil de cliente asociado a tu cuenta.');
          }
          var payload = {
            cliente: clienteId,
            tipo_equipo_solicitado: tipo,
            descripcion: descripcion,
            prioridad: prioridad,
          };
          if (fecha) payload.fecha_deseada = fecha;
          return api('/api/solicitudes/', { method: 'POST', body: JSON.stringify(payload) });
        })
        .then(function () {
          $('#solForm').classList.add('hidden');
          $('#solDone').classList.remove('hidden');
        })
        .catch(function (err) {
          setMsg('#solMsg', apiErrorMessage(err), 'error');
        })
        .then(function () { setBusy(btn, false); });
    });
  }
})();
