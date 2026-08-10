from rest_framework import serializers

from apps.materiales.models import Material, MovimientoInventario
from apps.materiales.services import ajustar_inventario, descontar_inventario, reponer_inventario


class MaterialSerializer(serializers.ModelSerializer):
    unidad_display = serializers.CharField(source='get_unidad_medida_display', read_only=True)
    stock_bajo = serializers.BooleanField(read_only=True)
    total_movimientos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Material
        fields = [
            'id', 'nombre', 'codigo', 'descripcion', 'categoria',
            'unidad_medida', 'unidad_display', 'cantidad_disponible',
            'stock_minimo', 'stock_bajo', 'precio', 'total_movimientos',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'stock_bajo', 'total_movimientos']

    def validate_codigo(self, value):
        qs = Material.objects.filter(codigo__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un material con ese código.')
        return value

    def validate(self, attrs):
        if attrs.get('stock_minimo', 0) is not None and attrs.get('cantidad_disponible', 0) is not None:
            if float(attrs.get('cantidad_disponible', 0)) < 0:
                raise serializers.ValidationError(
                    {'cantidad_disponible': 'La cantidad disponible no puede ser negativa.'}
                )
            if float(attrs.get('stock_minimo', 0)) < 0:
                raise serializers.ValidationError(
                    {'stock_minimo': 'El stock mínimo no puede ser negativo.'}
                )
        return attrs


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source='material.nombre', read_only=True)
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)

    class Meta:
        model = MovimientoInventario
        fields = [
            'id', 'material', 'material_nombre', 'tipo', 'tipo_display',
            'cantidad', 'motivo', 'usuario', 'usuario_nombre', 'fecha',
        ]
        read_only_fields = ['id', 'fecha', 'usuario', 'usuario_nombre']


class EntradaInventarioSerializer(serializers.Serializer):
    """Registra una entrada o ajuste manual de inventario."""
    cantidad = serializers.DecimalField(max_digits=12, decimal_places=2)
    motivo = serializers.CharField(max_length=255, required=False, allow_blank=True)
    tipo = serializers.ChoiceField(
        choices=['entrada', 'ajuste'], default='entrada',
        help_text='entrada suma stock; ajuste fija la cantidad disponible.',
    )

    def validate_cantidad(self, value):
        if value <= 0:
            raise serializers.ValidationError('La cantidad debe ser mayor que cero.')
        return value

    def save(self, material, usuario):
        tipo = self.validated_data.get('tipo', 'entrada')
        cantidad = self.validated_data['cantidad']
        motivo = self.validated_data.get('motivo', '')
        if tipo == 'ajuste':
            ajustar_inventario(material, cantidad, usuario, motivo or 'Ajuste manual')
        else:
            reponer_inventario(material, cantidad, usuario, motivo or 'Entrada de inventario')
        return material
