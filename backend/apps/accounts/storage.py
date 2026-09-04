"""Almacenamiento de fotos de perfil en Supabase Storage.

Se aplica ÚNICAMENTE al campo ``accounts.User.photo``. El resto del proyecto
(productos, evidencias, firmas y ``default_storage``) sigue usando
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
DEFAULT_TIMEOUT = 15
_SUPABASE_URL_ENV = 'SUPABASE_URL'
_SUPABASE_SECRET_ENV = 'SUPABASE_SECRET_KEY'


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
    """Error al operar con Supabase Storage."""


@deconstructible
class SupabaseStorage(Storage):
    """Storage para el bucket ``fotos-perfil`` de Supabase (fotos de perfil)."""

    def __init__(self, bucket=None, timeout=None):
        self.bucket = bucket or BUCKET
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT
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
                )
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

    def get_available_name(self, name, max_length=None):
        if self._local_fs is not None:
            return self._local_fs.get_available_name(name, max_length=max_length)
        # El nombre ya incluye uuid (único) y la subida usa x-upsert; devolverlo
        # tal cual evita una llamada HEAD por cada subida.
        if max_length is not None and len(self._norm(name)) > max_length:
            raise SupabaseStorageError(
                'El nombre del archivo excede el máximo permitido ({}).'.format(
                    max_length
                )
            )
        return self._norm(name)

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