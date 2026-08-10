from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.instalaciones.models import Instalacion, InstalacionEstadoLog, MaterialInstalacion
from apps.instalaciones.services import finalizar_instalacion


class MaterialInstalacionSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source='material.nombre', read_only=True)
    material_codigo = serializers.CharField(source='material.codigo', read_only=True)
    material_unidad = serializers.CharField(source='material.get_unidad_medida_display', read_only=True)
    stock_actual = serializers.DecimalField(
        source='material.cantidad_disponible', read_only=True, max_digits=12, decimal_places=2
    )

    class Meta:
        model = MaterialInstalacion
        fields = [
            'id', 'instalacion', 'material', 'material_nombre', 'material_codigo',
            'material_unidad', 'cantidad', 'precio_unitario', 'subtotal',
            'stock_actual', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'subtotal']

    def validate(self, attrs):
        material = attrs.get('material')
        cantidad = attrs.get('cantidad')
        if material and cantidad is not None:
            # RN-06: validar inventario suficiente al registrar el material.
            if material.cantidad_disponible < cantidad:
                raise serializers.ValidationError(
                    f'Inventario insuficiente de {material.nombre}: '
                    f'disponible {material.cantidad_disponible}, requerido {cantidad}.'
                )
        return attrs

    def create(self, validated_data):
        material = validated_data['material']
        cantidad = validated_data['cantidad']
        precio_unitario = validated_data.get('precio_unitario') or material.precio
        validated_data['precio_unitario'] = precio_unitario
        # El inventario se descuenta al finalizar la instalación
        # (instalaciones.services.finalizar_instalacion).
        return super().create(validated_data)


class InstalacionEstadoLogSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = InstalacionEstadoLog
        fields = [
            'id', 'instalacion', 'estado_anterior', 'estado_nuevo',
            'usuario', 'usuario_nombre', 'comentario', 'fecha',
        ]
        read_only_fields = fields


class InstalacionSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    equipo_nombre = serializers.CharField(read_only=True)
    tecnico_nombre = serializers.CharField(read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    solicitud_numero = serializers.IntegerField(source='solicitud.id', read_only=True)
    total_evidencias = serializers.SerializerMethodField()
    evidencias = serializers.SerializerMethodField()
    materiales_instalacion = MaterialInstalacionSerializer(many=True, read_only=True)
    total_materiales = serializers.SerializerMethodField()
    firmas = serializers.SerializerMethodField()
    ultimo_cambio_estado = serializers.SerializerMethodField()

    class Meta:
        model = Instalacion
        fields = [
            'id', 'cliente', 'cliente_nombre', 'equipo', 'equipo_nombre',
            'tecnico', 'tecnico_nombre', 'solicitud', 'solicitud_numero',
            'fecha_programada', 'fecha_instalacion', 'prioridad',
            'prioridad_display', 'direccion', 'ciudad', 'latitud', 'longitud',
            'estado', 'estado_display', 'observaciones', 'total_evidencias',
            'evidencias', 'materiales_instalacion', 'total_materiales',
            'firmas', 'ultimo_cambio_estado', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_total_evidencias(self, obj):
        return obj.evidencias.count()

    def get_evidencias(self, obj):
        from apps.core.serializers import EvidenciaSerializer
        qs = obj.evidencias.all()[:20]
        return EvidenciaSerializer(qs, many=True, context=self.context).data

    def get_total_materiales(self, obj):
        return round(sum(float(m.subtotal) for m in obj.materiales_instalacion.all()), 2)

    def get_firmas(self, obj):
        from apps.core.serializers import FirmaSerializer
        return FirmaSerializer(obj.firmas.all(), many=True, context=self.context).data

    def get_ultimo_cambio_estado(self, obj):
        log = obj.historial.first()
        if log:
            return {
                'estado_anterior': log.estado_anterior,
                'estado_nuevo': log.estado_nuevo,
                'usuario': log.usuario.username if log.usuario else None,
                'comentario': log.comentario,
                'fecha': log.fecha,
            }
        return None

    def validate(self, attrs):
        estado = attrs.get('estado', getattr(self.instance, 'estado', None))
        tecnico = attrs.get('tecnico', getattr(self.instance, 'tecnico', None))
        fecha = attrs.get('fecha_programada', getattr(self.instance, 'fecha_programada', None))

        # RN-01: Toda instalación debe estar asociada a un cliente.
        cliente = attrs.get('cliente', getattr(self.instance, 'cliente', None))
        if not cliente:
            raise serializers.ValidationError({'cliente': 'La instalación debe tener un cliente (RN-01).'})

        # RN-02 (aplicado a instalaciones): para iniciar debe haber técnico.
        if estado in ('asignada', 'en_proceso', 'finalizada') and not tecnico:
            raise serializers.ValidationError(
                {'tecnico': 'Debe asignarse un técnico antes de iniciar la instalación (RN-02).'}
            )

        # RN-03: Un técnico no debe tener dos instalaciones en el mismo horario.
        if tecnico and fecha:
            conflicts = Instalacion.objects.filter(
                tecnico=tecnico,
                fecha_programada__range=(fecha - timedelta(hours=2), fecha + timedelta(hours=2)),
            ).exclude(estado__in=['cancelada', 'finalizada'])
            if self.instance:
                conflicts = conflicts.exclude(pk=self.instance.pk)
            if conflicts.exists():
                raise serializers.ValidationError(
                    {'fecha_programada': 'El técnico ya tiene una instalación programada en ese horario (RN-03).'}
                )

        # RN-07: Una instalación cancelada no podrá marcarse como finalizada.
        prev_estado = getattr(self.instance, 'estado', None) if self.instance else None
        if prev_estado == 'cancelada' and estado == 'finalizada':
            raise serializers.ValidationError(
                'Una instalación cancelada no puede marcarse como finalizada (RN-07).'
            )

        return attrs

    def update(self, instance, validated_data):
        estado = validated_data.get('estado', instance.estado)
        if estado == 'finalizada' and instance.estado != 'finalizada':
            # RN-05: No se podrá finalizar una instalación sin evidencia fotográfica.
            if not instance.evidencias.exists():
                raise serializers.ValidationError(
                    'No se puede finalizar la instalación sin evidencia fotográfica (RN-05). '
                    'Sube al menos una evidencia con POST /api/evidencias/ antes de finalizar.'
                )
            if not validated_data.get('fecha_instalacion'):
                validated_data['fecha_instalacion'] = timezone.now()
            # RN-06: descontar del inventario los materiales utilizados (RF-15b).
            user = (self.context.get('request') or {}).user
            try:
                finalizar_instalacion(instance, user=user)
            except ValueError as exc:
                raise serializers.ValidationError({'error': str(exc)})
        return super().update(instance, validated_data)

    def create(self, validated_data):
        return super().create(validated_data)
