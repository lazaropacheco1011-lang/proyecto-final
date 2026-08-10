from django.contrib import admin

from apps.mantenimientos.models import Mantenimiento


@admin.register(Mantenimiento)
class MantenimientoAdmin(admin.ModelAdmin):
    list_display = [
        'equipo', 'cliente', 'tecnico', 'tipo', 'fecha',
        'proxima_fecha', 'estado', 'costo',
    ]
    list_filter = ['tipo', 'estado', 'fecha']
    search_fields = ['equipo__numero_serie', 'equipo__marca', 'cliente__nombre']
    date_hierarchy = 'fecha'
