"""
Backfill de tipo_solicitud a partir del contenido histórico de tipo_equipo_solicitado.

Reglas de clasificación (orden estricto):
  1. Valor exacto 'Instalación' / 'Reparación' / 'Mantenimiento' → slug correspondiente.
  2. Contiene 'repar'  (case-insensitive) → 'reparacion'.
  3. Contiene 'mantenimiento'              → 'mantenimiento'.
  4. Contiene 'instal'                     → 'instalacion'.
  5. Cualquier otro caso                   → 'otro' (fallback seguro).

Importante:
  - NUNCA se escribe sobre tipo_equipo_solicitado.
  - Esta migración es idempotente: re-ejecutarla no modifica datos ya clasificados.
  - Reverse = noop (el esquema 0002 ya asigna default 'otro'; revertir dejas todo en 'otro').
"""

from collections import defaultdict

from django.db import migrations


_LITERALS = {
    'instalación': 'instalacion',
    'reparación': 'reparacion',
    'mantenimiento': 'mantenimiento',
}


def classify_tipo(equipo):
    if not equipo:
        return 'otro'
    text = equipo.strip().lower()
    if text in _LITERALS:
        return _LITERALS[text]
    if 'repar' in text:
        return 'reparacion'
    if 'mantenimiento' in text:
        return 'mantenimiento'
    if 'instal' in text:
        return 'instalacion'
    return 'otro'


def backfill_tipo_solicitud(apps, schema_editor):
    Solicitud = apps.get_model('solicitudes', 'SolicitudInstalacion')
    if not Solicitud.objects.exists():
        return

    updates = defaultdict(list)
    for obj in Solicitud.objects.all():
        tipo = classify_tipo(obj.tipo_equipo_solicitado)
        if tipo != 'otro' and tipo != obj.tipo_solicitud:
            updates[tipo].append(obj.pk)

    for tipo, pks in updates.items():
        Solicitud.objects.filter(pk__in=pks).update(tipo_solicitud=tipo)


class Migration(migrations.Migration):

    dependencies = [
        ('solicitudes', '0002_solicitudinstalacion_tipo_solicitud_and_more'),
    ]

    operations = [
        migrations.RunPython(
            backfill_tipo_solicitud,
            migrations.RunPython.noop,
        ),
    ]
