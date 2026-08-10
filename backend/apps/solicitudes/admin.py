from django.contrib import admin

from apps.solicitudes.models import SolicitudInstalacion


@admin.register(SolicitudInstalacion)
class SolicitudInstalacionAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'tipo_equipo_solicitado', 'prioridad', 'estado', 'fecha_solicitud']
    list_filter = ['prioridad', 'estado', 'fecha_solicitud']
    search_fields = ['cliente__nombre', 'tipo_equipo_solicitado', 'descripcion']
    date_hierarchy = 'fecha_solicitud'
