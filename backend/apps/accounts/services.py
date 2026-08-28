"""Servicios de recuperación y cambio de contraseña."""
import hashlib
import logging
import secrets
import smtplib
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import PasswordResetToken

User = get_user_model()

logger = logging.getLogger(__name__)


class CorreoNoEnviado(Exception):
    """Se lanza cuando el envío real del correo falla (infraestructura)."""


def _hash_token(token):
    """Hash SHA-256 del token en claro (nunca se persiste el token original)."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _ttl():
    return timedelta(minutes=settings.PASSWORD_RESET_TIMEOUT_MINUTES)


def crear_token_recuperacion(user):
    """Genera y persiste un token de un solo uso. Devuelve el token en claro."""
    token = secrets.token_urlsafe(48)
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(token),
        expires_at=timezone.now() + _ttl(),
    )
    return token


def buscar_token(token):
    """Devuelve el registro de token válido (no usado, no expirado) o None."""
    if not token:
        return None
    registro = (
        PasswordResetToken.objects.filter(token_hash=_hash_token(token))
        .select_related('user')
        .first()
    )
    if registro is None or not registro.es_valido():
        return None
    return registro


def enviar_correo_recuperacion(email):
    """Envía el enlace de recuperación si el correo está registrado.

    Devuelve True si se envió. La respuesta al usuario siempre es genérica
    para no revelar si un correo está registrado (RNF).
    """
    try:
        user = User.objects.get(email__iexact=email.strip())
    except User.DoesNotExist:
        return False
    if not user.is_active:
        return False

    token = crear_token_recuperacion(user)
    enlace = '{base}/?reset={token}&correo={correo}'.format(
        base=settings.FRONTEND_URL.rstrip('/'),
        token=token,
        correo=email.strip(),
    )
    nombre = user.get_full_name() or user.username
    try:
        send_mail(
            subject='Recuperación de contraseña — RefriMaster',
            message=(
                f'Hola {nombre}:\n\n'
                'Recibimos una solicitud para restablecer la contraseña de tu cuenta '
                'en RefriMaster.\n\n'
                'Para continuar, abre el siguiente enlace (válido por '
                f'{settings.PASSWORD_RESET_TIMEOUT_MINUTES} minutos):\n\n'
                f'{enlace}\n\n'
                'Si no solicitaste este cambio, ignora este correo y tu contraseña '
                'seguirá igual.\n\n'
                'Saludos,\nEquipo RefriMaster'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except (smtplib.SMTPException, ConnectionError, TimeoutError, OSError) as exc:
        # Solo se registra el mensaje del error SMTP, sin credenciales ni token.
        logger.error('No se pudo enviar el correo de recuperación: %s', exc)
        raise CorreoNoEnviado(str(exc)) from exc
    return True


def enviar_correo_bienvenida(user):
    """Envía el correo de bienvenida tras crear una cuenta correctamente.

    Solo se ejecuta cuando el usuario ya fue creado de forma exitosa
    (el registro no debe enviarse si la creación falla). Para el rol cliente,
    confirma que su cuenta fue creada correctamente.
    """
    if not user or not user.email:
        return False
    nombre = user.get_full_name() or user.username
    send_mail(
        subject='Bienvenido a RefriMaster',
        message=(
            f'Hola {nombre}:\n\n'
            'Tu cuenta en RefriMaster fue creada correctamente. '
            'Ya puedes iniciar sesión con tu usuario y contraseña para '
            'comprar en la vitrina y consultar tus pedidos.\n\n'
            'Si tienes alguna duda, no dudes en contactarnos.\n\n'
            'Saludos,\nEquipo RefriMaster'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
    return True


def revocar_sesiones(user):
    """Invalida todos los refresh tokens activos del usuario.

    Tras cambiar o restablecer la contraseña, las sesiones anteriores quedan
    invalidadas (el access token vigente caduca en minutos).
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    for token in OutstandingToken.objects.filter(user=user):
        try:
            BlacklistedToken.objects.get_or_create(token=token)
        except OutstandingToken.DoesNotExist:
            continue
