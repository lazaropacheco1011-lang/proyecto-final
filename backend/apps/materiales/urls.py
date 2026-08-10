from rest_framework.routers import DefaultRouter

from apps.materiales.views import MaterialViewSet, MovimientoInventarioViewSet

router = DefaultRouter()
router.register('materiales', MaterialViewSet, basename='materiales')
router.register('movimientos', MovimientoInventarioViewSet, basename='movimientos')

urlpatterns = router.urls
