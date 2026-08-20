from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.core.permissions import IsAdminOrAlmacen, has_role
from apps.core.services import delete_or_conflict, register_audit, reject_if
from apps.materiales.models import Material, MovimientoInventario
from apps.materiales.serializers import (
    EntradaInventarioSerializer,
    MaterialSerializer,
    MaterialSerializerSinPrecio,
    MovimientoInventarioSerializer,
)


class MaterialViewSet(viewsets.ModelViewSet):
    """CRUD de materiales y repuestos (RF-15, RF-16)."""
    queryset = Material.objects.annotate(
        total_movimientos=Count('movimientos')
    ).order_by('nombre')
    serializer_class = MaterialSerializer
    filterset_fields = ['categoria', 'unidad_medida']
    search_fields = ['nombre', 'codigo', 'descripcion', 'categoria']
    ordering_fields = ['nombre', 'cantidad_disponible', 'precio', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'destroy', 'update', 'partial_update'):
            return [perm() for perm in (IsAdminOrAlmacen,)]
        return [perm() for perm in (CanViewMateriales,)]

    def get_serializer_class(self):
        if has_role(self.request.user, 'tecnico'):
            return MaterialSerializerSinPrecio
        return MaterialSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if has_role(self.request.user, 'cliente'):
            return qs.none()
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='materiales.material')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(
            self.request.user, 'actualizar', obj, model_name='materiales.material',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        reject_if(
            instance.usos.exists() or instance.movimientos.exists(),
            'No se puede eliminar el material porque tiene usos en órdenes de '
            'servicio o movimientos de inventario que deben conservarse.',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='materiales.material')
        delete_or_conflict(instance)

    @action(detail=False, methods=['get'])
    def stock_bajo(self, request):
        """Materiales cuyo stock está en o por debajo del mínimo."""
        qs = self.get_queryset().filter(
            cantidad_disponible__lte=__import__('django.db.models', fromlist=['F']).F('stock_minimo')
        )
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminOrAlmacen])
    def entrada(self, request, pk=None):
        """Registra una entrada o ajuste manual de inventario."""
        material = self.get_object()
        serializer = EntradaInventarioSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(material, usuario=request.user)
        register_audit(
            request.user, 'actualizar', material,
            model_name='materiales.material',
            changes={'tipo_movimiento': 'entrada_ajuste', **request.data},
        )
        return Response(
            self.get_serializer(material).data, status=status.HTTP_200_OK
        )


class CanViewMateriales(BasePermission):
    message = 'No tienes permisos para consultar materiales.'

    def has_permission(self, request, view):
        from apps.core.permissions import is_staff_role
        return bool(
            request.user
            and request.user.is_authenticated
            and is_staff_role(request.user)
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class MovimientoInventarioViewSet(viewsets.ReadOnlyModelViewSet):
    """Consulta de movimientos de inventario (solo administrador/almacén)."""
    queryset = MovimientoInventario.objects.select_related('material', 'usuario').all()
    serializer_class = MovimientoInventarioSerializer
    filterset_fields = ['material', 'tipo', 'usuario', 'fecha']
    search_fields = ['motivo', 'material__nombre', 'material__codigo']
    ordering_fields = ['fecha']

    def get_permissions(self):
        return [perm() for perm in (CanViewMovimientos,)]


class CanViewMovimientos(BasePermission):
    message = 'No tienes permisos para consultar movimientos.'

    def has_permission(self, request, view):
        from apps.core.permissions import has_role
        return has_role(request.user, 'administrador', 'almacen')

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
