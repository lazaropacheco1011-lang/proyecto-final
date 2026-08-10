from rest_framework import serializers

from apps.clientes.models import Cliente
from apps.core.permissions import CLIENTE, has_role
from apps.equipos.models import Equipo, TipoEquipo


class TipoEquipoSerializer(serializers.ModelSerializer):
    total_equipos = serializers.IntegerField(read_only=True)

    class Meta:
        model = TipoEquipo
        fields = ['id', 'nombre', 'descripcion', 'total_equipos']
        read_only_fields = ['id', 'total_equipos']

    def validate_nombre(self, value):
        qs = TipoEquipo.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un tipo de equipo con ese nombre.')
        return value


class EquipoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    tipo_nombre = serializers.CharField(source='tipo.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    garantia_hasta = serializers.DateField(read_only=True)
    garantia_activa = serializers.BooleanField(read_only=True)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True, default=None
    )

    class Meta:
        model = Equipo
        fields = [
            'id', 'cliente', 'cliente_nombre', 'tipo', 'tipo_nombre',
            'marca', 'modelo', 'numero_serie', 'capacidad', 'refrigerante',
            'estado', 'estado_display', 'fecha_instalacion', 'garantia_meses',
            'garantia_hasta', 'garantia_activa', 'ubicacion',
            'descripcion', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'garantia_hasta', 'garantia_activa']

    def validate_numero_serie(self, value):
        qs = Equipo.objects.filter(numero_serie__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un equipo con ese número de serie.')
        return value

    def validate(self, attrs):
        user = getattr(self.context.get('request'), 'user', None)
        es_cliente = has_role(user, CLIENTE)
        if es_cliente:
            # El cliente registra sus propios equipos: se asigna su perfil y se
            # mantienen los campos técnicos fuera de su alcance.
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
            attrs.pop('estado', None)
            attrs.pop('fecha_instalacion', None)
            attrs.pop('garantia_meses', None)
            if not self.instance:
                attrs['estado'] = Equipo.Estado.INSTALADO
        else:
            if attrs.get('cliente') is None:
                attrs.pop('cliente', None)
            if not self.instance and 'cliente' not in attrs:
                raise serializers.ValidationError(
                    {'cliente': 'El cliente es obligatorio (RN-01).'}
                )

        cliente = attrs.get('cliente', getattr(self.instance, 'cliente', None))
        numero_serie = attrs.get('numero_serie', getattr(self.instance, 'numero_serie', None))
        if cliente and numero_serie:
            qs = Equipo.objects.filter(cliente=cliente, numero_serie__iexact=numero_serie)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    'Este cliente ya tiene registrado un equipo con ese número de serie.'
                )
        return attrs
