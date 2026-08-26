/* ==========================================================================
   RefriMaster — Carrito de compra compartido (localStorage)
   - Estructura: [{ id, nombre, imagen, precio, stock, cantidad }]
   - Funciones globales expuestas: Cart (leer), addToCart, setCartQty,
     removeFromCart, clearCart, cartCount, cartSubtotal, renderCartBadges.
   ========================================================================== */
(function () {
  'use strict';

  var KEY = 'refri_cart';
  var STAFF_ROLES = ['administrador', 'supervisor', 'tecnico', 'almacen'];

  function isStaff() {
    try {
      var u = JSON.parse(localStorage.getItem('refri_user'));
      return u && STAFF_ROLES.indexOf(u.role) >= 0;
    } catch (e) { return false; }
  }

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      var arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (e) {
      return [];
    }
  }

  function write(items) {
    try {
      localStorage.setItem(KEY, JSON.stringify(items));
    } catch (e) { /* almacenamiento no disponible */ }
  }

  window.Cart = {
    items: function () { return read(); },

    add: function (producto, cantidad) {
      if (isStaff()) return read();
      var items = read();
      var qty = Math.max(1, parseInt(cantidad, 10) || 1);
      var found = false;
      items = items.map(function (it) {
        if (it.id === producto.id) {
          found = true;
          return {
            id: it.id, nombre: it.nombre, imagen: it.imagen,
            precio: it.precio, stock: producto.stock != null ? producto.stock : it.stock,
            cantidad: Math.min(it.cantidad + qty, it.stock || 999),
          };
        }
        return it;
      });
      if (!found) {
        items.push({
          id: producto.id,
          nombre: producto.nombre,
          imagen: producto.imagen || '',
          precio: producto.precio,
          stock: producto.stock != null ? producto.stock : 999,
          cantidad: Math.min(qty, producto.stock != null ? producto.stock : 999),
        });
      }
      write(items);
      renderCartBadges();
      return items;
    },

    setQty: function (id, qty) {
      var items = read().map(function (it) {
        if (it.id === id) {
          var n = parseInt(qty, 10);
          if (isNaN(n) || n <= 0) return null;
          return { id: it.id, nombre: it.nombre, imagen: it.imagen, precio: it.precio, stock: it.stock, cantidad: Math.min(n, it.stock || 999) };
        }
        return it;
      }).filter(Boolean);
      write(items);
      renderCartBadges();
      return items;
    },

    remove: function (id) {
      var items = read().filter(function (it) { return it.id !== id; });
      write(items);
      renderCartBadges();
      return items;
    },

    clear: function () {
      write([]);
      renderCartBadges();
    },

    count: function () {
      return read().reduce(function (n, it) { return n + it.cantidad; }, 0);
    },

    subtotal: function () {
      return read().reduce(function (n, it) {
        return n + (parseFloat(it.precio) || 0) * it.cantidad;
      }, 0);
    },
  };

  function renderCartBadges() {
    var count = window.Cart.count();
    $$('.cart-badge').forEach(function (el) {
      el.textContent = count;
      el.classList.toggle('hidden', count <= 0);
    });
  }

  window.cartCount = function () { return window.Cart.count(); };
  window.cartSubtotal = function () { return window.Cart.subtotal(); };
  window.renderCartBadges = renderCartBadges;

  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  document.addEventListener('DOMContentLoaded', function () {
    renderCartBadges();
    if (isStaff()) {
      var nav = document.querySelector('nav');
      if (nav) {
        $$('a[href="/carrito/"]', nav).forEach(function (el) {
          el.style.display = 'none';
        });
      }
    }
  });
})();
