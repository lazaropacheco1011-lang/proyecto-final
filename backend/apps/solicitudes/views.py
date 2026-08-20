from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.permissions import CLIENTE, TECNICO, has_role, is_admin
from apps.core.services import register_audit
from apps.notificaciones.services import notify_solicitud_creada, notify_solicitud_estado
from apps.solicitudes.models import SolicitudInstalacion
from apps.solicitudes.serializers import SolicitudInstalacionSerializer


class IsNotTecnicoForWrite(BasePermission):
    """Bloquea técnicos en acciones de escritura."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return not has_role(request.user, TECNICO)


class SolicitudInstalacionViewSet(viewsets.ModelViewSet):
    """Solicitudes de instalación (RF-06, RF-07)."""
    queryset = SolicitudInstalacion.objects.select_related('cliente').all()
    serializer_class = SolicitudInstalacionSerializer
    filterset_fields = ['estado', 'prioridad', 'cliente', 'fecha_deseada']
    search_fields = [
        'tipo_equipo_solicitado', 'descripcion', 'cliente__nombre',
        'cliente__apellidos', 'cliente__documento_numero',
    ]
    ordering_fields = ['fecha_solicitud', 'prioridad', 'fecha_deseada']

    def get_permissions(self):
        return [perm() for perm in (IsNotTecnicoForWrite,)]

    def _staff_usuarios(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return list(User.objects.filter(role__in=['administrador', 'supervisor']))

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='solicitudes.solicitudinstalacion')
        notify_solicitud_creada(obj, self._staff_usuarios())

    def perform_update(self, serializer):
        prev_estado = serializer.instance.estado if serializer.instance else None
        obj = serializer.save()
        if prev_estado != obj.estado:
            notify_solicitud_estado(obj, obj.estado)
        register_audit(
            self.request.user, 'actualizar', obj,
            model_name='solicitudes.solicitudinstalacion',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo el administrador puede eliminar solicitudes (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='solicitudes.solicitudinstalacion')
        instance.delete()
