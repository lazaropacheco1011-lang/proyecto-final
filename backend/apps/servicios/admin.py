from django.contrib import admin

from apps.servicios.models import EstadoOrdenLog, MaterialUtilizado, OrdenServicio


class MaterialUtilizadoInline(admin.TabularInline):
    model = MaterialUtilizado
    extra = 0


class EstadoOrdenLogInline(admin.TabularInline):
    model = EstadoOrdenLog
    extra = 0
    readonly_fields = ['estado_anterior', 'estado_nuevo', 'usuario', 'comentario', 'fecha']
    can_delete = False


@admin.register(OrdenServicio)
class OrdenServicioAdmin(admin.ModelAdmin):
    list_display = [
        'numero', 'cliente', 'equipo', 'tecnico', 'tipo_servicio',
        'fecha', 'estado',
    ]
    list_filter = ['estado', 'tipo_servicio', 'fecha']
    search_fields = ['numero', 'cliente__nombre', 'equipo__numero_serie', 'problema_reportado']
    inlines = [MaterialUtilizadoInline, EstadoOrdenLogInline]
    readonly_fields = ['numero']


@admin.register(MaterialUtilizado)
class MaterialUtilizadoAdmin(admin.ModelAdmin):
    list_display = ['orden', 'material', 'cantidad', 'precio_unitario', 'subtotal']
    search_fields = ['orden__numero', 'material__nombre']


@admin.register(EstadoOrdenLog)
class EstadoOrdenLogAdmin(admin.ModelAdmin):
    list_display = ['orden', 'estado_anterior', 'estado_nuevo', 'usuario', 'fecha']
    list_filter = ['estado_nuevo', 'fecha']
    search_fields = ['orden__numero', 'usuario__username']
