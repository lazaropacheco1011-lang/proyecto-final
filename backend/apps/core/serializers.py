from rest_framework import serializers

from apps.core.models import AuditLog, Evidencia, FirmaDigital

MAX_IMAGEN_BYTES = 5 * 1024 * 1024
EXTENSIONES_IMAGEN = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')


def validate_imagen(value):
    if value is None:
        return value
    if value.size > MAX_IMAGEN_BYTES:
        raise serializers.ValidationError('La imagen no puede superar los 5 MB.')
    nombre = (getattr(value, 'name', '') or '').lower()
    if not nombre.endswith(EXTENSIONES_IMAGEN):
        raise serializers.ValidationError(
            'El archivo debe ser una imagen (jpg, png, webp, gif o bmp).'
        )
    return value


class AuditLogSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'usuario', 'action', 'model_name', 'object_id',
            'object_repr', 'changes', 'ip_address', 'created_at',
        ]
        read_only_fields = fields


class EvidenciaSerializer(serializers.ModelSerializer):
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField(write_only=True)
    url = serializers.SerializerMethodField()
    subido_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Evidencia
        fields = [
            'id', 'content_type', 'object_id', 'imagen', 'url',
            'descripcion', 'fase', 'subido_por', 'created_at',
        ]
        read_only_fields = ['id', 'url', 'subido_por', 'created_at']

    def validate_imagen(self, value):
        return validate_imagen(value)

    def validate(self, attrs):
        from django.contrib.contenttypes.models import ContentType

        content_type_label = attrs.pop('content_type', None)
        object_id = attrs.pop('object_id', None)
        if not content_type_label or not object_id:
            raise serializers.ValidationError(
                'Debes indicar content_type (app_label.Modelo) y object_id.'
            )
        try:
            app_label, model = content_type_label.lower().split('.')
            content_type = ContentType.objects.get_by_natural_key(app_label, model)
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError(
                f'content_type inválido: {content_type_label}. '
                'Usa el formato app_label.modelo (ej: instalaciones.instalacion).'
            )
        try:
            content_type.model_class().objects.get(pk=object_id)
        except Exception:
            raise serializers.ValidationError(
                f'No existe el objeto {content_type_label} con id {object_id}.'
            )
        attrs['content_type'] = content_type
        attrs['object_id'] = object_id
        return attrs

    def get_url(self, obj):
        if obj.imagen:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None


class FirmaSerializer(serializers.ModelSerializer):
    """Registra una firma digital asociada a una instalación u orden."""

    content_type = serializers.CharField(write_only=True)
    object_id = serializers.IntegerField(write_only=True)
    url = serializers.SerializerMethodField()
    subido_por = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = FirmaDigital
        fields = [
            'id', 'content_type', 'object_id', 'imagen', 'url',
            'nombre', 'documento', 'observaciones', 'subido_por', 'created_at',
        ]
        read_only_fields = ['id', 'url', 'subido_por', 'created_at']

    def validate_imagen(self, value):
        return validate_imagen(value)

    def validate(self, attrs):
        from django.contrib.contenttypes.models import ContentType

        content_type_label = attrs.pop('content_type', None)
        object_id = attrs.pop('object_id', None)
        if not content_type_label or not object_id:
            raise serializers.ValidationError(
                'Debes indicar content_type (app_label.Modelo) y object_id.'
            )
        try:
            app_label, model = content_type_label.lower().split('.')
            content_type = ContentType.objects.get_by_natural_key(app_label, model)
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError(
                f'content_type inválido: {content_type_label}. '
                'Usa el formato app_label.modelo (ej: instalaciones.instalacion).'
            )
        try:
            content_type.model_class().objects.get(pk=object_id)
        except Exception:
            raise serializers.ValidationError(
                f'No existe el objeto {content_type_label} con id {object_id}.'
            )
        attrs['content_type'] = content_type
        attrs['object_id'] = object_id
        return attrs

    def get_url(self, obj):
        if obj.imagen:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.imagen.url)
            return obj.imagen.url
        return None
