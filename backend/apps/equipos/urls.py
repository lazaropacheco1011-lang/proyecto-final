from rest_framework.routers import DefaultRouter

from apps.equipos.views import EquipoViewSet, TipoEquipoViewSet

router = DefaultRouter()
router.register('equipos', EquipoViewSet, basename='equipos')
router.register('tipos-equipo', TipoEquipoViewSet, basename='tipos-equipo')

urlpatterns = router.urls
