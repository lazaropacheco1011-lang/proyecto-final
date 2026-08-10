from rest_framework.routers import DefaultRouter

from apps.accounts.views import TecnicoViewSet, UserViewSet

router = DefaultRouter()
router.register('usuarios', UserViewSet, basename='usuarios')
router.register('tecnicos', TecnicoViewSet, basename='tecnicos')

urlpatterns = router.urls
