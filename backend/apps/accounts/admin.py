from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import Supervisor, Tecnico, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'email', 'phone', 'role')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    list_display = ['user', 'telefono', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']


@admin.register(Tecnico)
class TecnicoAdmin(admin.ModelAdmin):
    list_display = ['user', 'supervisor', 'especialidad', 'telefono', 'disponible']
    list_filter = ['disponible', 'supervisor']
    search_fields = ['user__username', 'user__first_name', 'user__last_name']
