from rest_framework import mixins, viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.core.models import AuditLog, Evidencia, FirmaDigital
from apps.core.permissions import ALMACEN, TECNICO, has_role, is_admin, is_staff_role
from apps.core.serializers import AuditLogSerializer, EvidenciaSerializer, FirmaSerializer


class StaffOnlyPermission(BasePermission):
    """Solo el personal interno (incluido técnicos) puede acceder al recurso."""
    message = 'Solo el personal interno puede acceder a este recurso.'

    def has_permission(self, request, view):
        return is_staff_role(request.user)


class StaffNoDeleteForTecnico(BasePermission):
    """Personal interno puede acceder; técnicos no pueden eliminar."""
    message = 'No tienes permisos para realizar esta acción.'

    def has_permission(self, request, view):
        if request.method == 'DELETE' and has_role(request.user, TECNICO):
            return False
        return is_staff_role(request.user)


class EvidenciaViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Sube y consulta evidencias fotográficas vinculadas a instalaciones,
    órdenes de servicio y otros registros.
    """
    queryset = Evidencia.objects.select_related('subido_por', 'content_type')
    serializer_class = EvidenciaSerializer
    permission_classes = [StaffNoDeleteForTecnico]
    filterset_fields = ['content_type', 'object_id', 'fase']
    search_fields = ['descripcion']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, TECNICO):
            return qs.filter(subido_por=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(subido_por=self.request.user)


class FirmaViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Registra y consulta firmas digitales vinculadas a instalaciones y
    órdenes de servicio (RF-20b).
    """
    queryset = FirmaDigital.objects.select_related('subido_por', 'content_type')
    serializer_class = FirmaSerializer
    permission_classes = [StaffNoDeleteForTecnico]
    filterset_fields = ['content_type', 'object_id']
    search_fields = ['nombre', 'documento', 'observaciones']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, TECNICO):
            return qs.filter(subido_por=user)
        return qs

    def perform_create(self, serializer):
        serializer.save(subido_por=self.request.user)


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Consulta de auditoría.

    - Administrador: acceso total a todos los registros.
    - Almacén: solo el historial del inventario (productos y categorías).
    - Otros roles: sin acceso.
    """
    queryset = AuditLog.objects.select_related('user').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['action', 'model_name', 'user']
    search_fields = ['object_repr', 'changes']
    ordering_fields = ['created_at']

    INVENTARIO_MODELS = ('almacen.producto', 'almacen.categoria')

    def get_queryset(self):
        user = self.request.user
        if is_admin(user):
            return super().get_queryset()
        if has_role(user, ALMACEN):
            return super().get_queryset().filter(model_name__in=self.INVENTARIO_MODELS)
        return self.queryset.none()
