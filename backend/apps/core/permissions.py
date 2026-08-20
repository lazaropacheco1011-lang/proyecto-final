"""Permisos personalizados por rol (RNF-03, RN-08)."""
from rest_framework.permissions import SAFE_METHODS, BasePermission

ADMIN = 'administrador'
SUPERVISOR = 'supervisor'
TECNICO = 'tecnico'
ALMACEN = 'almacen'
CLIENTE = 'cliente'

ADMIN_ROLES = (ADMIN,)


def has_role(user, *roles):
    return bool(user and user.is_authenticated and getattr(user, 'role', None) in roles)


def is_admin(user):
    return has_role(user, ADMIN)


def is_supervisor(user):
    return has_role(user, SUPERVISOR)


def is_staff_role(user):
    """Roles internos de la empresa (no clientes)."""
    return has_role(user, ADMIN, SUPERVISOR, TECNICO, ALMACEN)


def get_supervisor_tecnico_ids(user):
    """Devuelve los IDs de los técnicos que gestiona el supervisor dado."""
    perfil = getattr(user, 'perfil_supervisor', None)
    if not perfil:
        return []
    return list(perfil.tecnicos.values_list('user_id', flat=True))


class IsAdmin(BasePermission):
    message = 'Solo los administradores pueden realizar esta acción.'

    def has_permission(self, request, view):
        return is_admin(request.user)


class IsAdminOrReadOnly(BasePermission):
    message = 'Solo los administradores pueden modificar este recurso.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return is_admin(request.user)


class IsAdminOrSupervisor(BasePermission):
    message = 'Se requiere rol de administrador o supervisor.'

    def has_permission(self, request, view):
        return has_role(request.user, ADMIN, SUPERVISOR)


class IsAdminOrAlmacen(BasePermission):
    message = 'Se requiere rol de administrador o almacén.'

    def has_permission(self, request, view):
        return has_role(request.user, ADMIN, ALMACEN)


class IsStaffOrAdmin(BasePermission):
    """Lectura para personal interno; escritura solo administrador."""
    message = 'No tienes permisos suficientes.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return is_staff_role(user) or is_admin(user)
        return is_admin(user)


class IsOwnerOrAdmin(BasePermission):
    """
    Permite el acceso total a administradores/supervisores y a clientes
    únicamente sobre sus propios registros.
    """
    message = 'Solo puedes acceder a tus propios registros.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_admin(user) or has_role(user, SUPERVISOR):
            return True
        owner = getattr(obj, 'user', None) or getattr(getattr(obj, 'cliente', None), 'user', None)
        return bool(owner and owner == user)


class IsAssignedTecnicoOrStaff(BasePermission):
    """
    Permite a un técnico operar únicamente sobre registros asignados.
    """
    message = 'Esta orden/instalación no está asignada a ti.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_admin(user) or has_role(user, SUPERVISOR):
            return True
        tecnico = getattr(obj, 'tecnico', None)
        if not tecnico:
            return False
        return bool(getattr(tecnico, 'user_id', None) == user.id)


class NoTecnico(BasePermission):
    """Bloquea acceso a técnicos. Para endpoints financieros."""
    message = 'Los técnicos no tienen acceso a esta información.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and not has_role(request.user, TECNICO))
