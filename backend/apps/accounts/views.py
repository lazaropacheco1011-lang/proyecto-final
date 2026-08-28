from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import get_valid_filename
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.models import Supervisor, Tecnico
from apps.accounts.services import (
    CorreoNoEnviado,
    buscar_token,
    enviar_correo_bienvenida,
    enviar_correo_recuperacion,
    revocar_sesiones,
)
from apps.accounts.serializers import (
    LoginSerializer,
    LogoutSerializer,
    MeProfileSerializer,
    MeUpdateSerializer,
    PasswordChangeSerializer,
    PasswordRecoverySerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    SupervisorSerializer,
    TecnicoMinSerializer,
    TecnicoSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.core.permissions import (
    ADMIN,
    ALMACEN,
    CLIENTE,
    SUPERVISOR,
    TECNICO,
    has_role,
    is_admin,
    is_staff_role,
)
from apps.core.services import register_audit

User = get_user_model()

# Tipos de imagen aceptados para la foto de perfil y tamaño máximo.
PERFIL_IMAGEN_CONTENT_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/avif': '.avif',
}
MAX_FOTO_PERFIL_SIZE = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
def build_token_payload(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': UserSerializer(user).data,
    }


class RegisterView(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """Registro de usuarios (cliente o técnico)."""
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        register_audit(user, 'crear', user, model_name='accounts.user', object_repr=str(user))
        if user.is_cliente:
            enviar_correo_bienvenida(user)
        data = build_token_payload(user)
        return Response(
            {'message': 'Usuario registrado correctamente.', **data},
            status=status.HTTP_201_CREATED,
        )


class LoginView(viewsets.GenericViewSet):
    """Inicio de sesión: devuelve access, refresh y datos del usuario."""
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'auth'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        register_audit(
            user, 'iniciar_sesion', user, model_name='accounts.user',
            object_repr=str(user),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return Response(
            {'message': 'Inicio de sesión exitoso.', **build_token_payload(user)},
            status=status.HTTP_200_OK,
        )


class LogoutView(viewsets.GenericViewSet):
    """Cierre de sesión: invalida el refresh token (lista negra)."""
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'message': 'Se requiere el campo refresh.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except (TokenError, InvalidToken, AttributeError) as exc:
            return Response(
                {'message': f'Token de refresco inválido: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        register_audit(
            request.user, 'cerrar_sesion', request.user, model_name='accounts.user'
        )
        return Response({'message': 'Sesión cerrada correctamente.'}, status=status.HTTP_200_OK)


class RefreshView(TokenRefreshView):
    """Renueva el access token a partir del refresh token."""


class PasswordSolicitudThrottle(SimpleRateThrottle):
    """Limita las solicitudes de enlace de recuperación por IP."""
    scope = 'password'

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PasswordRestablecerThrottle(SimpleRateThrottle):
    """Limita los intentos de restablecer la contraseña por IP."""
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        ident = request.user.pk if request.user.is_authenticated else self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class PasswordView(viewsets.GenericViewSet):
    """Recuperación y cambio de contraseña (los tres roles)."""

    permission_classes = [IsAuthenticated]

    @action(
        detail=False, methods=['post'], url_path='recuperar',
        permission_classes=[AllowAny], authentication_classes=[],
        throttle_classes=[PasswordSolicitudThrottle],
    )
    def recuperar(self, request, *args, **kwargs):
        """Solicita un enlace de recuperación al correo del usuario.

        La respuesta es genérica para no revelar si el correo está registrado.
        """
        serializer = PasswordRecoverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            enviar_correo_recuperacion(serializer.validated_data['email'])
        except CorreoNoEnviado:
            return Response(
                {'message': 'No se pudo enviar el correo en este momento. '
                            'Inténtalo de nuevo más tarde.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            'message': 'Si el correo está registrado, recibirás un enlace '
                       'para restablecer tu contraseña.',
        })

    @action(
        detail=False, methods=['post'], url_path='restablecer',
        permission_classes=[AllowAny], authentication_classes=[],
        throttle_classes=[PasswordRestablecerThrottle],
    )
    def restablecer(self, request, *args, **kwargs):
        """Restablece la contraseña con un token válido (un solo uso)."""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = buscar_token(serializer.validated_data['token'])
        if token is None:
            return Response(
                {'error': 'El enlace es inválido o ya fue utilizado. Solicita uno nuevo.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = token.user
        user.set_password(serializer.validated_data['password'])
        user.save(update_fields=['password'])
        token.used_at = timezone.now()
        token.save(update_fields=['used_at'])
        revocar_sesiones(user)
        register_audit(user, 'restablecer_contraseña', user, model_name='accounts.user')
        return Response({
            'message': 'Contraseña restablecida correctamente. '
                       'Ya puedes iniciar sesión con tu nueva contraseña.',
        })

    @action(detail=False, methods=['post'], url_path='cambiar')
    def cambiar(self, request, *args, **kwargs):
        """Cambia la contraseña del usuario autenticado (pide la actual)."""
        user = request.user
        serializer = PasswordChangeSerializer(
            data=request.data, context={'user': user},
        )
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data['nueva_password'])
        user.save(update_fields=['password'])
        revocar_sesiones(user)
        register_audit(user, 'cambiar_contraseña', user, model_name='accounts.user')
        return Response({
            'message': 'Contraseña cambiada correctamente. '
                       'Vuelve a iniciar sesión con tu nueva contraseña.',
        })


class MeView(viewsets.GenericViewSet):
    """Perfil del usuario autenticado."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def list(self, request, *args, **kwargs):
        return Response({'user': UserSerializer(request.user).data})

    def partial_update(self, request, *args, **kwargs):
        for field in ('role', 'is_active', 'is_staff'):
            if field in request.data:
                raise PermissionDenied(f'No puedes modificar el campo {field}.')
        user = request.user
        serializer = MeUpdateSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        register_audit(user, 'actualizar', user, model_name='accounts.user')
        return Response({'user': UserSerializer(user).data})

    @action(detail=False, methods=['get', 'patch'], url_path='perfil')
    def perfil(self, request, *args, **kwargs):
        """Obtiene o actualiza el perfil completo del usuario autenticado.

        La foto de perfil se gestiona aparte con ``foto`` (multipart).
        Los campos ``role`` e ``is_active`` no se pueden modificar aquí.
        """
        user = request.user
        if request.method == 'GET':
            return Response({'perfil': MeProfileSerializer(user).data})
        for field in ('role', 'is_active', 'is_staff'):
            if field in request.data:
                raise PermissionDenied(f'No puedes modificar el campo {field}.')
        serializer = MeProfileSerializer(
            user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        register_audit(user, 'actualizar', user, model_name='accounts.user')
        return Response({
            'message': 'Perfil actualizado correctamente.',
            'perfil': MeProfileSerializer(user).data,
        })

    @action(detail=False, methods=['post'], url_path='foto')
    def foto(self, request, *args, **kwargs):
        """Sube, reemplaza o elimina la foto de perfil del usuario autenticado.

        Subida:  ``POST multipart`` con el campo ``foto`` (imagen ≤ 5 MB).
        Borrado: ``POST`` JSON con ``{"eliminar": true}`` (restablece el avatar).
        """
        user = request.user
        if request.data.get('eliminar') in ('true', '1', True):
            if user.photo:
                user.photo.delete(save=True)
                register_audit(user, 'eliminar', user, model_name='accounts.user')
            return Response({
                'message': 'Foto de perfil eliminada.',
                'user': UserSerializer(user).data,
            })

        archivo = request.FILES.get('foto')
        if not archivo:
            return Response(
                {'error': 'No se recibió ninguna imagen (campo "foto").'}, status=400,
            )
        content_type = (archivo.content_type or '').lower()
        if content_type not in PERFIL_IMAGEN_CONTENT_TYPES:
            return Response(
                {'error': 'El archivo no es una imagen válida (JPG, PNG, GIF, WEBP o AVIF).'},
                status=400,
            )
        if archivo.size and archivo.size > MAX_FOTO_PERFIL_SIZE:
            return Response(
                {'error': 'La imagen supera el tamaño máximo de 5 MB.'}, status=400,
            )
        try:
            from PIL import Image
            imagen = Image.open(archivo)
            imagen.verify()
        except Exception:
            return Response(
                {'error': 'El archivo no es una imagen válida.'}, status=400,
            )
        archivo.seek(0)

        if user.photo:
            user.photo.delete(save=False)
        import uuid
        nombre = get_valid_filename(archivo.name or 'foto')
        ext = PERFIL_IMAGEN_CONTENT_TYPES[content_type]
        if not nombre.lower().endswith(ext):
            nombre += ext
        # Nombre único para que al reemplazar la foto cambie la URL.
        nombre = f'{uuid.uuid4().hex}_{nombre}'
        user.photo.save(nombre, archivo, save=True)
        register_audit(user, 'actualizar', user, model_name='accounts.user')
        return Response({
            'message': 'Foto de perfil actualizada.',
            'user': UserSerializer(user).data,
        })


# ---------------------------------------------------------------------------
# Administración de usuarios y técnicos
# ---------------------------------------------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    """CRUD de usuarios (administradores) y consulta para personal interno."""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_fields = ['role', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    ordering_fields = ['date_joined', 'username', 'role']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, SUPERVISOR):
            return qs.filter(role=TECNICO, perfil_tecnico__supervisor__user=user)
        if has_role(user, TECNICO):
            return qs.filter(pk=user.pk)
        return qs

    def get_permissions(self):
        if self.action in ('create', 'destroy', 'update', 'partial_update'):
            return [perm() for perm in (IsAdminWriteOnly,)]
        return [perm() for perm in (IsStaffReadOnly,)]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return UserUpdateSerializer if self.action != 'create' else UserCreateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        register_audit(self.request.user, 'crear', user, model_name='accounts.user')

    def perform_update(self, serializer):
        instance = serializer.instance
        user = self.request.user
        new_role = serializer.validated_data.get('role')
        if instance == user and new_role and new_role != user.role:
            raise PermissionDenied('No puedes cambiar tu propio rol.')
        if (
            new_role
            and instance.role == ADMIN
            and new_role != ADMIN
            and User.objects.filter(role=ADMIN).count() <= 1
        ):
            raise PermissionDenied('Debe existir al menos un administrador en el sistema.')
        user_updated = serializer.save()
        register_audit(
            self.request.user, 'actualizar', user_updated, model_name='accounts.user',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise PermissionDenied('No puedes eliminar tu propia cuenta.')
        if (
            instance.role == ADMIN
            and User.objects.filter(role=ADMIN).count() <= 1
        ):
            raise PermissionDenied('Debe existir al menos un administrador en el sistema.')
        register_audit(self.request.user, 'eliminar', instance, model_name='accounts.user')
        instance.delete()

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def roles(self, request):
        """Devuelve los roles disponibles del sistema."""
        return Response([{'value': c[0], 'label': c[1]} for c in User.Roles.choices])


class IsAdminWriteOnly(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsStaffReadOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_staff_role(request.user))


class TecnicoViewSet(viewsets.ModelViewSet):
    """Perfiles de técnicos y su disponibilidad."""
    queryset = Tecnico.objects.select_related('user', 'supervisor', 'supervisor__user').all()
    serializer_class = TecnicoSerializer
    filterset_fields = ['disponible', 'user__role', 'supervisor']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'especialidad']
    ordering_fields = ['user__first_name']

    def get_permissions(self):
        if self.action in ('create', 'destroy', 'update', 'partial_update'):
            return [perm() for perm in (IsAdminOrSupervisorWrite,)]
        return [perm() for perm in (IsTecnicoRead,)]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, TECNICO):
            return qs.filter(user=user)
        if has_role(user, SUPERVISOR):
            return qs
        return qs

    def perform_create(self, serializer):
        tecnico = serializer.save()
        register_audit(self.request.user, 'crear', tecnico, model_name='accounts.tecnico')

    def perform_update(self, serializer):
        tecnico = serializer.save()
        register_audit(self.request.user, 'actualizar', tecnico, model_name='accounts.tecnico')

    def perform_destroy(self, instance):
        register_audit(self.request.user, 'eliminar', instance, model_name='accounts.tecnico')
        usuario = instance.user
        instance.delete()
        if usuario and usuario.pk and usuario != self.request.user:
            usuario.delete()

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Lista ligera de técnicos para campos de selección."""
        qs = self.get_queryset().order_by('user__first_name', 'user__last_name')
        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
                | Q(user__username__icontains=search)
                | Q(especialidad__icontains=search)
            )
        return Response(TecnicoMinSerializer(qs[:200], many=True).data)


class SupervisorViewSet(viewsets.ModelViewSet):
    """CRUD de supervisores."""
    queryset = Supervisor.objects.select_related('user').all()
    serializer_class = SupervisorSerializer
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
    ordering_fields = ['user__first_name', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'destroy', 'update', 'partial_update'):
            return [perm() for perm in (IsAdminWriteOnly,)]
        return [perm() for perm in (IsStaffReadOnly,)]

    def perform_create(self, serializer):
        supervisor = serializer.save()
        register_audit(self.request.user, 'crear', supervisor, model_name='accounts.supervisor')

    def perform_update(self, serializer):
        supervisor = serializer.save()
        register_audit(self.request.user, 'actualizar', supervisor, model_name='accounts.supervisor')

    def perform_destroy(self, instance):
        register_audit(self.request.user, 'eliminar', instance, model_name='accounts.supervisor')
        usuario = instance.user
        instance.delete()
        if usuario and usuario.pk and usuario != self.request.user:
            usuario.delete()


class IsAdminOrSupervisorWrite(BasePermission):
    def has_permission(self, request, view):
        return has_role(request.user, ADMIN, SUPERVISOR)


class IsTecnicoRead(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and has_role(request.user, ADMIN, SUPERVISOR, TECNICO)
        )
