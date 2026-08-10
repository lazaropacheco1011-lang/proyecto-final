from rest_framework import serializers

from apps.clientes.models import Cliente
from apps.core.permissions import CLIENTE, has_role
from apps.evaluaciones.models import EvaluacionServicio
from apps.servicios.models import OrdenServicio


class EvaluacionServicioSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    orden_numero = serializers.CharField(source='orden.numero', read_only=True)
    instalacion_id = serializers.IntegerField(source='instalacion.id', read_only=True)
    cliente = serializers.PrimaryKeyRelatedField(
        queryset=Cliente.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = EvaluacionServicio
        fields = [
            'id', 'cliente', 'cliente_nombre', 'orden', 'orden_numero',
            'instalacion', 'instalacion_id', 'calificacion', 'comentario', 'fecha',
        ]
        read_only_fields = ['id', 'fecha']
        # La unicidad de (cliente, orden) se valida en validate() con un mensaje
        # amigable (RN-10). Sin esto, DRF genera un UniqueTogetherValidator que
        # además exige enviar 'cliente' en el POST del cliente.
        validators = []

    def validate_calificacion(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('La calificación debe estar entre 1 y 5.')
        return value

    def validate(self, attrs):
        # RN-10: solo se evalúa un servicio finalizado.
        instancia = self.instance
        orden = attrs.get('orden', instancia.orden if instancia else None)
        instalacion = attrs.get('instalacion', instancia.instalacion if instancia else None)
        cliente = attrs.get('cliente', instancia.cliente if instancia else None)

        if not orden and not instalacion:
            raise serializers.ValidationError(
                'La evaluación debe estar asociada a una orden o instalación.'
            )
        if orden and orden.estado != OrdenServicio.Estado.FINALIZADA:
            raise serializers.ValidationError(
                'Solo puedes evaluar servicios finalizados (RN-10).'
            )
        if instalacion and instalacion.estado != 'finalizada':
            raise serializers.ValidationError(
                'Solo puedes evaluar instalaciones finalizadas (RN-10).'
            )

        # El cliente evalúa únicamente servicios de su propia cuenta.
        user = getattr(self.context.get('request'), 'user', None)
        if has_role(user, CLIENTE):
            perfil = getattr(user, 'perfil_cliente', None)
            if perfil is None:
                raise serializers.ValidationError(
                    {'cliente': 'Tu cuenta no tiene un perfil de cliente asociado.'}
                )
            attrs['cliente'] = perfil
            cliente = perfil

        if not cliente:
            raise serializers.ValidationError({'cliente': 'El cliente es obligatorio.'})

        # RN-10: una sola evaluación por servicio/instalación (evita el error 500
        # de la restricción única y devuelve un 400 con mensaje claro).
        def ya_evaluado(clave):
            qs = EvaluacionServicio.objects.filter(cliente=cliente, **clave)
            if instancia:
                qs = qs.exclude(pk=instancia.pk)
            return qs.exists()

        if orden and ya_evaluado({'orden': orden}):
            raise serializers.ValidationError(
                {'error': 'Este servicio ya fue evaluado. Solo se permite una evaluación por servicio (RN-10).'}
            )
        if instalacion and ya_evaluado({'instalacion': instalacion}):
            raise serializers.ValidationError(
                {'error': 'Esta instalación ya fue evaluada. Solo se permite una evaluación por instalación (RN-10).'}
            )
        return attrs
