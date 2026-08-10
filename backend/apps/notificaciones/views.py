from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import has_role
from apps.notificaciones.models import Notificacion
from apps.notificaciones.serializers import NotificacionSerializer


class NotificacionViewSet(viewsets.ReadOnlyModelViewSet):
    """Notificaciones del usuario autenticado (RF-24)."""
    serializer_class = NotificacionSerializer
    filterset_fields = ['tipo', 'leida']
    search_fields = ['titulo', 'mensaje']
    ordering_fields = ['fecha']

    def get_queryset(self):
        return Notificacion.objects.filter(usuario=self.request.user).select_related('usuario')

    @action(detail=False, methods=['post'])
    def marcar_todas_leidas(self, request):
        self.get_queryset().update(leida=True)
        return Response({'message': 'Notificaciones marcadas como leídas.'})

    @action(detail=True, methods=['post'])
    def marcar_leida(self, request, pk=None):
        notificacion = self.get_object()
        notificacion.leida = True
        notificacion.save(update_fields=['leida'])
        return Response(self.get_serializer(notificacion).data)

    @action(detail=False, methods=['get'])
    def no_leidas(self, request):
        qs = self.get_queryset().filter(leida=False)
        return Response({'count': qs.count()})
