from rest_framework import viewsets
from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.core.permissions import ADMIN, ALMACEN, CLIENTE, SUPERVISOR, get_supervisor_tecnico_ids, has_role, is_admin, is_supervisor
from apps.core.services import register_audit
from apps.notificaciones.services import notify_pago_confirmado
from apps.pagos.models import Factura, Pago
from apps.pagos.serializers import FacturaSerializer, PagoSerializer


class StaffNoTecnicoPermission(BasePermission):
    """Acceso a pagos/facturas: personal interno excepto técnicos."""
    message = 'Los técnicos no tienen acceso a información de pagos.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if has_role(request.user, 'tecnico'):
            return False
        if request.method in SAFE_METHODS:
            return True
        return has_role(request.user, ADMIN, SUPERVISOR, ALMACEN)


class PagoViewSet(viewsets.ModelViewSet):
    """Pagos y abonos de clientes (RF-18)."""
    queryset = Pago.objects.select_related('cliente', 'orden', 'instalacion').all()
    serializer_class = PagoSerializer
    permission_classes = [StaffNoTecnicoPermission]
    filterset_fields = ['cliente', 'orden', 'instalacion', 'metodo', 'estado', 'fecha']
    search_fields = ['referencia', 'cliente__nombre', 'cliente__documento_numero']
    ordering_fields = ['fecha', 'monto', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(orden__tecnico__user_id__in=tecnicos_ids)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        pago = serializer.save(registrado_por=self.request.user)
        register_audit(self.request.user, 'crear', pago, model_name='pagos.pago')
        if pago.estado == 'pagado':
            notify_pago_confirmado(pago)

    def perform_update(self, serializer):
        prev_estado = serializer.instance.estado if serializer.instance else None
        pago = serializer.save()
        if prev_estado != 'pagado' and pago.estado == 'pagado':
            notify_pago_confirmado(pago)
        register_audit(
            self.request.user, 'actualizar', pago, model_name='pagos.pago',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied
        user = self.request.user
        if has_role(user, SUPERVISOR):
            raise PermissionDenied('Los supervisores no pueden eliminar pagos.')
        if not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar pagos (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='pagos.pago')
        instance.delete()


class FacturaViewSet(viewsets.ModelViewSet):
    """Facturas y comprobantes de servicio (RF-19)."""
    queryset = Factura.objects.prefetch_related('pagos').select_related('cliente', 'orden', 'creado_por')
    serializer_class = FacturaSerializer
    permission_classes = [StaffNoTecnicoPermission]
    filterset_fields = ['cliente', 'orden', 'fecha']
    search_fields = ['numero', 'cliente__nombre']
    ordering_fields = ['fecha', 'total', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(orden__tecnico__user_id__in=tecnicos_ids)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        factura = serializer.save(creado_por=self.request.user)
        if factura.pagos.exists():
            factura.calcular_totales()
        register_audit(self.request.user, 'crear', factura, model_name='pagos.factura')

    def perform_update(self, serializer):
        factura = serializer.save()
        if factura.pagos.exists():
            factura.calcular_totales()
        register_audit(
            self.request.user, 'actualizar', factura, model_name='pagos.factura',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        from rest_framework.exceptions import PermissionDenied
        user = self.request.user
        if has_role(user, SUPERVISOR):
            raise PermissionDenied('Los supervisores no pueden eliminar facturas.')
        if not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar facturas (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='pagos.factura')
        instance.delete()
