from django.contrib import admin

from apps.notificaciones.models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'usuario', 'tipo', 'leida', 'fecha']
    list_filter = ['tipo', 'leida', 'fecha']
    search_fields = ['titulo', 'mensaje', 'usuario__username']
