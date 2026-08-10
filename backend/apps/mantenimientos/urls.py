from rest_framework.routers import DefaultRouter

from apps.mantenimientos.views import MantenimientoViewSet

router = DefaultRouter()
router.register('mantenimientos', MantenimientoViewSet, basename='mantenimientos')

urlpatterns = router.urls
