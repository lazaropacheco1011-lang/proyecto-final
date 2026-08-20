from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import Supervisor, Tecnico
from apps.clientes.models import Cliente
from apps.core.permissions import ADMIN, ALMACEN, CLIENTE, SUPERVISOR, TECNICO

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'role_display', 'phone', 'photo', 'full_name',
            'is_active', 'is_staff', 'date_joined', 'last_login',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'photo']
        extra_kwargs = {
            'username': {'help_text': 'Nombre de usuario único'},
        }

    def validate_username(self, value):
        if self.instance is None and User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('El nombre de usuario ya está en uso.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('El correo electrónico ya está registrado.')
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
    )
    role = serializers.ChoiceField(choices=User.Roles.choices, default=CLIENTE)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'first_name',
            'last_name', 'role', 'phone', 'is_active',
        ]

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('El nombre de usuario ya está en uso.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('El correo electrónico ya está registrado.')
        return value

    def validate_role(self, value):
        if value not in (ADMIN, SUPERVISOR, TECNICO, ALMACEN, CLIENTE):
            raise serializers.ValidationError('Rol inválido.')
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        if validated_data.get('role') == CLIENTE:
            Cliente.objects.create(
                user=user,
                nombre=user.first_name or user.username,
                apellidos=user.last_name,
                email=user.email,
                telefono=user.phone,
                tipo=Cliente.TIPO_PERSONA,
                tipo_documento='cc',
                documento_numero=f'DOC-{user.id}',
            )
        return user


class UserUpdateSerializer(UserCreateSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        validators=[validate_password],
        allow_blank=True,
    )

    class Meta(UserCreateSerializer.Meta):
        fields = [
            'id', 'username', 'email', 'password', 'first_name',
            'last_name', 'role', 'phone', 'is_active',
        ]

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class MeUpdateSerializer(UserUpdateSerializer):
    """Actualización del propio perfil: el usuario no puede cambiarse role ni is_active."""

    role = serializers.ChoiceField(choices=User.Roles.choices, read_only=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta(UserUpdateSerializer.Meta):
        fields = UserUpdateSerializer.Meta.fields


class MeProfileSerializer(serializers.ModelSerializer):
    """
    Perfil completo del usuario autenticado: datos de la cuenta, foto y los
    datos personales según el rol (cliente o técnico). Solo se actualiza el
    perfil del propio usuario; role e is_active nunca se pueden modificar aquí.
    """

    role_display = serializers.CharField(source='get_role_display', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    photo = serializers.ImageField(read_only=True)
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        validators=[validate_password],
    )

    # Datos del cliente (solo se aplican cuando el usuario tiene perfil de cliente)
    nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    apellidos = serializers.CharField(max_length=150, required=False, allow_blank=True)
    tipo_documento = serializers.ChoiceField(
        choices=Cliente.TIPO_DOCUMENTO_CHOICES, required=False,
    )
    documento_numero = serializers.CharField(max_length=30, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    telefono_alternativo = serializers.CharField(max_length=20, required=False, allow_blank=True)
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ciudad = serializers.CharField(max_length=100, required=False, allow_blank=True)

    # Datos del técnico (solo se aplican cuando el usuario tiene perfil de técnico)
    especialidad = serializers.CharField(max_length=150, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'phone',
            'role', 'role_display', 'full_name', 'photo', 'password',
            'nombre', 'apellidos', 'tipo_documento', 'documento_numero',
            'telefono', 'telefono_alternativo', 'direccion', 'ciudad',
            'especialidad',
        ]
        read_only_fields = ['id', 'username', 'role', 'role_display', 'full_name', 'photo']

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError('El correo electrónico ya está registrado.')
        return value

    def validate_documento_numero(self, value):
        value = (value or '').strip()
        if not value:
            return value
        qs = Cliente.objects.filter(documento_numero__iexact=value)
        if self.instance:
            perfil = getattr(self.instance, 'perfil_cliente', None)
            if perfil:
                qs = qs.exclude(pk=perfil.pk)
        if qs.exists():
            raise serializers.ValidationError('El número de documento ya está registrado.')
        return value

    def to_representation(self, instance):
        data = super().to_representation(instance)
        perfil_cliente = getattr(instance, 'perfil_cliente', None)
        perfil_tecnico = getattr(instance, 'perfil_tecnico', None)

        # Campos del cliente (vacíos si no aplican)
        for f in ('nombre', 'apellidos', 'tipo_documento', 'documento_numero',
                  'telefono', 'telefono_alternativo', 'direccion', 'ciudad'):
            if perfil_cliente:
                data[f] = getattr(perfil_cliente, f, '') or ''
            else:
                data[f] = ''

        # Campos del técnico (vacíos si no aplican)
        data['especialidad'] = ''
        if perfil_tecnico:
            data['especialidad'] = perfil_tecnico.especialidad or ''
            if not perfil_cliente:
                data['telefono'] = perfil_tecnico.telefono or ''
                data['direccion'] = perfil_tecnico.direccion or ''
        return data

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr in ('first_name', 'last_name', 'email', 'phone'):
            if attr in validated_data:
                setattr(instance, attr, validated_data.get(attr) or '')
        if password:
            instance.set_password(password)
        instance.save()

        perfil_cliente = getattr(instance, 'perfil_cliente', None)
        perfil_tecnico = getattr(instance, 'perfil_tecnico', None)
        if perfil_cliente:
            for field in ('nombre', 'apellidos', 'tipo_documento', 'documento_numero',
                          'telefono', 'telefono_alternativo', 'direccion', 'ciudad'):
                if field in validated_data:
                    setattr(perfil_cliente, field, validated_data.get(field) or '')
            perfil_cliente.save()
            # Mantiene el nombre visible en la cuenta sincronizado con el cliente.
            if 'nombre' in validated_data or 'apellidos' in validated_data:
                instance.first_name = perfil_cliente.nombre or instance.username
                instance.last_name = perfil_cliente.apellidos or ''
                instance.save()
        if perfil_tecnico:
            for field in ('especialidad', 'telefono', 'direccion'):
                if field in validated_data:
                    setattr(perfil_tecnico, field, validated_data.get(field) or '')
            perfil_tecnico.save()
        return instance


class RegisterSerializer(serializers.Serializer):
    """Registro público de usuarios (RF-01)."""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=20, allow_blank=True, required=False)
    role = serializers.ChoiceField(
        choices=[c for c in User.Roles.choices if c[0] in (CLIENTE, TECNICO)],
        default=CLIENTE,
        help_text='Solo se permiten los roles cliente o técnico en el registro público.',
    )
    # Datos de cliente
    nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    apellidos = serializers.CharField(max_length=150, required=False, allow_blank=True)
    tipo = serializers.ChoiceField(choices=Cliente.TIPO_CHOICES, required=False)
    tipo_documento = serializers.ChoiceField(
        choices=Cliente.TIPO_DOCUMENTO_CHOICES, required=False, default='cc'
    )
    documento = serializers.CharField(max_length=30, required=False, allow_blank=True)
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True)
    ciudad = serializers.CharField(max_length=100, required=False, allow_blank=True)
    telefono_alternativo = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('El nombre de usuario ya está en uso.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('El correo electrónico ya está registrado.')
        return value

    def validate_documento(self, value):
        value = (value or '').strip()
        if value and Cliente.objects.filter(documento_numero__iexact=value).exists():
            raise serializers.ValidationError('El número de documento ya está registrado.')
        return value

    def validate(self, attrs):
        if attrs.get('role', CLIENTE) == CLIENTE:
            if not (attrs.get('documento') or '').strip():
                raise serializers.ValidationError({
                    'documento': 'El número de documento es obligatorio.',
                })
            tipo_documento = attrs.get('tipo_documento', 'cc')
            tipo = attrs.get('tipo') or (
                Cliente.TIPO_EMPRESA if tipo_documento == 'rnc' else Cliente.TIPO_PERSONA
            )
            if tipo == Cliente.TIPO_EMPRESA and tipo_documento not in ('rnc', 'nit'):
                raise serializers.ValidationError({
                    'tipo_documento': 'Para empresas el tipo de documento debe ser RNC o NIT.',
                })
            attrs['tipo'] = tipo
        return attrs

    def create(self, validated_data):
        role = validated_data.get('role', CLIENTE)
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone=validated_data.get('phone', ''),
            role=role,
        )
        user.set_password(validated_data['password'])
        user.save()

        if role == CLIENTE:
            Cliente.objects.create(
                user=user,
                nombre=validated_data.get('nombre') or user.first_name or user.username,
                apellidos=validated_data.get('apellidos') or user.last_name,
                tipo=validated_data.get('tipo', Cliente.TIPO_PERSONA),
                tipo_documento=validated_data.get('tipo_documento', 'cc'),
                documento_numero=validated_data.get('documento') or f'DOC-{user.id}',
                email=user.email,
                telefono=user.phone,
                telefono_alternativo=validated_data.get('telefono_alternativo', ''),
                direccion=validated_data.get('direccion', ''),
                ciudad=validated_data.get('ciudad', ''),
            )
        return user


class LoginSerializer(serializers.Serializer):
    """Inicio de sesión con JWT (RF-02)."""
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(style={'input_type': 'password'})

    def validate(self, attrs):
        from django.contrib.auth import authenticate

        username = attrs.get('username') or ''
        email = attrs.get('email') or ''
        if not username and not email:
            raise serializers.ValidationError('Debes indicar usuario o correo electrónico.')

        user = None
        if email:
            try:
                user = User.objects.get(email__iexact=email)
            except User.DoesNotExist:
                user = None
            if user:
                user = authenticate(username=user.username, password=attrs['password'])
        if user is None and username:
            user = authenticate(username=username, password=attrs['password'])

        if not user:
            raise serializers.ValidationError('Credenciales inválidas.')
        if not user.is_active:
            raise serializers.ValidationError('El usuario está inactivo.')

        attrs['user'] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text='Refresh token que se desea invalidar.')


