from django.contrib import admin

from apps.pagos.models import Factura, Pago


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ['id', 'cliente', 'orden', 'instalacion', 'monto', 'metodo', 'fecha', 'estado']
    list_filter = ['metodo', 'estado', 'fecha']
    search_fields = ['cliente__nombre', 'referencia']


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'cliente', 'orden', 'fecha', 'subtotal', 'iva', 'total']
    list_filter = ['fecha']
    search_fields = ['numero', 'cliente__nombre']
    filter_horizontal = ['pagos']
    readonly_fields = ['numero']
