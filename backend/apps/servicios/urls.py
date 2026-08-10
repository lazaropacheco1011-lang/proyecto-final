from rest_framework.routers import DefaultRouter

from apps.servicios.views import (
    MaterialUtilizadoViewSet,
    OrdenServicioViewSet,
    VisitaTecnicaViewSet,
)

router = DefaultRouter()
router.register('servicios', OrdenServicioViewSet, basename='servicios')
router.register('servicios-materiales', MaterialUtilizadoViewSet, basename='servicios-materiales')
router.register('visitas', VisitaTecnicaViewSet, basename='visitas')

urlpatterns = router.urls
