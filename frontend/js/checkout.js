/* ==========================================================================
   RefriMaster — Checkout: datos de entrega + pago (tarjeta / PayPal / billetera)
   ========================================================================== */
(function () {
  'use strict';

  var API_BASE = new URLSearchParams(location.search).get('api') ||
                 window.REFRI_API ||
                 'http://127.0.0.1:8000';

  var ENVIO = { costo: 25000, gratis_desde: 500000 };
  var estado = { metodo: 'tarjeta' };

  function getToken() {
    try { return localStorage.getItem('refri_access') || ''; } catch (e) { return ''; }
  }

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

  function setMsg(text, type) {
    var el = $('#payMsg');
    if (!text) {
      el.classList.add('hidden');
      el.textContent = '';
      return;
    }
    el.textContent = text;
    el.classList.remove('hidden', 'text-red-700', 'bg-red-50', 'text-emerald-700', 'bg-emerald-50');
    if (type === 'success') {
      el.classList.add('text-emerald-700', 'bg-emerald-50');
    } else {
      el.classList.add('text-red-700', 'bg-red-50');
    }
  }

  function setBusy(busy) {
    var btn = $('#coSubmit');
    if (busy) {
      btn.dataset.label = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="material-symbols-outlined animate-spin">progress_activity</span> Procesando…';
    } else {
      btn.disabled = false;
      if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
    }
  }

  function envioCosto(subtotal) {
    return subtotal >= ENVIO.gratis_desde ? 0 : ENVIO.costo;
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

  function renderSummary() {
    var items = window.Cart.items();
    var subtotal = window.Cart.subtotal();
    var envio = envioCosto(subtotal);
    var total = subtotal + envio;

    $('#coItems').innerHTML = items.map(function (it) {
      return '<div class="flex items-center gap-3">' +
        '<div class="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-surface-container">' +
          '<img src="' + esc(it.imagen) + '" alt="' + esc(it.nombre) + '" class="h-full w-full object-cover" loading="lazy">' +
        '</div>' +
        '<div class="min-w-0 flex-1">' +
          '<div class="truncate text-sm font-semibold text-on-surface">' + esc(it.nombre) + '</div>' +
          '<div class="text-xs text-on-surface-variant">' + it.cantidad + ' × ' + moneyDOP(it.precio) + '</div>' +
        '</div>' +
        '<div class="text-sm font-bold text-on-surface">' + moneyDOP((parseFloat(it.precio) || 0) * it.cantidad) + '</div>' +
      '</div>';
    }).join('');

    $('#coSubtotal').textContent = moneyDOP(subtotal);
    $('#coEnvio').textContent = envio === 0 ? 'Gratis' : moneyDOP(envio);
    $('#coTotal').textContent = moneyDOP(total);
    $('#coFreeShip').classList.toggle('hidden', envio !== 0);
  }

  function switchMetodo(metodo) {
    estado.metodo = metodo;
    $('#cardBox').classList.toggle('hidden', metodo !== 'tarjeta');
    $('#paypalBox').classList.toggle('hidden', metodo !== 'paypal');
    $('#walletBox').classList.toggle('hidden', metodo !== 'billetera');
    setMsg('', '');
    var label = metodo === 'tarjeta' ? 'Pagar ahora'
      : metodo === 'paypal' ? 'Pagar con PayPal' : 'Registrar pedido';
    var btn = $('#coSubmit');
    var icon = metodo === 'tarjeta' ? 'lock' : metodo === 'paypal' ? 'account_balance_wallet' : 'phone_iphone';
    btn.innerHTML = '<span class="material-symbols-outlined">' + icon + '</span> ' + label;
  }

  $$('input[name="metodo"]').forEach(function (r) {
    r.addEventListener('change', function () { switchMetodo(r.value); });
  });

  /* ---------- Formato y validación de tarjeta ---------- */
  function soloDigitos(value) { return String(value).replace(/\D/g, ''); }

  function luhnValid(num) {
    var n = soloDigitos(num);
    if (n.length < 13 || n.length > 19) return false;
    var suma = 0, doblar = false;
    for (var i = n.length - 1; i >= 0; i--) {
      var d = parseInt(n[i], 10);
      if (doblar) { d *= 2; if (d > 9) d -= 9; }
      suma += d;
      doblar = !doblar;
    }
    return suma % 10 === 0;
  }

  $('#coCardNumber').addEventListener('input', function () {
    var digits = soloDigitos(this.value).slice(0, 16);
    this.value = digits.replace(/(.{4})/g, '$1 ').trim();
  });

  $('#coCardExp').addEventListener('input', function () {
    var digits = soloDigitos(this.value).slice(0, 4);
    if (digits.length > 2) digits = digits.slice(0, 2) + '/' + digits.slice(2);
    this.value = digits;
  });

  function validarTarjeta() {
    var numero = soloDigitos($('#coCardNumber').value);
    var nombre = $('#coCardName').value.trim();
    var exp = $('#coCardExp').value.trim();
    var cvv = $('#coCardCvv').value.trim();
    if (!luhnValid(numero)) return 'El número de tarjeta no es válido.';
    if (!nombre) return 'Ingresa el nombre del titular de la tarjeta.';
    var m = exp.match(/^(\d{2})\/(\d{2})$/);
    if (!m) return 'La fecha de vencimiento debe tener el formato MM/AA.';
    var mes = parseInt(m[1], 10), anio = parseInt(m[2], 10);
    if (mes < 1 || mes > 12) return 'El mes de vencimiento no es válido.';
    var hoy = new Date();
    var expAnio = 2000 + anio;
    if (expAnio < hoy.getFullYear() || (expAnio === hoy.getFullYear() && mes < (hoy.getMonth() + 1))) {
      return 'La tarjeta está vencida.';
    }
    if (!/^\d{3,4}$/.test(cvv)) return 'El código de seguridad (CVV) no es válido.';
    return '';
  }

  function validarDatos() {
    if (!$('#coNombre').value.trim()) return 'Ingresa tu nombre completo.';
    if (!/^\S+@\S+\.\S+$/.test($('#coEmail').value.trim())) return 'Ingresa un correo electrónico válido.';
    if (!$('#coTelefono').value.trim()) return 'Ingresa tu teléfono de contacto.';
    if (!$('#coDocumento').value.trim()) return 'Ingresa tu documento o RNC.';
    if (!$('#coProvincia').value.trim()) return 'Selecciona tu provincia.';
    if (!$('#coSector').value.trim()) return 'Ingresa tu sector.';
    if (!$('#coCiudad').value.trim()) return 'Ingresa tu ciudad.';
    if (!$('#coDireccion').value.trim()) return 'Ingresa tu dirección de entrega.';
    return '';
  }

  function payloadDatos() {
    return {
      nombre: $('#coNombre').value.trim(),
      email: $('#coEmail').value.trim(),
      telefono: $('#coTelefono').value.trim(),
      documento: $('#coDocumento').value.trim(),
      provincia: $('#coProvincia').value.trim(),
      sector: $('#coSector').value.trim(),
      ciudad: $('#coCiudad').value.trim(),
      direccion: $('#coDireccion').value.trim(),
      referencia: $('#coReferencia').value.trim(),
      notas: $('#coNotas').value.trim(),
    };
  }

  function payloadCarrito() {
    return window.Cart.items().map(function (it) {
      return { producto_id: it.id, cantidad: it.cantidad };
    });
  }

  async function api(path, options) {
    options = options || {};
    var token = getToken();
    var headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    var res = await fetch(API_BASE + path, {
      ...options,
      headers: headers,
    });
    var data = null;
    try { data = await res.json(); } catch (e) { /* cuerpo no JSON */ }
    if (!res.ok && res.status !== 402) {
      var err = new Error('API error ' + res.status);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return { status: res.status, data: data };
  }

  function apiError(err) {
    var d = err && err.data;
    if (d && typeof d.detail === 'string' && d.detail) return d.detail;
    if (d && typeof d === 'object') {
      var keys = Object.keys(d);
      for (var i = 0; i < keys.length; i++) {
        var first = d[keys[i]];
        if (Array.isArray(first) && first.length) return first[0];
      }
    }
    return 'No fue posible completar la compra. Verifica tu conexión.';
  }

  function irConfirmacion(numero) {
    window.location.href = '/checkout/exito/?orden=' + encodeURIComponent(numero);
  }

  $('#checkoutForm').addEventListener('submit', async function (e) {
    e.preventDefault();
    var errores = validarDatos();
    if (errores) { setMsg(errores, 'error'); return; }

    if (!window.Cart.items().length) {
      setMsg('Tu carrito está vacío.', 'error');
      return;
    }

    if (estado.metodo === 'tarjeta') {
      var tErr = validarTarjeta();
      if (tErr) { setMsg(tErr, 'error'); return; }
    }

    setBusy(true);
    setMsg('', '');
    try {
      var base = {
        nombre: payloadDatos().nombre,
        email: payloadDatos().email,
        telefono: payloadDatos().telefono,
        documento: payloadDatos().documento,
        provincia: payloadDatos().provincia,
        sector: payloadDatos().sector,
        ciudad: payloadDatos().ciudad,
        direccion: payloadDatos().direccion,
        referencia: payloadDatos().referencia,
        notas: payloadDatos().notas,
        items: payloadCarrito(),
      };

      if (estado.metodo === 'tarjeta') {
        var body = Object.assign({}, base, {
          tarjeta: {
            numero: soloDigitos($('#coCardNumber').value),
            nombre_titular: $('#coCardName').value.trim(),
            exp_mes: $('#coCardExp').value.split('/')[0],
            exp_anio: '20' + $('#coCardExp').value.split('/')[1],
            cvv: $('#coCardCvv').value.trim(),
          },
        });
        var res = await api('/api/tienda/pagos/tarjeta/', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        if (res.status === 201 || (res.data && res.data.aprobado)) {
          window.Cart.clear();
          irConfirmacion(res.data.orden);
        } else if (res.status === 402) {
          setMsg('Pago rechazado: ' + (res.data.mensaje || 'La tarjeta fue rechazada.') +
            ' La orden ' + res.data.orden + ' quedó registrada con estado pendiente.', 'error');
        } else {
          setMsg(res.data.detail || 'No se pudo procesar el pago.', 'error');
        }
      } else if (estado.metodo === 'paypal') {
        var pp = await api('/api/tienda/pagos/paypal/crear/', {
          method: 'POST',
          body: JSON.stringify(base),
        });
        if (pp.status === 201 && pp.data.aprobacion_url) {
          window.Cart.clear();
          window.location.href = pp.data.aprobacion_url;
        } else {
          setMsg(pp.data.detail || 'No se pudo iniciar el pago con PayPal.', 'error');
        }
      } else {
        var wal = await api('/api/tienda/pagos/billetera/', {
          method: 'POST',
          body: JSON.stringify(base),
        });
        if (wal.status === 201) {
          window.Cart.clear();
          irConfirmacion(wal.data.orden);
        } else {
          setMsg(wal.data.detail || 'No se pudo registrar el pedido.', 'error');
        }
      }
    } catch (err) {
      setMsg(apiError(err), 'error');
    } finally {
      setBusy(false);
    }
  });

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
    if (!getToken()) {
      try { localStorage.setItem('refri_checkout_return', '/checkout/'); } catch (e) { /* ok */ }
      toast('Debes iniciar sesión para continuar con la compra.', 'error');
      setTimeout(function () { window.location.href = '/'; }, 800);
      return;
    }
    await loadConfig();
    if (!window.Cart.items().length) {
      toast('Tu carrito está vacío. Agrega productos para continuar.', 'error');
      setTimeout(function () { window.location.href = '/productos/'; }, 900);
      return;
    }
    renderSummary();
    switchMetodo('tarjeta');
  })();
})();
