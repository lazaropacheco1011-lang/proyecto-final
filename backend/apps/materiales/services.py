"""Operaciones de inventario compartidas (RN-06)."""
from decimal import Decimal

from django.db import transaction

from apps.materiales.models import MovimientoInventario


@transaction.atomic
def descontar_inventario(material, cantidad, usuario=None, motivo='Uso en orden de servicio'):
    """Resta del inventario y registra el movimiento de salida (RN-06)."""
    cantidad = Decimal(str(cantidad))
    if cantidad <= 0:
        raise ValueError('La cantidad debe ser mayor que cero.')
    if material.cantidad_disponible < cantidad:
        raise ValueError(
            f'Inventario insuficiente de {material.nombre}: '
            f'disponible {material.cantidad_disponible}, requerido {cantidad}.'
        )
    material.cantidad_disponible -= cantidad
    material.save(update_fields=['cantidad_disponible', 'updated_at'])
    MovimientoInventario.objects.create(
        material=material,
        tipo=MovimientoInventario.Tipo.SALIDA,
        cantidad=cantidad,
        motivo=motivo,
        usuario=usuario,
    )


@transaction.atomic
def reponer_inventario(material, cantidad, usuario=None, motivo='Devolución por ajuste'):
    """Suma al inventario y registra la entrada."""
    cantidad = Decimal(str(cantidad))
    material.cantidad_disponible += cantidad
    material.save(update_fields=['cantidad_disponible', 'updated_at'])
    MovimientoInventario.objects.create(
        material=material,
        tipo=MovimientoInventario.Tipo.ENTRADA,
        cantidad=cantidad,
        motivo=motivo,
        usuario=usuario,
    )


@transaction.atomic
def ajustar_inventario(material, nueva_cantidad, usuario=None, motivo='Ajuste manual'):
    """Fija la cantidad disponible y registra el ajuste."""
    nueva_cantidad = Decimal(str(nueva_cantidad))
    if nueva_cantidad < 0:
        raise ValueError('La cantidad no puede ser negativa.')
    diferencia = nueva_cantidad - material.cantidad_disponible
    material.cantidad_disponible = nueva_cantidad
    material.save(update_fields=['cantidad_disponible', 'updated_at'])
    if diferencia:
        MovimientoInventario.objects.create(
            material=material,
            tipo=MovimientoInventario.Tipo.AJUSTE,
            cantidad=diferencia,
            motivo=motivo,
            usuario=usuario,
        )
