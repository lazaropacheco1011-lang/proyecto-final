"""Carga idempotente del catálogo de Almacén real del proyecto.

Lee ``data/almacen_data.json`` (generado a partir de la base SQLite local) y
sincroniza SOLO las tablas ``almacen_categoria`` y ``almacen_producto``.

Reglas de seguridad:
- Categorías: ``get_or_create`` por NOMBRE. No copia IDs de SQLite.
- Productos: ``update_or_create`` por NOMBRE; los IDs se regeneran en Postgres.
- ``categoria`` se mapea por NOMBRE (no por ID).
- Nunca borra nada. No usa --flush. No toca ninguna otra tabla.
- No sobrescribe imágenes existentes (``update_or_create`` conserva el valor
  que ya esté en la BD para un producto con el mismo nombre).
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.almacen.models import Categoria, Producto

DATA_FILE = Path(__file__).resolve().parent.parent / 'data' / 'almacen_data.json'


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
                'stock': p.get('stock', 0),
                'destacado': bool(p.get('destacado', False)),
                'en_oferta': bool(p.get('en_oferta', False)),
                'precio_oferta': p.get('precio_oferta'),
            }
            # Imagen: solo se asigna en alta; si el producto ya existe, se conserva la actual.
            if p.get('imagen'):
                defaults['imagen'] = p['imagen']

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
            f'{Producto.objects.count()} productos (creados: {creados}, actualizados: {actualizados}).'
        ))
