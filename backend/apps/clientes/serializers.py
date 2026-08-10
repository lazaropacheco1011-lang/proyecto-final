from rest_framework import serializers

from apps.clientes.models import Cliente, DireccionInstalacion


class DireccionInstalacionSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)

    class Meta:
        model = DireccionInstalacion
        fields = [
            'id', 'cliente', 'cliente_nombre', 'etiqueta', 'direccion',
            'ciudad', 'referencia', 'latitud', 'longitud', 'principal',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClienteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email_contacto = serializers.CharField(source='user.email', read_only=True)
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)
    fecha_registro = serializers.DateTimeField(source='created_at', read_only=True)
    direcciones = DireccionInstalacionSerializer(many=True, read_only=True)
    total_equipos = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = [
            'id', 'user', 'username', 'tipo', 'nombre', 'apellidos',
            'nombre_completo', 'tipo_documento', 'tipo_documento_display',
            'documento_numero', 'email', 'email_contacto', 'telefono',
            'telefono_alternativo', 'direccion', 'ciudad', 'notas',
            'direcciones', 'total_equipos', 'fecha_registro', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'username', 'created_at', 'updated_at']
        extra_kwargs = {
            'documento_numero': {'validators': []},
        }

    def get_total_equipos(self, obj):
        return obj.equipos.count()

    def validate_documento_numero(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('El número de documento es obligatorio.')
        qs = Cliente.objects.filter(documento_numero__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('El número de documento ya está registrado.')
        return value

    def validate_email(self, value):
        qs = Cliente.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un cliente con ese correo.')
        return value

    def validate(self, attrs):
        tipo = attrs.get('tipo', getattr(self.instance, 'tipo', None) or Cliente.TIPO_PERSONA)
        tipo_documento = attrs.get(
            'tipo_documento',
            getattr(self.instance, 'tipo_documento', None),
        )
        if tipo == Cliente.TIPO_EMPRESA and tipo_documento not in ('rnc', 'nit', None):
            raise serializers.ValidationError({
                'tipo_documento': 'Para empresas el tipo de documento debe ser RNC o NIT.',
            })
        return attrs


class ClienteMinSerializer(serializers.ModelSerializer):
    """Representación ligera para listas de selección sin datos sensibles."""
    nombre_completo = serializers.CharField(read_only=True)
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)

    class Meta:
        model = Cliente
        fields = ['id', 'nombre_completo', 'tipo', 'tipo_documento', 'tipo_documento_display', 'ciudad']
