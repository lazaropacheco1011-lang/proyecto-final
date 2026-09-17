# -*- coding: utf-8 -*-
# Migracion de DATOS (no de esquema). SOLO actualiza latitud/longitud de las
# instalaciones identificadas por su (direccion, ciudad) EXACTA y que aun no
# tienen coordenadas. Idempotente: si ya hay lat/long no toca nada.
# No modifica direcciones, clientes, equipos, estados ni otros campos.
# Reverse NO destructivo (no borra nada).
from django.db import migrations
from decimal import Decimal

CB = {  # (clave FK -> NO existe FK: uso direccion+ciudad evaluadas por seed_data.py)
    "instalacion1": {
        "direccion": "Av. 27 de Febrero # 45",
        "ciudad": "Santiago de los Caballeros",
        "lat": Decimal("19.4616800"),
        "lng": Decimal("-70.6797400"),
    },
    "instalacion3": {
        "direccion": "Av. Salvador Estrella Sadhalá",
        "ciudad": "Santiago de los Caballeros",
        "lat": Decimal("19.4485600"),
        "lng": Decimal("-70.6876200"),
    },
}


def setear(apps, schema_editor):
    Instalacion = apps.get_model("instalaciones", "Instalacion")
    # Filtramos (direccion, ciudad) EXACTOS y solo si NO tienen coordenadas.
    # Asi: idempotente y nunca reescribe coordenadas ya existentes/validas.
    for datos in CB.values():
        Instalacion.objects.filter(
            direccion=datos["direccion"],
            ciudad=datos["ciudad"],
            latitud__isnull=True,
            longitud__isnull=True,
        ).update(
            latitud=datos["lat"],
            longitud=datos["lng"],
        )


def sin_efecto(apps, schema_editor):
    # Reverse no destructivo: no borra coordenadas ni ningun dato.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("instalaciones", "0002_instalacion_latitud_instalacion_longitud_and_more"),
    ]
    operations = [
        migrations.RunPython(setear, sin_efecto),
    ]
