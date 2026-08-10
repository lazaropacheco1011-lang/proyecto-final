from django.db.models import Count
from rest_framework import serializers

from apps.almacen.images import resolve_asset_url
from apps.almacen.models import Categoria, Producto


class CategoriaSerializer(serializers.ModelSerializer):
    total_productos = serializers.IntegerField(read_only=True)

    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'descripcion', 'icono', 'orden', 'total_productos']
        read_only_fields = ['id', 'total_productos']

    def validate_nombre(self, value):
        qs = Categoria.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe una categoría con ese nombre.')
        return value


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    agotado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'categoria', 'categoria_nombre', 'descripcion',
            'imagen', 'precio', 'disponible', 'stock', 'destacado',
            'agotado', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_imagen(self, value):
        # Normaliza la ruta guardada para que la Vitrina Pública y el panel
        # usen siempre la misma URL válida y existente.
        return resolve_asset_url(value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['imagen'] = resolve_asset_url(data.get('imagen') or '')
        return data

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock no puede ser negativo.')
        return value
