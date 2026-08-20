from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response

from apps.clientes.models import Cliente, DireccionInstalacion
from apps.clientes.serializers import (
    ClienteMinSerializer,
    ClienteSerializer,
    DireccionInstalacionSerializer,
)
from apps.core.permissions import (
    CLIENTE,
    SUPERVISOR,
    TECNICO,
    IsAdminOrReadOnly,
    IsAdminOrSupervisor,
    IsOwnerOrAdmin,
    IsStaffOrAdmin,
    has_role,
    is_admin,
)
from apps.core.services import delete_or_conflict, register_audit, reject_if

User = get_user_model()

# Relaciones del cliente cuyo historial debe conservarse al intentar eliminar.
_CLIENTE_RELACIONES = [
    ('solicitudes', 'solicitudes de instalación'),
    ('equipos', 'equipos registrados'),
    ('instalaciones', 'instalaciones'),
    ('ordenes', 'órdenes de servicio'),
    ('mantenimientos', 'mantenimientos'),
    ('pagos', 'pagos'),
    ('facturas', 'facturas'),
    ('cotizaciones', 'cotizaciones'),
    ('evaluaciones', 'evaluaciones de servicio'),
    ('ordenes_tienda', 'órdenes de la tienda'),
]


class ClienteViewSet(viewsets.ModelViewSet):
    """CRUD de clientes (RF-04). Solo el administrador elimina (RN-08)."""
    queryset = Cliente.objects.prefetch_related('direcciones').all()
    serializer_class = ClienteSerializer
    filterset_fields = ['tipo', 'tipo_documento', 'ciudad']
    search_fields = [
        'nombre', 'apellidos', 'documento_numero', 'email', 'telefono', 'ciudad'
    ]
    ordering_fields = ['nombre', 'created_at', 'updated_at']

    def get_permissions(self):
        if self.action == 'destroy':
            return [perm() for perm in (IsAdminOnlyDestroy,)]
        if self.action == 'create':
            return [perm() for perm in (IsAdminOrSupervisor,)]
        if self.action in ('update', 'partial_update'):
            return [perm() for perm in (IsOwnerOrAdmin,)]
        if self.action == 'disponibles':
            return [perm() for perm in (IsStaffOrAdmin,)]
        if self.action in ('list', 'retrieve'):
            return [perm() for perm in (IsClienteRead,)]
        return [perm() for perm in (IsOwnerOrAdmin,)]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(user=user)
        return qs

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Lista ligera de clientes para campos de selección (sin datos sensibles)."""
        qs = self.get_queryset().order_by('nombre', 'apellidos')
        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(nombre__icontains=search)
                | Q(apellidos__icontains=search)
                | Q(documento_numero__icontains=search)
            )
        return Response(ClienteMinSerializer(qs[:200], many=True).data)

    def _sync_cuenta(self, cliente):
        """Crea o sincroniza la cuenta de acceso del cliente (panel admin)."""
        data = self.request.data
        username = (data.get('cuenta_username') or '').strip()
        password = data.get('cuenta_password') or ''
        user = cliente.user

        if user:
            dirty = False
            if user.email != cliente.email:
                if User.objects.filter(email__iexact=cliente.email).exclude(pk=user.pk).exists():
                    raise ValidationError({'email': 'Ya existe una cuenta de acceso con ese correo.'})
                user.email = cliente.email
                dirty = True
            if user.first_name != cliente.nombre:
                user.first_name = cliente.nombre
                dirty = True
            if user.last_name != cliente.apellidos:
                user.last_name = cliente.apellidos
                dirty = True
            if user.phone != cliente.telefono:
                user.phone = cliente.telefono
                dirty = True
            if username and username != user.username:
                if User.objects.filter(username__iexact=username).exists():
                    raise ValidationError({'cuenta_username': 'Ese nombre de usuario ya está en uso.'})
                user.username = username
                dirty = True
            if password:
                user.set_password(password)
                dirty = True
            if dirty:
                user.save()
            return

        if username and password:
            if User.objects.filter(username__iexact=username).exists():
                raise ValidationError({'cuenta_username': 'Ese nombre de usuario ya está en uso.'})
            if User.objects.filter(email__iexact=cliente.email).exists():
                raise ValidationError({'cuenta_username': 'Ya existe una cuenta de acceso con ese correo.'})
            user = User(
                username=username,
                email=cliente.email,
                first_name=cliente.nombre,
                last_name=cliente.apellidos,
                phone=cliente.telefono,
                role=CLIENTE,
            )
            user.set_password(password)
            user.save()
            cliente.user = user
            cliente.save(update_fields=['user'])

    def perform_create(self, serializer):
        cliente = serializer.save()
        self._sync_cuenta(cliente)
        register_audit(self.request.user, 'crear', cliente, model_name='clientes.cliente')

    def perform_update(self, serializer):
        cliente = serializer.save()
        self._sync_cuenta(cliente)
        register_audit(
            self.request.user, 'actualizar', cliente, model_name='clientes.cliente',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        relacionados = [
            label for name, label in _CLIENTE_RELACIONES
            if getattr(instance, name).exists()
        ]
        reject_if(
            relacionados,
            'No se puede eliminar el cliente porque tiene registros relacionados '
            'que deben conservarse: ' + ', '.join(relacionados) + '.',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='clientes.cliente')
        delete_or_conflict(instance)


class IsAdminOnlyDestroy(BasePermission):
    message = 'Solo el administrador puede eliminar clientes (RN-08).'

    def has_permission(self, request, view):
        return is_admin(request.user)

    def has_object_permission(self, request, view, obj):
        return is_admin(request.user)


class IsClienteRead(BasePermission):
    """Lectura de información completa de clientes: solo admin, supervisor y el propio cliente."""
    message = 'No tienes permiso para consultar la información de clientes.'

    def has_permission(self, request, view):
        return is_admin(request.user) or has_role(request.user, SUPERVISOR, CLIENTE)


class DireccionAccess(BasePermission):
    """Técnicos no acceden a direcciones de instalación."""
    message = 'Los técnicos no tienen acceso a direcciones de instalación.'

    def has_permission(self, request, view):
        return not has_role(request.user, TECNICO)


class DireccionInstalacionViewSet(viewsets.ModelViewSet):
    """Direcciones de instalación de los clientes (RF-05)."""
    queryset = DireccionInstalacion.objects.select_related('cliente').all()
    serializer_class = DireccionInstalacionSerializer
    filterset_fields = ['cliente', 'ciudad', 'principal']
    search_fields = ['direccion', 'ciudad', 'etiqueta', 'referencia']

    def get_permissions(self):
        if self.action == 'destroy':
            return [perm() for perm in (IsAdminOnlyDestroy,)]
        return [perm() for perm in (DireccionAccess,)]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='clientes.direccioninstalacion')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'actualizar', obj, model_name='clientes.direccioninstalacion')

    def perform_destroy(self, instance):
        register_audit(self.request.user, 'eliminar', instance, model_name='clientes.direccioninstalacion')
        instance.delete()
