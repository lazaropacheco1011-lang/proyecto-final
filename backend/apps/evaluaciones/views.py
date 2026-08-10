from rest_framework import viewsets

from apps.core.permissions import CLIENTE, has_role
from apps.core.services import register_audit
from apps.evaluaciones.models import EvaluacionServicio
from apps.evaluaciones.serializers import EvaluacionServicioSerializer


class EvaluacionServicioViewSet(viewsets.ModelViewSet):
    """Evaluaciones de satisfacción del cliente (RF-25, RN-10)."""
    queryset = EvaluacionServicio.objects.select_related('cliente', 'orden', 'instalacion').all()
    serializer_class = EvaluacionServicioSerializer
    filterset_fields = ['cliente', 'orden', 'instalacion', 'calificacion']
    search_fields = ['comentario', 'cliente__nombre']
    ordering_fields = ['fecha', 'calificacion']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        return qs

    def perform_create(self, serializer):
        eval_ = serializer.save()
        register_audit(self.request.user, 'crear', eval_, model_name='evaluaciones.evaluacionservicio')

    def perform_update(self, serializer):
        eval_ = serializer.save()
        register_audit(self.request.user, 'actualizar', eval_, model_name='evaluaciones.evaluacionservicio')

    def perform_destroy(self, instance):
        from apps.core.permissions import is_admin
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo el administrador puede eliminar evaluaciones (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='evaluaciones.evaluacionservicio')
        instance.delete()
