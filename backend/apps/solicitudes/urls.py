from rest_framework.routers import DefaultRouter

from apps.solicitudes.views import SolicitudInstalacionViewSet

router = DefaultRouter()
router.register('solicitudes', SolicitudInstalacionViewSet, basename='solicitudes')

urlpatterns = router.urls
