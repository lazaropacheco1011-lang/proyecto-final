from django.contrib import admin

from apps.core.models import AuditLog, Evidencia


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'model_name', 'object_repr', 'user', 'created_at']
    list_filter = ['action', 'model_name', 'created_at']
    search_fields = ['object_repr', 'user__username']
    date_hierarchy = 'created_at'


@admin.register(Evidencia)
class EvidenciaAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_type', 'object_id', 'fase', 'subido_por', 'created_at']
    list_filter = ['fase', 'content_type', 'created_at']
    search_fields = ['descripcion']
