"""Almacenamiento de imágenes en Supabase Storage.

``SupabaseStorage`` es un backend parametrizable por bucket. Se usa en dos
lugares, cada uno con su bucket y sin compartir estado:

- ``accounts.User.photo`` -> bucket ``fotos-perfil`` (``SupabaseStorage()``).
- ``apps.almacen.views.ProductoImagenUploadView`` -> bucket ``productos``
  (``get_productos_storage()``).

El resto del proyecto (evidencias, firmas y ``default_storage``) sigue usando
``FileSystemStorage`` con ``MEDIA_ROOT``/``MEDIA_URL``; aquí no se cambia
ningún almacenamiento global.

Comportamiento:
- Si faltan ``SUPABASE_URL`` o ``SUPABASE_SECRET_KEY`` se degrada a
  ``FileSystemStorage`` local (desarrollo), conservando el comportamiento previo.
- Bucket: ``fotos-perfil``. Las llaves del bucket son exactamente el nombre
  guardado en ``accounts_user.photo`` (p. ej. ``fotos_perfil/<uuid>_<archivo>``).
- REEMPLAZO SEGURO: el orden "primero se sube la nueva, luego se borra la
  anterior" NO depende de estado guardado en el storage; lo garantiza la vista
  ``MeView.foto`` (sube la nueva y recién después llama a ``delete``). Aquí no
  se conserva estado entre llamadas (un hilo/gunicorn se reutiliza entre
  peticiones, por lo que un estado por hilo podría borrar la foto de otro
  usuario en una petición posterior).
- ``delete()`` es best-effort: si Supabase no borra (objeto inexistente o error
  de red) se registra por logging sin romper la operación del usuario.
- Los fallos de subida NUNCA son silenciosos: se lanzan ``SupabaseStorageError``.
"""
import logging
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.deconstruct import deconstructible

logger = logging.getLogger(__name__)

BUCKET = 'fotos-perfil'
# Bucket de las imágenes de producto subidas desde el panel.
BUCKET_PRODUCTOS = 'productos'
DEFAULT_TIMEOUT = 15
# Columna accounts_user.photo (ImageField sin max_length propio): varchar(100).
COLUMN_MAX_LENGTH = 100
# Suelo del presupuesto de nombre: siempre debe caber "productos/" + uuid + ext.
MIN_NAME_MAX_LENGTH = 64
# Pasadas de ajuste del nombre y suelo al recortar el nombre base.
_MAX_LENGTH_PASSES = 12
_MIN_NAME_BUDGET = 48
# Columna almacen_producto.imagen (CharField max_length=300).
COLUMN_MAX_LENGTH_PRODUCTOS = 300
_SUPABASE_URL_ENV = 'SUPABASE_URL'
_SUPABASE_SECRET_ENV = 'SUPABASE_SECRET_KEY'


def _adjust_name_length(name, max_length):
    """Ajusta un nombre de objeto para que no supere ``max_length``.

    Conserva el directorio (``fotos_perfil/``), el uuid único al inicio del
    nombre base y la extensión original (``.jpg``, ``.jpeg``, ``.png``, etc.).
    Solo se recorta el nombre base cuando es estrictamente necesario.
    """
    name = str(name).replace('\\', '/')
    if len(name) <= max_length:
        return name
    dirname, _, filename = name.rpartition('/')
    stem, dot, ext = filename.rpartition('.')
    if not dot:
        stem = filename
        dot, ext = '', ''
    prefix = ''
    rest = stem
    if len(stem) > 32 and stem[32] == '_':
        prefix = stem[:33]
        rest = stem[33:]
    budget = max_length - len(dirname) - 1 - len(prefix) - len(dot) - len(ext)
    if budget < 0:
        budget = 0
    return (dirname + '/' if dirname else '') + prefix + rest[:budget] + dot + ext


def _auth_headers(secret):
    """Headers de autenticación compatibles con Supabase Storage.

    Las claves nuevas de Supabase (formato ``sb_secret_...``) se envían en el
    header ``apikey``. Las claves JWT heredadas (``eyJ...``) se envían como
    ``Authorization: Bearer <jwt>``. Se incluye ``apikey`` siempre y además
    ``Authorization`` solo si la clave parece un JWT, para soportar ambos
    formatos sin romper la degradación a FileSystemStorage.
    """
    headers = {'apikey': secret}
    if secret.startswith('eyJ'):
        headers['Authorization'] = 'Bearer {}'.format(secret)
    return headers