class PasswordRecoverySerializer(serializers.Serializer):
    """Solicitud de enlace de recuperación por correo (respuesta genérica)."""
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirma la recuperación: token + nueva contraseña (un solo uso)."""
    token = serializers.CharField(help_text='Token recibido por correo.')
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password2 = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                'password2': 'Las contraseñas no coinciden.',
            })
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """Cambio de contraseña del usuario autenticado (pide la contraseña actual)."""
    password_actual = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )
    nueva_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    confirmar_nueva_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        user = self.context['user']
        if not user.check_password(attrs['password_actual']):
            raise serializers.ValidationError({
                'password_actual': 'La contraseña actual es incorrecta.',
            })
        if attrs['nueva_password'] != attrs['confirmar_nueva_password']:
            raise serializers.ValidationError({
                'confirmar_nueva_password': 'Las contraseñas no coinciden.',
            })
        return attrs


class TecnicoSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    nombre = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    rol = serializers.CharField(source='user.get_role_display', read_only=True)
    supervisor_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Tecnico
        fields = [
            'id', 'user', 'username', 'nombre', 'email', 'rol',
            'supervisor', 'supervisor_nombre',
            'especialidad', 'telefono', 'direccion', 'disponible',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'username', 'nombre', 'email', 'rol',
            'supervisor_nombre', 'created_at', 'updated_at',
        ]
        extra_kwargs = {'telefono': {'allow_blank': True}}

    def get_supervisor_nombre(self, obj):
        if obj.supervisor and obj.supervisor.user:
            return obj.supervisor.user.get_full_name() or obj.supervisor.user.username
        return ''

    def validate_user(self, value):
        if value and value.role != 'tecnico':
            raise serializers.ValidationError('El usuario debe tener el rol de técnico.')
        return value


class SupervisorSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    nombre = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    rol = serializers.CharField(source='user.get_role_display', read_only=True)
    tecnicos_count = serializers.SerializerMethodField()

    class Meta:
        model = Supervisor
        fields = [
            'id', 'user', 'username', 'nombre', 'email', 'rol',
            'telefono', 'tecnicos_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'username', 'nombre', 'email', 'rol',
            'tecnicos_count', 'created_at', 'updated_at',
        ]

    def get_tecnicos_count(self, obj):
        return obj.tecnicos.count()
