from decimal import Decimal

from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import (
    ADMIN,
    SUPERVISOR,
    TECNICO,
    CLIENTE,
    has_role,
    is_admin,
    is_staff_role,
)
from apps.core.services import log_state_change, register_audit
from apps.materiales.services import reponer_inventario
from apps.notificaciones.services import notify_orden_estado
from apps.servicios.models import EstadoOrdenLog, MaterialUtilizado, OrdenServicio, VisitaTecnica
from apps.servicios.serializers import (
    EstadoOrdenLogSerializer,
    MaterialUtilizadoSerializer,
    OrdenServicioSerializer,
    VisitaTecnicaSerializer,
)


class OrdenServicioViewSet(viewsets.ModelViewSet):
    """Órdenes de trabajo / servicios (RF-08, RF-09, RF-21)."""
    queryset = OrdenServicio.objects.select_related(
        'cliente', 'equipo', 'tecnico'
    ).prefetch_related('materiales_utilizados__material', 'historial', 'evidencias').annotate(
        costo_materiales=Coalesce(
            Sum('materiales_utilizados__subtotal'), Value(Decimal('0.00'))
        )
    )
    serializer_class = OrdenServicioSerializer
    filterset_fields = [
        'estado', 'tipo_servicio', 'cliente', 'equipo', 'tecnico', 'fecha',
    ]
    search_fields = [
        'numero', 'problema_reportado', 'diagnostico', 'trabajo_realizado',
        'observaciones', 'cliente__nombre', 'cliente__apellidos',
        'equipo__numero_serie', 'equipo__marca',
    ]
    ordering_fields = ['fecha', 'created_at', 'estado']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        return qs

    def perform_create(self, serializer):
        orden = serializer.save()
        EstadoOrdenLog.objects.create(
            orden=orden,
            estado_anterior='',
            estado_nuevo=orden.estado,
            usuario=self.request.user,
            comentario='Creación de la orden',
        )
        register_audit(self.request.user, 'crear', orden, model_name='servicios.ordenservicio')
        notify_orden_estado(orden, orden.estado)

    def perform_update(self, serializer):
        prev_estado = serializer.instance.estado if serializer.instance else None
        orden = serializer.save()
        if prev_estado != orden.estado:
            EstadoOrdenLog.objects.create(
                orden=orden,
                estado_anterior=prev_estado,
                estado_nuevo=orden.estado,
                usuario=self.request.user,
                comentario='Actualización de estado',
            )
            log_state_change(self.request.user, orden, prev_estado, orden.estado)
            notify_orden_estado(orden, orden.estado)
        register_audit(
            self.request.user, 'actualizar', orden, model_name='servicios.ordenservicio',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            raise PermissionDenied('Solo el administrador puede eliminar órdenes (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='servicios.ordenservicio')
        instance.delete()

    # ------------------------------------------------------------------
    # Materiales de la orden (RN-06)
    # ------------------------------------------------------------------
    @action(detail=True, methods=['get', 'post'])
    def materiales(self, request, pk=None):
        """Lista o agrega materiales utilizados en la orden (RF-15)."""
        orden = self.get_object()
        if request.method == 'GET':
            qs = orden.materiales_utilizados.select_related('material')
            serializer = MaterialUtilizadoSerializer(qs, many=True, context={'request': request})
            return Response(serializer.data)

        if not is_staff_role(request.user):
            raise PermissionDenied('Solo el personal interno puede registrar materiales.')
        data = {**request.data, 'orden': orden.id}
        serializer = MaterialUtilizadoSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            uso = serializer.save()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        register_audit(
            request.user, 'crear', uso, model_name='servicios.materialutilizado'
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        """Historial de cambios de estado de la orden (RN-09)."""
        orden = self.get_object()
        qs = orden.historial.select_related('usuario')
        serializer = EstadoOrdenLogSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado validando transiciones y reglas de negocio."""
        orden = self.get_object()
        nuevo_estado = request.data.get('estado')
        if not nuevo_estado:
            return Response(
                {'detail': 'El campo estado es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comentario = request.data.get('comentario', '')
        serializer = self.get_serializer(
            orden, data={'estado': nuevo_estado, **request.data}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        prev = orden.estado
        serializer.save()
        EstadoOrdenLog.objects.create(
            orden=orden,
            estado_anterior=prev,
            estado_nuevo=orden.estado,
            usuario=request.user,
            comentario=comentario,
        )
        log_state_change(request.user, orden, prev, orden.estado)
        notify_orden_estado(orden, orden.estado)
        return Response(self.get_serializer(orden).data)

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Órdenes pendientes de atención."""
        qs = self.get_queryset().filter(estado__in=['pendiente', 'asignada']).order_by('fecha')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class VisitaTecnicaViewSet(viewsets.ModelViewSet):
    """Visitas técnicas al domicilio del cliente (RF-11)."""
    queryset = VisitaTecnica.objects.select_related('cliente', 'orden', 'tecnico').all()
    serializer_class = VisitaTecnicaSerializer
    filterset_fields = ['estado', 'cliente', 'tecnico', 'fecha']
    search_fields = [
        'numero', 'motivo', 'direccion',
        'cliente__nombre', 'cliente__apellidos', 'orden__numero',
    ]
    ordering_fields = ['fecha', 'created_at', 'estado']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        return qs

    def perform_create(self, serializer):
        if not is_staff_role(self.request.user):
            raise PermissionDenied('Solo el personal interno puede registrar visitas técnicas.')
        visita = serializer.save()
        register_audit(self.request.user, 'crear', visita, model_name='servicios.visitatecnica')

    def perform_update(self, serializer):
        if not is_staff_role(self.request.user):
            raise PermissionDenied('Solo el personal interno puede modificar visitas técnicas.')
        visita = serializer.save()
        register_audit(
            self.request.user, 'actualizar', visita,
            model_name='servicios.visitatecnica',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            raise PermissionDenied('Solo el administrador puede eliminar visitas (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='servicios.visitatecnica')
        instance.delete()


class MaterialUtilizadoViewSet(viewsets.ModelViewSet):
    """Actualizar o eliminar un material utilizado en una orden."""
    queryset = MaterialUtilizado.objects.select_related('material', 'orden')
    serializer_class = MaterialUtilizadoSerializer
    filterset_fields = ['orden', 'material']

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        if not is_staff_role(self.request.user):
            raise PermissionDenied('Solo el personal interno puede registrar materiales.')
        serializer.save()

    def perform_update(self, serializer):
        if not is_staff_role(self.request.user):
            raise PermissionDenied('Solo el personal interno puede modificar materiales.')
        uso = serializer.save()
        register_audit(self.request.user, 'actualizar', uso, model_name='servicios.materialutilizado')

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            raise PermissionDenied('Solo el administrador puede eliminar ítems de materiales (RN-08).')
        reponer_inventario(
            instance.material, instance.cantidad,
            usuario=self.request.user,
            motivo=f'Eliminación de ítem en orden {instance.orden.numero}',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='servicios.materialutilizado')
        instance.delete()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(orden__cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(orden__tecnico__user=user)
        return qs
