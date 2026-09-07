"""Vistas del Almacén: vitrina pública de productos + gestión interna."""
from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.utils.text import get_valid_filename
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.almacen.models import Categoria, Producto
from apps.almacen.serializers import CategoriaSerializer, ProductoSerializer
from apps.core.permissions import ADMIN, ALMACEN, has_role
from apps.core.services import delete_or_conflict, register_audit, reject_if


# Extensiones por tipo de imagen REAL detectado por firma binaria: no se
# confía en el Content-Type declarado por el cliente (es manipulable).
IMAGEN_CONTENT_TYPES = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/avif': '.avif',
}
MAX_IMAGEN_SIZE = 5 * 1024 * 1024  # 5 MB


def _detectar_tipo_imagen(head):
    """Detecta el tipo de imagen real por magic bytes. Retorna el mime o None."""
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if head[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if head[:6] in (b'GIF87a', b'GIF89a'):
        return 'image/gif'
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'image/webp'
    if head[4:8] == b'ftyp' and b'avif' in head[:12]:
        return 'image/avif'
    return None


class AlmacenPermission(BasePermission):
    """Lectura pública (vitrina); escritura solo administrador o almacén."""

    message = 'Se requiere rol de administrador o almacén para modificar productos.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return has_role(request.user, ADMIN, ALMACEN)


class ProductoImagenUploadView(APIView):
    """Sube una imagen de producto al directorio MEDIA (``/media/productos/``).

    El panel (admin-dashboard) la usa desde "Editar Producto" para elegir la
    imagen desde el equipo sin digitar rutas. Devuelve la URL media lista
    para guardarse en ``Producto.imagen``.
    """
    permission_classes = [AlmacenPermission]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        archivo = request.FILES.get('imagen')
        if not archivo:
            return Response(
                {'error': 'No se recibió ningún archivo de imagen.'}, status=400,
            )
        head = archivo.read(16)
        archivo.seek(0)
        # Los SVG se rechazan: pueden contener <script> y se servirían en el
        # mismo origen (/media/), permitiendo XSS almacenado. Los SVG del
        # proyecto viven en /assets/ y se referencian por ruta en el panel.
        if b'<svg' in head.lower() or head.lstrip(b'\xef\xbb\xbf')[:4].lower() in (b'<svg', b'<?xm'):
            return Response(
                {'error': 'No se permiten archivos SVG por seguridad. '
                          'Usa PNG/JPG/WebP o indica una ruta de /assets.'},
                status=400,
            )
        mime = _detectar_tipo_imagen(head)
        if mime is None:
            return Response(
                {'error': 'El archivo no es una imagen válida.'}, status=400,
            )
        if archivo.size and archivo.size > MAX_IMAGEN_SIZE:
            return Response(
                {'error': 'La imagen supera el tamaño máximo de 5 MB.'}, status=400,
            )
        # Verificación con Pillow de que el archivo es una imagen decodificable.
        # AVIF se valida solo por firma (depende de libavif en Pillow).
        if mime != 'image/avif':
            try:
                from PIL import Image
                Image.open(archivo).verify()
                archivo.seek(0)
            except Exception:
                return Response(
                    {'error': 'El archivo no es una imagen válida.'}, status=400,
                )

        nombre = get_valid_filename(archivo.name or 'imagen')
        ext = IMAGEN_CONTENT_TYPES[mime]
        if not nombre.lower().endswith(ext):
            nombre = nombre + ext

        ruta_guardada = default_storage.save('productos/' + nombre, archivo)
        url = settings.MEDIA_URL + ruta_guardada
        return Response({
            'imagen': url,
            'url': url,
            'nombre': ruta_guardada.split('/')[-1],
        })


class CategoriaViewSet(viewsets.ModelViewSet):
    """Catálogo de categorías de productos (público)."""
    serializer_class = CategoriaSerializer
    permission_classes = [AlmacenPermission]
    pagination_class = None
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre', 'orden']

    def get_queryset(self):
        qs = Categoria.objects.all()
        user = self.request.user
        if not (user and user.is_authenticated and has_role(user, ADMIN, ALMACEN)):
            qs = qs.filter(productos__disponible=True)
        return qs.annotate(total_productos=Count('productos', distinct=True))

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='almacen.categoria')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'actualizar', obj, model_name='almacen.categoria')

    def perform_destroy(self, instance):
        if instance.productos.exists():
            raise PermissionDenied('No se puede eliminar una categoría que tiene productos asociados.')
        register_audit(self.request.user, 'eliminar', instance, model_name='almacen.categoria')
        instance.delete()


class ProductoViewSet(viewsets.ModelViewSet):
    """CRUD de productos. Lectura pública filtrada a productos disponibles."""
    STOCK_BAJO = 5
    queryset = Producto.objects.select_related('categoria').all()
    serializer_class = ProductoSerializer
    permission_classes = [AlmacenPermission]
    filterset_fields = ['categoria', 'disponible', 'destacado']
    search_fields = ['nombre', 'descripcion', 'categoria__nombre']
    ordering_fields = ['nombre', 'precio', 'stock', 'created_at', 'updated_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not (user and user.is_authenticated and has_role(user, ADMIN, ALMACEN)):
            qs = qs.filter(disponible=True)
        disp = self.request.query_params.get('disp')
        if disp == 'disponible':
            qs = qs.filter(disponible=True, stock__gt=0)
        elif disp == 'bajo':
            qs = qs.filter(disponible=True, stock__gt=0, stock__lte=self.STOCK_BAJO)
        elif disp == 'agotado':
            qs = qs.filter(Q(disponible=False) | Q(stock=0))
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='almacen.producto')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(
            self.request.user, 'actualizar', obj,
            model_name='almacen.producto', changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        reject_if(
            instance.items_orden.exists(),
            'No se puede eliminar el producto porque aparece en órdenes de la '
            'tienda que deben conservarse.',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='almacen.producto')
        delete_or_conflict(instance)
