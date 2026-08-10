from django.apps import AppConfig


class ServiciosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.servicios'
    verbose_name = 'Órdenes de servicio'

    def ready(self):
        from apps.servicios import signals  # noqa: F401
