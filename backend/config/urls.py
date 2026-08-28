"""URLs raíz del proyecto REFRIMASTE."""
from mimetypes import guess_type
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.generic import RedirectView

from config.settings import env_bool
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / 'frontend'


def serve_frontend_file(request, path=''):
    # 1) Resolver primero desde la URL completa del request
    #    (ej: /css/styles.css -> frontend/css/styles.css, /js/admin.js -> ...).
    rel_path = Path(request.path.lstrip('/') or '')
    if rel_path.is_absolute() or '..' in rel_path.parts:
        raise Http404

    target_path = FRONTEND_DIR / rel_path
    if not (target_path.exists() and target_path.is_file()):
        # 2) Respaldo: ruta explícita pasada por la vista
        #    (ej: index.html, admin-dashboard.html).
        if not path:
            target_path = FRONTEND_DIR / 'index.html'
        else:
            rel_path = Path(path)
            if rel_path.is_absolute() or '..' in rel_path.parts:
                raise Http404
            target_path = FRONTEND_DIR / rel_path
            if not (target_path.exists() and target_path.is_file()):
                raise Http404
    content_type, _ = guess_type(str(target_path))
    if not content_type:
        content_type = 'application/octet-stream'
    return FileResponse(target_path.open('rb'), content_type=content_type)


def frontend_home(request):
    return serve_frontend_file(request, 'index.html')


def admin_dashboard(request):
    return serve_frontend_file(request, 'admin-dashboard.html')


def productos_page(request):
    return serve_frontend_file(request, 'productos.html')


def carrito_page(request):
    return serve_frontend_file(request, 'carrito.html')


def checkout_page(request):
    return serve_frontend_file(request, 'checkout.html')


def confirmacion_page(request):
    return serve_frontend_file(request, 'confirmacion.html')


def mis_compras_page(request):
    return serve_frontend_file(request, 'mis-compras.html')


def mantenimiento_page(request):
    return serve_frontend_file(request, 'mantenimiento.html')


def reparaciones_page(request):
    return serve_frontend_file(request, 'reparaciones.html')


def detalle_servicio_page(request):
    return serve_frontend_file(request, 'detalle-servicio.html')


def paypal_aprobacion_page(request):
    return serve_frontend_file(request, 'paypal-aprobacion.html')


urlpatterns = [
    path('', frontend_home, name='home'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('productos/', productos_page, name='productos'),
    path('carrito/', carrito_page, name='carrito'),
    path('checkout/', checkout_page, name='checkout'),
    path('checkout/paypal/aprobar/', paypal_aprobacion_page, name='paypal_aprobacion'),
    path('checkout/exito/', confirmacion_page, name='confirmacion'),
    path('mis-compras/', mis_compras_page, name='mis_compras'),
    path('mantenimiento/', mantenimiento_page, name='mantenimiento'),
    path('reparaciones/', reparaciones_page, name='reparaciones'),
    path('servicio/', detalle_servicio_page, name='detalle_servicio'),
    path('css/<path:path>', serve_frontend_file),
    path('js/<path:path>', serve_frontend_file),
    path('assets/<path:path>', serve_frontend_file),
    path('img/<path:path>', serve_frontend_file),
    path('images/<path:path>', serve_frontend_file),

    # API
    path('api/auth/', include('apps.accounts.auth_urls')),
    path('api/', include('apps.core.urls')),
    path('api/', include('apps.accounts.urls')),
    path('api/', include('apps.clientes.urls')),
    path('api/', include('apps.solicitudes.urls')),
    path('api/', include('apps.equipos.urls')),
    path('api/', include('apps.instalaciones.urls')),
    path('api/', include('apps.servicios.urls')),
    path('api/', include('apps.mantenimientos.urls')),
    path('api/', include('apps.materiales.urls')),
    path('api/', include('apps.cotizaciones.urls')),
    path('api/', include('apps.pagos.urls')),
    path('api/', include('apps.notificaciones.urls')),
    path('api/', include('apps.evaluaciones.urls')),
    path('api/', include('apps.reportes.urls')),
    path('api/', include('apps.almacen.urls')),
    path('api/tienda/', include('apps.tienda.urls')),
]

# El admin de Django y la documentación de la API solo se exponen en
# desarrollo (o si se habilita explícitamente con DJANGO_ADMIN_ENABLED).
# En producción el panel de administración es el frontend admin-dashboard.
admin_enabled = settings.DEBUG or env_bool('DJANGO_ADMIN_ENABLED', False)
if admin_enabled:
    urlpatterns += [
        path('django-admin/', admin.site.urls),
        path('admin/', RedirectView.as_view(url='/admin-dashboard/', permanent=False), name='admin_redirect'),
        path('administrador', RedirectView.as_view(url='/admin-dashboard/', permanent=False), name='administrador_redirect'),
        path('administrador/', RedirectView.as_view(url='/admin-dashboard/', permanent=False), name='administrador_redirect_slash'),
        path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
        path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
