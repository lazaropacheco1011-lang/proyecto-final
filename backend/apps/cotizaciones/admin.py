from django.contrib import admin

from apps.cotizaciones.models import Cotizacion, CotizacionDetalle


class CotizacionDetalleInline(admin.TabularInline):
    model = CotizacionDetalle
    extra = 0


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ['numero', 'cliente', 'tecnico', 'fecha', 'subtotal', 'descuento', 'total', 'estado']
    list_filter = ['estado', 'fecha']
    search_fields = ['numero', 'cliente__nombre']
    inlines = [CotizacionDetalleInline]
    readonly_fields = ['numero', 'subtotal', 'total']
