from django.contrib import admin

from apps.clientes.models import Cliente, DireccionInstalacion


class DireccionInstalacionInline(admin.TabularInline):
    model = DireccionInstalacion
    extra = 0


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'apellidos', 'tipo', 'documento_numero', 'email', 'telefono', 'ciudad']
    list_filter = ['tipo', 'tipo_documento', 'ciudad']
    search_fields = ['nombre', 'apellidos', 'documento_numero', 'email', 'telefono']
    inlines = [DireccionInstalacionInline]


@admin.register(DireccionInstalacion)
class DireccionInstalacionAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'etiqueta', 'direccion', 'ciudad', 'principal']
    list_filter = ['principal', 'ciudad']
    search_fields = ['direccion', 'ciudad', 'cliente__nombre']
