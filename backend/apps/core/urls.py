from rest_framework.routers import DefaultRouter

from apps.core.views import AuditLogViewSet, EvidenciaViewSet, FirmaViewSet

router = DefaultRouter()
router.register('evidencias', EvidenciaViewSet, basename='evidencias')
router.register('firmas', FirmaViewSet, basename='firmas')
router.register('auditoria', AuditLogViewSet, basename='auditoria')

urlpatterns = router.urls
