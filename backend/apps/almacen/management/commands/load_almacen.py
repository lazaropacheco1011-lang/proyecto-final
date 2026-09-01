"""Carga idempotente del catálogo de Almacén real del proyecto.

Lee ``data/almacen_data.json`` (generado a partir de la base SQLite local) y
sincroniza SOLO las tablas ``almacen_categoria`` y ``almacen_producto``.

Reglas de seguridad:
- Categorías: ``get_or_create`` por NOMBRE. No copia IDs de SQLite.
- Productos: ``update_or_create`` por NOMBRE; los IDs se regeneran en Postgres.
- ``categoria`` se mapea por NOMBRE (no por ID).
- En productos EXISTENTES nunca se modifican ``stock``, ``en_oferta`` ni
  ``precio_oferta`` (decisión del usuario): ``update_or_create`` solo actualiza
  categoría, descripción, precio, disponible, destacado e imagen corregida.
  Esos tres campos solo se asignan al CREAR un producto nuevo.
- Nunca borra nada. No usa --flush. No toca ninguna otra tabla.

Fotos de producto (regla permanente): las fotos reales/correctas nunca se
reemplazan por decisión propia. Solo se CORRIGEN casos concretos verificados:
  - Imágenes ``.svg`` genéricas del seed antiguo (p. ej. compresores.svg):
    se reemplazan por la foto real correspondiente de ``almacen_data.json``.
  - La ruta ``/media/...`` corrupta y verificada del producto
    "Aire acondicionado split 12.000 BTU": se corrige a la foto real definida
    en ``almacen_data.json``.
No se toca ninguna otra ruta ``/media/...`` ni imagen real existente sin
verificación previa. Los productos nuevos usan exactamente la imagen definida
en ``almacen_data.json``.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.almacen.models import Categoria, Producto

DATA_FILE = Path(__file__).resolve().parent.parent.parent / 'data' / 'almacen_data.json'


def _es_svg_roto(valor):
    """Indica si una imagen guardada es un ``.svg`` genérico del seed antiguo.

    Solo estos SVG se corrigen automáticamente. Cualquier otra ruta (incluidas
    las ``/media/...``) NO se considera rota sin verificación previa.
    """
    if not valor:
        return True
    return str(valor).strip().lower().endswith('.svg')


# Correcciones verificadas y explícitas de rutas incorrectas que NO son SVG.
# Solo se aplican al producto indicado (por nombre). El resto de imágenes,
# aunque estén en /media/, se dejan intactas salvo verificación previa.
IMAGENES_CORREGIR_ESPECIFICAS = {
    'Aire acondicionado split 12.000 BTU': '/assets/img/productos/aire-acondicionado.webp',
}


class Command(BaseCommand):
    help = 'Carga las categorías y productos del Almacén desde almacen_data.json.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not DATA_FILE.exists():
            self.stderr.write(f'No se encuentra el archivo de datos: {DATA_FILE}')
            return

        with open(DATA_FILE, encoding='utf-8') as f:
            data = json.load(f)

        categorias = data.get('categorias', [])
        productos = data.get('productos', [])

        # 1) Categorías por nombre
        cat_objects = {}
        for cat in categorias:
            obj, _ = Categoria.objects.get_or_create(
                nombre=cat['nombre'],
                defaults={
                    'descripcion': cat.get('descripcion', ''),
                    'icono': cat.get('icono', ''),
                    'orden': cat.get('orden', 0),
                },
            )
            cat_objects[cat['nombre']] = obj

        # 2) Productos por nombre, mapeando la categoría por nombre
        creados = 0
        actualizados = 0
        corregidos = 0
        for p in productos:
            categoria = cat_objects.get(p['categoria'])
            if categoria is None:
                self.stderr.write(
                    f"Producto '{p['nombre']}': categoría '{p['categoria']}' no existe. Se omite."
                )
                continue

            defaults = {
                'categoria': categoria,
                'descripcion': p.get('descripcion', ''),
                'precio': p.get('precio'),
                'disponible': bool(p.get('disponible', True)),
                'destacado': bool(p.get('destacado', False)),
            }

            existente = Producto.objects.filter(nombre=p['nombre']).first()

            # Regla permanente del usuario: en productos EXISTENTES nunca se
            # modifican stock, en_oferta ni precio_oferta. Esos campos solo se
            # asignan en el alta de productos NUEVOS.
            if existente is None:
                defaults.update({
                    'stock': p.get('stock', 0),
                    'en_oferta': bool(p.get('en_oferta', False)),
                    'precio_oferta': p.get('precio_oferta'),
                })

            # Imagen: en alta se usa la foto real del data. Si el producto ya
            # existe, solo se CORRIGE la imagen si está verificada como rota:
            #   - .svg genérico del seed antiguo (auto), o
            #   - una ruta /media/ incorrecta del listado explícito.
            # Cualquier otra imagen real existente se deja intacta.
            if p.get('imagen'):
                nombre = p['nombre']
                debe_corregir = False
                if existente is None:
                    debe_corregir = True  # alta -> usa la imagen real del data
                elif _es_svg_roto(existente.imagen):
                    debe_corregir = True  # svg genérico roto
                elif nombre in IMAGENES_CORREGIR_ESPECIFICAS and \
                        str(existente.imagen or '').strip().lower().startswith('/media/'):
                    debe_corregir = True  # ruta /media corrupta verificada

                if debe_corregir:
                    defaults['imagen'] = p['imagen']
                    if existente is not None:
                        corregidos += 1

            producto, created = Producto.objects.update_or_create(
                nombre=p['nombre'],
                defaults=defaults,
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Almacén sincronizado: {Categoria.objects.count()} categorías, '
            f'{Producto.objects.count()} productos (creados: {creados}, '
            f'actualizados: {actualizados}, imágenes corregidas: {corregidos}).'
        ))
