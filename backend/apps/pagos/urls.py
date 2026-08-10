from rest_framework.routers import DefaultRouter

from apps.pagos.views import FacturaViewSet, PagoViewSet

router = DefaultRouter()
router.register('pagos', PagoViewSet, basename='pagos')
router.register('facturas', FacturaViewSet, basename='facturas')

urlpatterns = router.urls
