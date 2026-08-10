"""Servicios de instalaciones: agenda inteligente e inventario (RF-10, RN-06)."""
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone as tz

from apps.core.services import log_state_change, register_audit
from apps.instalaciones.models import Instalacion
from apps.materiales.services import descontar_inventario

# Ventana de bloqueo del técnico (RN-03): ±2 horas alrededor de cada cita.
VENTANA_BLOQUEO_HORAS = 2
# Horario laboral sugerido.
HORA_INICIO = time(8, 0)
HORA_FIN = time(18, 0)
PASO_SUGERENCIA = timedelta(minutes=30)


def finalizar_instalacion(instalacion, user=None, comentario=''):
    """Finaliza una instalación descontando el inventario de los materiales usados.

    Se invoca una sola vez por transición a 'finalizada' desde el viewset.
    Levanta ValueError si algún material no tiene inventario suficiente.
    """
    with transaction.atomic():
        usos = list(instalacion.materiales_instalacion.select_related('material').all())
        for uso in usos:
            descontar_inventario(
                uso.material,
                uso.cantidad,
                usuario=user,
                motivo=f'Uso en instalación #{instalacion.pk}',
            )
        if not instalacion.fecha_instalacion:
            instalacion.fecha_instalacion = tz.now()
            instalacion.save(update_fields=['fecha_instalacion', 'updated_at'])
        if user:
            register_audit(
                user, 'actualizar', instalacion,
                model_name='instalaciones.instalacion',
                changes={'inventario': 'descontado', 'comentario': comentario},
            )
    return usos


def sugerir_horarios(fecha, tecnico_id=None, duracion_minutos=120, excluir_instalacion=None):
    """Calcula horarios libres de un técnico para una fecha dada.

    Devuelve una lista de {inicio, fin} (datetime local) que respetan la
    ventana de ±2 h respecto a instalaciones ya programadas (RN-03).
    """
    if not fecha:
        raise ValueError('La fecha es obligatoria.')
    if not tecnico_id:
        raise ValueError('Debes indicar el técnico para sugerir horarios.')

    from django.utils.dateparse import parse_date
    if isinstance(fecha, str):
        fecha = parse_date(fecha)
        if fecha is None:
            raise ValueError('Formato de fecha inválido (usa AAAA-MM-DD).')

    dia = fecha if isinstance(fecha, datetime) else datetime.combine(fecha, time(0, 0))
    inicio_dia = tz.make_aware(datetime.combine(dia.date(), HORA_INICIO), tz.get_current_timezone())
    fin_dia = tz.make_aware(datetime.combine(dia.date(), HORA_FIN), tz.get_current_timezone())
    duracion = timedelta(minutes=int(duracion_minutos) or 120)

    qs = Instalacion.objects.filter(
        tecnico_id=tecnico_id,
        fecha_programada__date=dia.date(),
    ).exclude(estado__in=['cancelada', 'finalizada'])
    if excluir_instalacion:
        qs = qs.exclude(pk=excluir_instalacion)

    bloques = []
    for ins in qs.values('fecha_programada'):
        f = ins['fecha_programada']
        bloques.append((f - timedelta(hours=VENTANA_BLOQUEO_HORAS),
                        f + timedelta(hours=VENTANA_BLOQUEO_HORAS)))

    slots = []
    cursor = inicio_dia
    while cursor + duracion <= fin_dia:
        fin_slot = cursor + duracion
        libre = all(fin_slot <= inicio_bloque or cursor >= fin_bloque
                    for inicio_bloque, fin_bloque in bloques)
        if libre:
            slots.append({
                'inicio': cursor.isoformat(),
                'fin': fin_slot.isoformat(),
            })
        cursor += PASO_SUGERENCIA
    return slots
