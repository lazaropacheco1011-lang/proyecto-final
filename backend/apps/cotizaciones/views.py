from rest_framework import viewsets

from apps.core.permissions import CLIENTE, TECNICO, get_supervisor_tecnico_ids, has_role, is_admin, is_supervisor
from apps.core.services import register_audit
from apps.cotizaciones.models import Cotizacion
from apps.cotizaciones.serializers import CotizacionSerializer


class CotizacionViewSet(viewsets.ModelViewSet):
    """Cotizaciones de instalación (RF-17)."""
    queryset = Cotizacion.objects.prefetch_related('detalles').select_related(
        'cliente', 'tecnico', 'solicitud'
    ).all()
    serializer_class = CotizacionSerializer
    filterset_fields = ['estado', 'cliente', 'tecnico', 'solicitud', 'fecha']
    search_fields = ['numero', 'notas', 'cliente__nombre', 'cliente__apellidos']
    ordering_fields = ['fecha', 'total', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, TECNICO):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Los técnicos no tienen acceso a cotizaciones.')
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(tecnico__user_id__in=tecnicos_ids)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='cotizaciones.cotizacion')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(
            self.request.user, 'actualizar', obj,
            model_name='cotizaciones.cotizacion',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied
        user = self.request.user
        if has_role(user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden eliminar cotizaciones.')
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if not instance.tecnico or instance.tecnico.user_id not in tecnicos_ids:
                raise PermissionDenied('Solo puedes eliminar cotizaciones asignadas a tus técnicos.')
        elif not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar cotizaciones (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='cotizaciones.cotizacion')
        instance.delete()
