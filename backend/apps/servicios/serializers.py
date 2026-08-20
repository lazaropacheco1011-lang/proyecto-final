from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente
from apps.core.permissions import CLIENTE, has_role
from apps.materiales.services import descontar_inventario
from apps.servicios.models import (
    EstadoOrdenLog,
    MaterialUtilizado,
    OrdenServicio,
    VisitaTecnica,
)


class EstadoOrdenLogSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = EstadoOrdenLog
        fields = [
            'id', 'orden', 'estado_anterior', 'estado_nuevo',
            'usuario', 'usuario_nombre', 'comentario', 'fecha',
        ]
        read_only_fields = fields


class MaterialUtilizadoSerializer(serializers.ModelSerializer):
    material_nombre = serializers.CharField(source='material.nombre', read_only=True)
    material_codigo = serializers.CharField(source='material.codigo', read_only=True)
    material_unidad = serializers.CharField(source='material.get_unidad_medida_display', read_only=True)
    stock_actual = serializers.DecimalField(
        source='material.cantidad_disponible', read_only=True, max_digits=12, decimal_places=2
    )

    class Meta:
        model = MaterialUtilizado
        fields = [
            'id', 'orden', 'material', 'material_nombre', 'material_codigo',
            'material_unidad', 'cantidad', 'precio_unitario', 'subtotal',
            'stock_actual', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'subtotal']


