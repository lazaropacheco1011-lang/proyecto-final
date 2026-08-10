from django.contrib import admin

from apps.evaluaciones.models import EvaluacionServicio


@admin.register(EvaluacionServicio)
class EvaluacionServicioAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'orden', 'instalacion', 'calificacion', 'fecha']
    list_filter = ['calificacion', 'fecha']
    search_fields = ['cliente__nombre', 'comentario']
