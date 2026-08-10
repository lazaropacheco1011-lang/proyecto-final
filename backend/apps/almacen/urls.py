from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.almacen.views import CategoriaViewSet, ProductoImagenUploadView, ProductoViewSet

router = DefaultRouter()
router.register('productos', ProductoViewSet, basename='productos')
router.register('categorias', CategoriaViewSet, basename='categorias')

urlpatterns = [
    # Debe declararse antes de las rutas del router para no ser capturada
    # por la ruta de detalle de producto (pk).
    path('productos/subir-imagen/', ProductoImagenUploadView.as_view(), name='producto-imagen-upload'),
] + router.urls