class MaterialUtilizadoSerializerSinCostos(serializers.ModelSerializer):
    """Sin campos de precio para técnicos."""
    material_nombre = serializers.CharField(source='material.nombre', read_only=True)
    material_codigo = serializers.CharField(source='material.codigo', read_only=True)
    material_unidad = serializers.CharField(source='material.get_unidad_medida_display', read_only=True)
    stock_actual = serializers.DecimalField(
        source='material.cantidad_disponible', read_only=True, max_digits=12, decimal_places=2
    )

    class Meta:
        model = MaterialUtilizado
        fields = [
            'id', 'orden', 'material', 'material_nombre', 'material_codigo',
            'material_unidad', 'cantidad', 'stock_actual', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        material = attrs.get('material')
        cantidad = attrs.get('cantidad')
        if material and cantidad is not None:
            # RN-06: validar inventario suficiente.
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

        # RN-06: descontar del inventario y registrar movimiento.
        descontar_inventario(
            material,
            cantidad,
            usuario=self.context['request'].user,
            motivo=f'Uso en orden {validated_data["orden"].numero}',
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        nueva_cantidad = validated_data.get('cantidad', instance.cantidad)
        material = validated_data.get('material', instance.material)
        diferencia = Decimal(str(nueva_cantidad)) - Decimal(str(instance.cantidad))

        if material != instance.material:
            raise serializers.ValidationError('No se puede cambiar el material de un ítem ya registrado.')

        if diferencia > 0:
            if material.cantidad_disponible < diferencia:
                raise serializers.ValidationError(
                    f'Inventario insuficiente de {material.nombre}: '
                    f'faltan {diferencia} unidades.'
                )
            descontar_inventario(
                material, diferencia,
                usuario=self.context['request'].user,
                motivo=f'Ajuste en orden {instance.orden.numero}',
            )
        elif diferencia < 0:
            from apps.materiales.services import reponer_inventario
            reponer_inventario(
                material, abs(diferencia),
                usuario=self.context['request'].user,
                motivo=f'Devolución por ajuste en orden {instance.orden.numero}',
            )

        validated_data.pop('material', None)
        return super().update(instance, validated_data)


class VisitaTecnicaSerializer(serializers.ModelSerializer):
    """Visitas técnicas programadas (RF-11)."""
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    tecnico_nombre = serializers.CharField(read_only=True)
    orden_numero = serializers.CharField(source='orden.numero', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    orden = serializers.PrimaryKeyRelatedField(
        queryset=OrdenServicio.objects.all(), required=False, allow_null=True
    )
    tecnico = serializers.PrimaryKeyRelatedField(
        queryset=Tecnico.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = VisitaTecnica
        fields = [
            'id', 'numero', 'cliente', 'cliente_nombre', 'orden', 'orden_numero',
            'tecnico', 'tecnico_nombre', 'fecha', 'hora', 'estado', 'estado_display',
            'motivo', 'direccion', 'observaciones', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'numero', 'created_at', 'updated_at']


class OrdenServicioSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    equipo_nombre = serializers.CharField(read_only=True)
    tecnico_nombre = serializers.CharField(read_only=True)
    tipo_servicio_display = serializers.CharField(source='get_tipo_servicio_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    materiales_utilizados = serializers.SerializerMethodField()
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )
    total_materiales = serializers.SerializerMethodField()
    total_evidencias = serializers.SerializerMethodField()
    ultimo_cambio_estado = serializers.SerializerMethodField()

    class Meta:
        model = OrdenServicio
        fields = [
            'id', 'numero', 'cliente', 'cliente_nombre', 'equipo',
            'equipo_nombre', 'tecnico', 'tecnico_nombre', 'tipo_servicio',
            'tipo_servicio_display', 'fecha', 'problema_reportado',
            'diagnostico', 'trabajo_realizado', 'estado', 'estado_display',
            'observaciones', 'fecha_asignacion', 'fecha_finalizacion',
            'materiales_utilizados', 'total_materiales', 'total_evidencias',
            'ultimo_cambio_estado', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'numero', 'created_at', 'updated_at',
            'fecha_asignacion', 'fecha_finalizacion',
        ]

    def get_total_evidencias(self, obj):
        return obj.evidencias.count()

    def _is_tecnico(self):
        request = self.context.get('request')
        if request:
            return has_role(request.user, 'tecnico')
        return False

    def get_materiales_utilizados(self, obj):
        qs = obj.materiales_utilizados.select_related('material')
        if self._is_tecnico():
            return MaterialUtilizadoSerializerSinCostos(qs, many=True).data
        return MaterialUtilizadoSerializer(qs, many=True).data

    def get_total_materiales(self, obj):
        if self._is_tecnico():
            return None
        return round(sum(float(m.subtotal) for m in obj.materiales_utilizados.all()), 2)

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
        user = getattr(self.context.get('request'), 'user', None)
        es_cliente = has_role(user, CLIENTE)
        if es_cliente:
            # El cliente solicita el servicio para sí mismo: se asigna su perfil
            # y los campos técnicos quedan fuera de su alcance.
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
            attrs['tecnico'] = None
            attrs['estado'] = OrdenServicio.Estado.PENDIENTE
            attrs.pop('diagnostico', None)
            attrs.pop('trabajo_realizado', None)
            attrs.pop('observaciones', None)
            attrs.pop('fecha_asignacion', None)
            attrs.pop('fecha_finalizacion', None)

        equipo = attrs.get('equipo', getattr(self.instance, 'equipo', None))
        cliente = attrs.get('cliente', getattr(self.instance, 'cliente', None))
        if not cliente:
            raise serializers.ValidationError(
                {'cliente': 'El cliente es obligatorio.'}
            )
        if cliente and equipo and equipo.cliente_id != cliente.id:
            raise serializers.ValidationError(
                {'equipo': 'El equipo no pertenece al cliente indicado.'}
            )

        estado = attrs.get('estado', getattr(self.instance, 'estado', None) if self.instance else None)
        tecnico = attrs.get('tecnico', getattr(self.instance, 'tecnico', None) if self.instance else None)
        prev_estado = getattr(self.instance, 'estado', None) if self.instance else None

        # RN-02: Toda orden debe tener técnico asignado antes de iniciar.
        if estado in ('asignada', 'en_proceso', 'finalizada') and not tecnico:
            raise serializers.ValidationError(
                {'tecnico': 'Debe asignarse un técnico antes de iniciar la orden (RN-02).'}
            )

        # RN-07: Una orden cancelada no podrá marcarse como finalizada.
        if prev_estado == OrdenServicio.Estado.CANCELADA and estado == OrdenServicio.Estado.FINALIZADA:
            raise serializers.ValidationError(
                'Una orden cancelada no puede marcarse como finalizada (RN-07).'
            )

        # Transiciones válidas.
        if prev_estado and estado != prev_estado:
            permitidas = OrdenServicio.TRANSICIONES_VALIDAS.get(prev_estado, set())
            if estado not in permitidas:
                raise serializers.ValidationError(
                    f'Transición no permitida: {prev_estado} → {estado}. '
                    f'Transiciones válidas: {sorted(permitidas) or "ninguna"}.'
                )

        # RN-04: No se podrá finalizar una orden sin registrar observaciones técnicas.
        if estado == OrdenServicio.Estado.FINALIZADA:
            trabajo = attrs.get('trabajo_realizado', getattr(self.instance, 'trabajo_realizado', ''))
            observaciones = attrs.get('observaciones', getattr(self.instance, 'observaciones', ''))
            diagnostico = attrs.get('diagnostico', getattr(self.instance, 'diagnostico', ''))
            if not (trabajo or observaciones):
                raise serializers.ValidationError(
                    {'error': 'Para finalizar la orden debes registrar el trabajo realizado '
                              'o las observaciones técnicas (RN-04).'}
                )
            if not diagnostico:
                raise serializers.ValidationError(
                    {'diagnostico': 'Debes registrar el diagnóstico antes de finalizar la orden (RN-04).'}
                )

        return attrs

    def create(self, validated_data):
        estado = validated_data.get('estado', OrdenServicio.Estado.PENDIENTE)
        tecnico = validated_data.get('tecnico')
        if estado == OrdenServicio.Estado.ASIGNADA and tecnico:
            validated_data['fecha_asignacion'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        prev_estado = instance.estado
        nuevo_estado = validated_data.get('estado', prev_estado)
        tecnico = validated_data.get('tecnico', instance.tecnico)

        if prev_estado == OrdenServicio.Estado.ASIGNADA and nuevo_estado == OrdenServicio.Estado.EN_PROCESO:
            validated_data['fecha_asignacion'] = validated_data.get(
                'fecha_asignacion', instance.fecha_asignacion
            ) or timezone.now()

        if nuevo_estado == OrdenServicio.Estado.FINALIZADA:
            if not validated_data.get('fecha_finalizacion'):
                validated_data['fecha_finalizacion'] = timezone.now()
            if prev_estado != OrdenServicio.Estado.FINALIZADA:
                # RN-10: al finalizar se habilita la evaluación del cliente.
                pass

        orden = super().update(instance, validated_data)

        if tecnico and orden.fecha_asignacion is None:
            orden.fecha_asignacion = timezone.now()
            orden.save(update_fields=['fecha_asignacion', 'updated_at'])

        return orden
