from rest_framework import serializers

from apps.cotizaciones.models import Cotizacion, CotizacionDetalle


class CotizacionDetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CotizacionDetalle
        fields = ['id', 'descripcion', 'cantidad', 'precio_unitario', 'total']
        read_only_fields = ['id', 'total']


class CotizacionSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    tecnico_nombre = serializers.CharField(read_only=True)
    solicitud_numero = serializers.IntegerField(source='solicitud.id', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    detalles = CotizacionDetalleSerializer(many=True)

    class Meta:
        model = Cotizacion
        fields = [
            'id', 'numero', 'cliente', 'cliente_nombre', 'solicitud',
            'solicitud_numero', 'tecnico', 'tecnico_nombre', 'fecha',
            'validez_dias', 'subtotal', 'descuento', 'total', 'estado',
            'estado_display', 'notas', 'detalles', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'numero', 'fecha', 'created_at', 'updated_at']
        extra_kwargs = {'subtotal': {'read_only': True}, 'total': {'read_only': True}}

    def create(self, validated_data):
        detalles = validated_data.pop('detalles', [])
        cotizacion = Cotizacion.objects.create(**validated_data)
        for detalle in detalles:
            CotizacionDetalle.objects.create(cotizacion=cotizacion, **detalle)
        cotizacion.recalcular()
        return cotizacion

    def update(self, instance, validated_data):
        detalles = validated_data.pop('detalles', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if detalles is not None:
            instance.detalles.all().delete()
            for detalle in detalles:
                CotizacionDetalle.objects.create(cotizacion=instance, **detalle)
            instance.recalcular()
        return instance
