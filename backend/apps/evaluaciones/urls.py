from rest_framework.routers import DefaultRouter

from apps.evaluaciones.views import EvaluacionServicioViewSet

router = DefaultRouter()
router.register('evaluaciones', EvaluacionServicioViewSet, basename='evaluaciones')

urlpatterns = router.urls
