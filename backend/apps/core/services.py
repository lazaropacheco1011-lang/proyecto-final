"""Servicios compartidos del núcleo."""
from django.contrib.contenttypes.models import ContentType
from django.db.models.deletion import ProtectedError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.models import AuditLog


def register_audit(user, action, instance=None, changes=None, model_name=None,
                   object_id=None, object_repr='', ip_address=None):
    """Registra una acción importante en el log de auditoría."""
    try:
        AuditLog.objects.create(
            user=user if user and user.is_authenticated else None,
            action=action,
            model_name=model_name or (instance._meta.label if instance else ''),
            object_id=object_id if object_id is not None else (instance.pk if instance else None),
            object_repr=object_repr or (str(instance) if instance else ''),
            changes=changes or {},
            ip_address=ip_address,
        )
    except Exception:
        # La auditoría nunca debe interrumpir la operación principal.
        pass


def log_state_change(user, instance, previous, new, comment=''):
    """Registra en auditoría un cambio de estado."""
    register_audit(
        user=user,
        action=AuditLog.Action.STATE_CHANGE,
        instance=instance,
        changes={
            'estado_anterior': previous,
            'estado_nuevo': new,
            'comentario': comment,
        },
    )


def response_error(message, http_status=status.HTTP_400_BAD_REQUEST):
    return Response({'detail': message}, status=http_status)


def content_type_for(model):
    return ContentType.objects.get_for_model(model)


def reject_if(condition, message):
    """Impide la eliminación si el registro tiene datos relacionados a conservar."""
    if condition:
        raise ValidationError(message)


def delete_or_conflict(instance, message='No se puede eliminar este registro porque '
                                          'tiene información relacionada que debe conservarse.'):
    """Elimina la instancia de la base de datos.

    Si una restricción de integridad (ForeignKey PROTECT) lo impide, devuelve
    un error claro en lugar de un 500.
    """
    try:
        instance.delete()
    except ProtectedError:
        raise ValidationError(message)
