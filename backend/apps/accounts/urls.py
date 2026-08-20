from rest_framework.routers import DefaultRouter

from apps.accounts.views import SupervisorViewSet, TecnicoViewSet, UserViewSet

router = DefaultRouter()
router.register('usuarios', UserViewSet, basename='usuarios')
router.register('tecnicos', TecnicoViewSet, basename='tecnicos')
router.register('supervisores', SupervisorViewSet, basename='supervisores')

urlpatterns = router.urls
