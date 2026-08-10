from decimal import Decimal

from rest_framework import serializers

from apps.clientes.models import Cliente
from apps.core.permissions import CLIENTE, has_role
from apps.mantenimientos.models import Mantenimiento


class MantenimientoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    equipo_nombre = serializers.CharField(read_only=True)
    tecnico_nombre = serializers.CharField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Mantenimiento
        fields = [
            'id', 'equipo', 'equipo_nombre', 'cliente', 'cliente_nombre',
            'tecnico', 'tecnico_nombre', 'tipo', 'tipo_display', 'fecha',
            'proxima_fecha', 'descripcion', 'trabajo_realizado', 'estado',
            'estado_display', 'costo', 'observaciones', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        user = getattr(self.context.get('request'), 'user', None)
        es_cliente = has_role(user, CLIENTE)
        if es_cliente:
            # El cliente solicita para sí mismo: se asigna su perfil y se
            # mantienen campos técnicos fuera de su alcance.
            perfil = None
            if user:
                try:
                    perfil = user.perfil_cliente
                except Exception:
                    perfil = None
            if perfil is None:
                raise serializers.ValidationError(
                    {'cliente': 'Tu cuenta no tiene un perfil de cliente asociado.'}
                )
            attrs['cliente'] = perfil
            attrs['tecnico'] = None
            attrs['estado'] = Mantenimiento.Estado.PENDIENTE
            attrs['costo'] = Decimal('0')
            attrs.pop('trabajo_realizado', None)

        equipo = attrs.get('equipo', getattr(self.instance, 'equipo', None))
        cliente = attrs.get('cliente', getattr(self.instance, 'cliente', None))
        if not cliente:
            raise serializers.ValidationError(
                {'cliente': 'El cliente es obligatorio (RN-01).'}
            )
        if cliente and equipo and equipo.cliente_id != cliente.id:
            raise serializers.ValidationError(
                {'equipo': 'El equipo no pertenece al cliente indicado.'}
            )
        return attrs
