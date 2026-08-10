from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.tienda.views import (
    AprobarPayPalView,
    CrearOrdenBilleteraView,
    CrearOrdenPayPalView,
    CrearOrdenTarjetaView,
    OrdenPublicaDetailView,
    OrdenViewSet,
    TiendaConfigView,
)

router = DefaultRouter()
router.register('ordenes', OrdenViewSet, basename='tienda-ordenes')

urlpatterns = [
    path('config/', TiendaConfigView.as_view(), name='tienda-config'),
    path('pagos/tarjeta/', CrearOrdenTarjetaView.as_view(), name='tienda-pago-tarjeta'),
    path('pagos/paypal/crear/', CrearOrdenPayPalView.as_view(), name='tienda-pago-paypal-crear'),
    path('pagos/paypal/aprobar/', AprobarPayPalView.as_view(), name='tienda-pago-paypal-aprobar'),
    path('pagos/billetera/', CrearOrdenBilleteraView.as_view(), name='tienda-pago-billetera'),
    path('ordenes/p/<str:numero>/', OrdenPublicaDetailView.as_view(), name='tienda-orden-publica'),
] + router.urls
