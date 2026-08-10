from rest_framework.routers import DefaultRouter

from apps.instalaciones.views import InstalacionViewSet

router = DefaultRouter()
router.register('instalaciones', InstalacionViewSet, basename='instalaciones')

urlpatterns = router.urls
