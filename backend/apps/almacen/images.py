"""Resolución centralizada de rutas de imagen de productos del almacén.

El campo ``Producto.imagen`` guarda una ruta (o URL) digitada desde el panel
(admin-dashboard). Para que la Vitrina Pública y el panel usen siempre una
URL que realmente exista en el frontend, normalizamos la ruta: si el valor
guardado no apunta a un archivo real (por ejemplo, quedó guardado sin
extensión o con una extensión incorrecta), se intenta resolver agregando la
extensión de un archivo que sí existe dentro de ``/assets/img/productos/``.
"""
import os

from django.conf import settings

# Extensiones admitidas para imágenes de producto, en orden de preferencia.
IMAGE_EXTENSIONS = ('webp', 'png', 'jpg', 'jpeg', 'avif', 'gif', 'svg')


def _asset_exists(url):
    """Indica si ``url`` corresponde a un archivo real.

    Se busca tanto en el frontend (``FRONTEND_DIR``) como en ``MEDIA_ROOT``,
    ya que los productos pueden referenciar assets de ``/assets/...`` o
    imágenes subidas por el panel en ``/media/...``.
    """
    try:
        rel = url.lstrip('/')
        targets = [
            settings.FRONTEND_DIR / rel,
            settings.MEDIA_ROOT / rel,
        ]
        if rel.startswith('media/'):
            # /media/productos/foo.jpg -> MEDIA_ROOT/productos/foo.jpg
            targets.append(settings.MEDIA_ROOT / rel[len('media/'):])
        return any(
            '..' not in t.parts and t.is_file()
            for t in targets
        )
    except Exception:
        return False


def resolve_asset_url(value):
    """Devuelve una URL de asset que realmente existe en el frontend.

    - Valor vacío -> ''
    - URLs externas o data-URLs -> tal cual
    - Rutas que ya existen -> tal cual
    - Rutas sin extensión (o con extensión inexistente) -> se resuelve
      agregando la extensión de un archivo realmente presente.
    - Si no se encuentra ninguna coincidencia -> el valor original intacto.
    """
    if not value:
        return ''
    raw = str(value).strip()
    if raw.startswith(('http://', 'https://', '//', 'data:')):
        return raw
    url = raw.split('?')[0].split('#')[0].rstrip('/')
    if not url.startswith('/'):
        url = '/' + url
    if _asset_exists(url):
        return url
    base = os.path.splitext(url)[0]
    for ext in IMAGE_EXTENSIONS:
        candidate = base + '.' + ext
        if _asset_exists(candidate):
            return candidate
    return raw
