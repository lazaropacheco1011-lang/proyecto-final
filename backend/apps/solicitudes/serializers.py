from rest_framework import serializers

from apps.solicitudes.models import SolicitudInstalacion


class SolicitudInstalacionSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    instalacion_id = serializers.IntegerField(source='instalacion.id', read_only=True)

    class Meta:
        model = SolicitudInstalacion
        fields = [
            'id', 'cliente', 'cliente_nombre', 'tipo_equipo_solicitado',
            'descripcion', 'prioridad', 'prioridad_display', 'estado',
            'estado_display', 'fecha_solicitud', 'fecha_deseada',
            'observaciones', 'instalacion_id',
        ]
        read_only_fields = ['id', 'fecha_solicitud', 'instalacion_id']
