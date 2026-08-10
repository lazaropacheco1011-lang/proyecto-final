from rest_framework import serializers

from apps.pagos.models import Factura, Pago


class PagoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    orden_numero = serializers.CharField(source='orden.numero', read_only=True)
    instalacion_id = serializers.IntegerField(source='instalacion.id', read_only=True)
    metodo_display = serializers.CharField(source='get_metodo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Pago
        fields = [
            'id', 'cliente', 'cliente_nombre', 'orden', 'orden_numero',
            'instalacion', 'instalacion_id', 'monto', 'es_abono', 'metodo',
            'metodo_display', 'fecha', 'referencia', 'estado', 'estado_display',
            'registrado_por', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'registrado_por']

    def validate_monto(self, value):
        if value <= 0:
            raise serializers.ValidationError('El monto debe ser mayor que cero.')
        return value

    def validate(self, attrs):
        if not attrs.get('orden') and not attrs.get('instalacion'):
            raise serializers.ValidationError(
                'El pago debe estar asociado a una orden de servicio o a una instalación.'
            )
        return attrs


class FacturaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    orden_numero = serializers.CharField(source='orden.numero', read_only=True)
    pagos_detalle = PagoSerializer(source='pagos', many=True, read_only=True)
    creado_por_nombre = serializers.CharField(source='creado_por.username', read_only=True)

    class Meta:
        model = Factura
        fields = [
            'id', 'numero', 'cliente', 'cliente_nombre', 'orden', 'orden_numero',
            'fecha', 'subtotal', 'iva', 'total', 'pagos', 'pagos_detalle',
            'notas', 'creado_por', 'creado_por_nombre', 'created_at',
        ]
        read_only_fields = ['id', 'numero', 'fecha', 'creado_por', 'created_at']
        extra_kwargs = {'subtotal': {'read_only': True}, 'total': {'read_only': True}}
