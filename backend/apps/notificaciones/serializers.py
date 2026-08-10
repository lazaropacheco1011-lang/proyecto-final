from rest_framework import serializers

from apps.notificaciones.models import Notificacion


class NotificacionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    fecha_formateada = serializers.DateTimeField(source='fecha', read_only=True, format='%d/%m/%Y %H:%M')

    class Meta:
        model = Notificacion
        fields = [
            'id', 'usuario', 'tipo', 'tipo_display', 'titulo',
            'mensaje', 'leida', 'fecha', 'fecha_formateada',
        ]
        read_only_fields = ['id', 'usuario', 'tipo', 'titulo', 'mensaje', 'fecha', 'fecha_formateada']
