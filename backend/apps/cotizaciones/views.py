from rest_framework import viewsets

from apps.core.permissions import CLIENTE, has_role, is_admin
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
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
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
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo el administrador puede eliminar cotizaciones (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='cotizaciones.cotizacion')
        instance.delete()
