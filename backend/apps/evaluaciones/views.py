from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from apps.core.permissions import CLIENTE, TECNICO, get_supervisor_tecnico_ids, has_role, is_admin, is_supervisor
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
        if has_role(user, TECNICO):
            return qs.none()
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(orden__tecnico__user_id__in=tecnicos_ids)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        if has_role(self.request.user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden crear evaluaciones.')
        eval_ = serializer.save()
        register_audit(self.request.user, 'crear', eval_, model_name='evaluaciones.evaluacionservicio')

    def perform_update(self, serializer):
        if has_role(self.request.user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden modificar evaluaciones.')
        eval_ = serializer.save()
        register_audit(self.request.user, 'actualizar', eval_, model_name='evaluaciones.evaluacionservicio')

    def perform_destroy(self, instance):
        user = self.request.user
        if has_role(user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden eliminar evaluaciones.')
        if has_role(user, CLIENTE):
            raise PermissionDenied('Los clientes no pueden eliminar evaluaciones.')
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if instance.orden and instance.orden.tecnico and instance.orden.tecnico.user_id in tecnicos_ids:
                pass
            else:
                raise PermissionDenied('Solo puedes eliminar evaluaciones de tus técnicos.')
        elif not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar evaluaciones (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='evaluaciones.evaluacionservicio')
        instance.delete()
