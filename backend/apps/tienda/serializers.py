"""Serializers de la tienda."""
from rest_framework import serializers

from apps.tienda.models import Orden, OrdenEstadoLog, OrdenItem, PagoTienda


class OrdenItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenItem
        fields = ['id', 'producto', 'nombre', 'imagen', 'precio_unitario', 'cantidad', 'subtotal']


class PagoTiendaSerializer(serializers.ModelSerializer):
    metodo_display = serializers.CharField(source='get_metodo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = PagoTienda
        fields = [
            'id', 'metodo', 'metodo_display', 'estado', 'estado_display',
            'monto', 'moneda', 'referencia', 'ultimos_digitos',
            'marca_tarjeta', 'created_at',
        ]
        read_only_fields = fields


class PagoTiendaPublicoSerializer(serializers.ModelSerializer):
    """Pago visible al público: sin referencia del proveedor ni dígitos de tarjeta."""
    metodo_display = serializers.CharField(source='get_metodo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = PagoTienda
        fields = [
            'id', 'metodo', 'metodo_display', 'estado', 'estado_display',
            'monto', 'moneda', 'created_at',
        ]
        read_only_fields = fields


class OrdenEstadoLogSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = OrdenEstadoLog
        fields = ['id', 'estado_anterior', 'estado_nuevo', 'usuario', 'usuario_nombre', 'comentario', 'fecha']
        read_only_fields = fields


class OrdenSerializer(serializers.ModelSerializer):
    items = OrdenItemSerializer(many=True, read_only=True)
    pagos = PagoTiendaSerializer(many=True, read_only=True)
    historial = OrdenEstadoLogSerializer(many=True, read_only=True)
    cliente_display = serializers.CharField(read_only=True)
    metodo_pago = serializers.CharField(read_only=True)
    estado_pago = serializers.CharField(read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = Orden
        fields = [
            'id', 'numero', 'cliente', 'cliente_display', 'nombre_cliente',
            'email', 'telefono', 'direccion_entrega', 'ciudad_entrega',
            'referencia_entrega', 'notas',
            'documento', 'provincia', 'sector',
            'usuario', 'usuario_nombre',
            'subtotal', 'envio', 'descuento',
            'total', 'moneda', 'estado', 'estado_display', 'items', 'pagos',
            'historial', 'metodo_pago', 'estado_pago', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'numero', 'subtotal', 'envio', 'descuento', 'total',
            'moneda', 'items', 'pagos', 'historial', 'created_at', 'updated_at',
        ]


class OrdenPublicaSerializer(serializers.ModelSerializer):
    """Versión pública de la orden: sin datos personales ni de tarjeta."""
    items = OrdenItemSerializer(many=True, read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    pagos = PagoTiendaPublicoSerializer(many=True, read_only=True)

    class Meta:
        model = Orden
        fields = [
            'numero', 'subtotal', 'envio', 'descuento', 'total',
            'moneda', 'estado', 'estado_display', 'items', 'pagos',
            'created_at',
        ]
