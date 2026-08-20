from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import CLIENTE, TECNICO, get_supervisor_tecnico_ids, has_role, is_admin, is_supervisor
from apps.core.services import register_audit
from apps.mantenimientos.models import Mantenimiento
from apps.mantenimientos.serializers import MantenimientoSerializer
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import notify_user


class MantenimientoViewSet(viewsets.ModelViewSet):
    """Mantenimientos preventivos y correctivos."""
    queryset = Mantenimiento.objects.select_related('equipo', 'cliente', 'tecnico').all()
    serializer_class = MantenimientoSerializer
    filterset_fields = ['tipo', 'estado', 'equipo', 'cliente', 'tecnico', 'fecha', 'proxima_fecha']
    search_fields = [
        'equipo__marca', 'equipo__modelo', 'equipo__numero_serie',
        'cliente__nombre', 'descripcion', 'trabajo_realizado',
    ]
    ordering_fields = ['fecha', 'proxima_fecha', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(tecnico__user_id__in=tecnicos_ids)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if has_role(user, TECNICO):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Los técnicos no pueden crear mantenimientos.')
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='mantenimientos.mantenimiento')
        self._notificar(obj, 'creado')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(
            self.request.user, 'actualizar', obj,
            model_name='mantenimientos.mantenimiento',
            changes=serializer.validated_data,
        )
        self._notificar(obj, 'actualizado')

    def perform_destroy(self, instance):
        user = self.request.user
        if has_role(user, TECNICO):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Los técnicos no pueden eliminar mantenimientos.')
        if is_supervisor(user):
            from rest_framework.exceptions import PermissionDenied
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if not instance.tecnico or instance.tecnico.user_id not in tecnicos_ids:
                raise PermissionDenied('Solo puedes eliminar mantenimientos asignados a tus técnicos.')
        elif not is_admin(user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo el administrador puede eliminar mantenimientos (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='mantenimientos.mantenimiento')
        instance.delete()

    def _notificar(self, mantenimiento, accion):
        if mantenimiento.cliente and mantenimiento.cliente.user:
            notify_user(
                mantenimiento.cliente.user,
                Notificacion.Tipo.MANTENIMIENTO,
                f'Mantenimiento {accion}',
                f'El mantenimiento {mantenimiento.get_tipo_display().lower()} de '
                f'{mantenimiento.equipo} fue {accion}. Próxima fecha: '
                f'{mantenimiento.proxima_fecha or "por definir"}.',
            )
        if mantenimiento.tecnico:
            notify_user(
                mantenimiento.tecnico.user,
                Notificacion.Tipo.MANTENIMIENTO,
                'Mantenimiento asignado',
                f'Se te asignó el mantenimiento de {mantenimiento.equipo} '
                f'para el {mantenimiento.fecha}.',
            )

    @action(detail=False, methods=['get'])
    def proximos(self, request):
        """Mantenimientos con próxima fecha dentro de los próximos 30 días."""
        hoy = timezone.localdate()
        limite = hoy + timedelta(days=30)
        qs = self.get_queryset().filter(
            proxima_fecha__range=(hoy, limite),
            estado__in=['pendiente', 'en_proceso'],
        ).order_by('proxima_fecha')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def vencidos(self, request):
        """Mantenimientos pendientes cuya próxima fecha ya venció."""
        hoy = timezone.localdate()
        qs = self.get_queryset().filter(
            proxima_fecha__lt=hoy,
            estado__in=['pendiente', 'en_proceso'],
        ).order_by('proxima_fecha')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def historial(self, request):
        """Historial completo de mantenimientos (filtrable por equipo/cliente)."""
        qs = self.get_queryset()
        return Response(self.get_serializer(qs, many=True).data)
