from django.contrib import admin

from apps.tienda.models import Orden, OrdenEstadoLog, OrdenItem, PagoTienda


class OrdenItemInline(admin.TabularInline):
    model = OrdenItem
    extra = 0
    readonly_fields = ['producto', 'nombre', 'imagen', 'precio_unitario', 'cantidad', 'subtotal']


class PagoTiendaInline(admin.TabularInline):
    model = PagoTienda
    extra = 0
    readonly_fields = [
        'metodo', 'estado', 'monto', 'moneda', 'referencia',
        'ultimos_digitos', 'marca_tarjeta', 'detalle', 'created_at',
    ]


class OrdenEstadoLogInline(admin.TabularInline):
    model = OrdenEstadoLog
    extra = 0
    readonly_fields = ['estado_anterior', 'estado_nuevo', 'usuario', 'comentario', 'fecha']


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre_cliente', 'email', 'total', 'estado', 'metodo_pago', 'estado_pago', 'created_at']
    list_filter = ['estado', 'created_at']
    search_fields = ['numero', 'nombre_cliente', 'email', 'cliente__nombre']
    readonly_fields = [
        'numero', 'subtotal', 'envio', 'descuento', 'total', 'moneda',
        'cliente', 'created_at', 'updated_at',
    ]
    inlines = [OrdenItemInline, PagoTiendaInline, OrdenEstadoLogInline]


@admin.register(PagoTienda)
class PagoTiendaAdmin(admin.ModelAdmin):
    list_display = ['id', 'orden', 'metodo', 'monto', 'estado', 'referencia', 'ultimos_digitos', 'created_at']
    list_filter = ['metodo', 'estado']
    search_fields = ['orden__numero', 'referencia']
    readonly_fields = ['ultimos_digitos', 'marca_tarjeta', 'detalle']
