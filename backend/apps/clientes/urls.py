from rest_framework.routers import DefaultRouter

from apps.clientes.views import ClienteViewSet, DireccionInstalacionViewSet

router = DefaultRouter()
router.register('clientes', ClienteViewSet, basename='clientes')
router.register('direcciones', DireccionInstalacionViewSet, basename='direcciones')

urlpatterns = router.urls