class SupabaseStorageError(RuntimeError):
    """Error al operar con Supabase Storage.

    ``status`` conserva el codigo HTTP que devolvio Supabase (``None`` si el
    fallo fue de red o inesperado) para que la vista pueda informar la causa
    real en lugar de un mensaje generico.
    """

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


@deconstructible
class SupabaseStorage(Storage):
    """Storage para el bucket ``fotos-perfil`` de Supabase (fotos de perfil)."""

    def __init__(self, bucket=None, timeout=None, column_max_length=None, store_url=False):
        self.bucket = bucket or BUCKET
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
        self.column_max_length = (
            column_max_length if column_max_length is not None else COLUMN_MAX_LENGTH
        )
        # True cuando lo que se guarda en la columna es la URL publica y no el
        # nombre del objeto (almacen_producto.imagen). Es lo que obliga a medir
        # la URL ya percent-codificada, y no el nombre crudo.
        self.store_url = bool(store_url)
        if self._config() is None:
            # Degradación a almacenamiento local (dev): mismo MEDIA_ROOT/MEDIA_URL.
            self._local_fs = FileSystemStorage(
                location=settings.MEDIA_ROOT,
                base_url=settings.MEDIA_URL,
            )
        else:
            self._local_fs = None

    # ------------------------------------------------------------------ #
    # Configuración
    # ------------------------------------------------------------------ #
    def _config(self):
        base = os.environ.get(_SUPABASE_URL_ENV, '').strip().rstrip('/')
        secret = os.environ.get(_SUPABASE_SECRET_ENV, '').strip()
        if not base or not secret:
            return None
        return base, secret

    @staticmethod
    def _norm(name):
        # Normaliza separadores (en Windows os.path puede devolver '\\').
        return str(name).replace('\\', '/')

    def _endpoint(self, kind, name):
        base, _ = self._config()
        return '{}/storage/v1/object/{}/{}/{}'.format(
            base,
            kind,
            self.bucket,
            urllib.parse.quote(self._norm(name), safe='/'),
        )

    # ------------------------------------------------------------------ #
    # API de Django
    # ------------------------------------------------------------------ #
    def _open(self, name, mode='rb'):
        raise SupabaseStorageError(
            'SupabaseStorage no soporta lectura directa de archivos; '
            'usa storage.url() para obtener la URL pública.'
        )

    def _save(self, name, content):
        if self._local_fs is not None:
            return self._local_fs.save(name, content)

        base, secret = self._config()
        name = self._norm(name)
        content.seek(0)
        data = content.read()
        content_type = (
            getattr(content, 'content_type', None)
            or mimetypes.guess_type(name)[0]
            or 'application/octet-stream'
        )
        url = '{}/storage/v1/object/{}/{}'.format(
            base, self.bucket, urllib.parse.quote(name, safe='/'),
        )
        request = urllib.request.Request(url, data=data, method='POST', headers={
            **_auth_headers(secret),
            'Content-Type': content_type,
            'x-upsert': 'true',
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, 'status', 200)
                if status >= 400:
                    raise SupabaseStorageError(
                        'Supabase respondió {} al subir la foto.'.format(status)
                    )
        except urllib.error.HTTPError as exc:
            raise SupabaseStorageError(
                'Supabase respondió {} al subir la foto ({}).'.format(
                    exc.code,
                    getattr(exc, 'reason', exc),
                ),
                status=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise SupabaseStorageError(
                'No se pudo conectar con Supabase al subir la foto ({}).'.format(exc.reason)
            ) from exc
        except Exception as exc:
            raise SupabaseStorageError(
                'No se pudo subir la foto a Supabase ({}: {}).'.format(
                    type(exc).__name__, exc
                )
            ) from exc
        return name

    def delete(self, name):
        """Borra el objeto del bucket. Best-effort: no lanza al llamador.

        Solo debe invocarse cuando la foto nueva ya se subió correctamente
        (reemplazo) o cuando se elimina la foto a propósito. Los errores se
        registran por logging para no romper la operación del usuario.
        """
        if not name:
            return
        if self._local_fs is not None:
            self._local_fs.delete(name)
            return
        try:
            self._remove(name)
        except SupabaseStorageError as exc:
            logger.warning('Foto no eliminada en Supabase (%s): %s', name, exc)

    def exists(self, name):
        if not name:
            return False
        if self._local_fs is not None:
            return self._local_fs.exists(name)
        url = self._endpoint('public', name)
        _, secret = self._config()
        request = urllib.request.Request(url, method='HEAD', headers=_auth_headers(secret))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return getattr(response, 'status', 200) < 400
        except urllib.error.HTTPError as exc:
            return 100 <= exc.code < 400
        except Exception:
            return False

    def url(self, name):
        if not name:
            return ''
        if self._local_fs is not None:
            return self._local_fs.url(name)
        return self._endpoint('public', name)

    def _stored_value(self, name):
        """Valor que realmente queda escrito en la columna de la base de datos."""
        if self.store_url:
            return self.url(name)
        return name

    def get_available_name(self, name, max_length=None):
        # accounts_user.photo es varchar(100) (ImageField sin max_length propio)
        # y almacen_producto.imagen es varchar(300): el limite por defecto
        # depende del campo, y el cropping conserva el directorio, el
        # uuid (único) y la extensión.
        limite = max_length if max_length is not None else self.column_max_length
        name = self._norm(name)
        if self._local_fs is not None:
            return self._local_fs.get_available_name(name, max_length=limite)
        name = _adjust_name_length(name, limite)
        # Si lo que se guarda es la URL, el nombre debe recortarse contra la
        # longitud de la URL ya percent-codificada: un espacio, por ejemplo,
        # ocupa 3 caracteres como %20. Sin este ajuste, un nombre con espacios
        #largos desbordaría la columna pese a caber en el recorte inicial.
        for _ in range(_MAX_LENGTH_PASSES):
            valor = self._stored_value(name)
            if len(valor) <= limite:
                break
            siguiente = _adjust_name_length(
                name, max(_MIN_NAME_BUDGET, len(name) - (len(valor) - limite)),
            )
            if siguiente == name:
                break
            name = siguiente
        # El nombre ya incluye uuid (único) y la subida usa x-upsert: devolverlo
        # tal cual evita llamadas HEAD adicionales por cada subida.
        return name

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    def _remove(self, name):
        """Borrado real en Supabase. Eleva SupabaseStorageError si falla."""
        if not name:
            return
        base, secret = self._config()
        name = self._norm(name)
        url = '{}/storage/v1/object/{}/{}'.format(
            base, self.bucket, urllib.parse.quote(name, safe='/'),
        )
        request = urllib.request.Request(url, method='DELETE', headers=_auth_headers(secret))
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = getattr(response, 'status', 200)
                if status >= 400:
                    raise SupabaseStorageError(
                        'Supabase respondió {} al borrar la foto.'.format(status)
                    )
        except urllib.error.HTTPError as exc:
            # Un objeto que ya no existe no es un error.
            if exc.code in (400, 404):
                return
            raise SupabaseStorageError(
                'Supabase respondió {} al borrar la foto.'.format(exc.code)
            ) from exc
        except urllib.error.URLError as exc:
            raise SupabaseStorageError(
                'No se pudo conectar con Supabase al borrar la foto ({}).'.format(exc.reason)
            ) from exc
        except Exception as exc:
            raise SupabaseStorageError(
                'No se pudo borrar la foto en Supabase ({}: {}).'.format(
                    type(exc).__name__, exc
                )
            ) from exc


# --------------------------------------------------------------------------- #
# Instancias por bucket
# --------------------------------------------------------------------------- #
def get_fotos_perfil_storage():
    """Storage del bucket ``fotos-perfil`` (campo ``accounts.User.photo``).

    Se crea por llamada (y no como constante de módulo) para que la degradación a
    ``FileSystemStorage`` se evalúe con el entorno ya carregado, igual que hace
    ``StorageField`` al deconstructar el storage.
    """
    return SupabaseStorage(bucket=BUCKET)


def get_productos_storage():
    """Storage del bucket ``productos`` (imágenes de productos del panel).

    Instancia de storage que escribe en el bucket ``productos``; la usa
    ``ProductoImagenUploadView`` para guardar las imágenes subidas desde el
    panel.

    A diferencia de ``photo``, lo que se guarda en ``almacen_producto.imagen``
    (varchar 300) es la URL absoluta y no el nombre del objeto: por eso
    ``store_url=True`` hace que el recorte del nombre mida la URL pública ya
    percent-codificada, y no el nombre crudo.
    """
    return SupabaseStorage(
        bucket=BUCKET_PRODUCTOS,
        column_max_length=COLUMN_MAX_LENGTH_PRODUCTOS,
        store_url=True,
    )