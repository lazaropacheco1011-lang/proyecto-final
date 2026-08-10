"""Servicios de notificaciones (RF-24)."""
from datetime import timedelta

from django.utils import timezone

from apps.notificaciones.models import Notificacion


def notify_user(user, tipo, titulo, mensaje):
    if not user:
        return None
    return Notificacion.objects.create(
        usuario=user,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
    )


def notify_solicitud_creada(solicitud, staff_users):
    """Avisa al personal (admin/supervisor) de una nueva solicitud (RF-07)."""
    for user in staff_users:
        notify_user(
            user,
            Notificacion.Tipo.SISTEMA,
            'Nueva solicitud de instalación',
            f'{solicitud.cliente.nombre_completo} solicitó instalación de '
            f'"{solicitud.tipo_equipo_solicitado}" (solicitud #{solicitud.pk}).',
        )


def notify_solicitud_estado(solicitud, estado_nuevo):
    """Notifica al cliente los cambios de estado de su solicitud."""
    cliente = solicitud.cliente
    if not (cliente and cliente.user):
        return
    titulos = {
        'aprobada': 'Solicitud aprobada',
        'rechazada': 'Solicitud rechazada',
        'reprogramada': 'Solicitud reprogramada',
        'completada': 'Solicitud completada',
    }
    titulo = titulos.get(estado_nuevo)
    if not titulo:
        return
    notify_user(
        cliente.user,
        Notificacion.Tipo.CAMBIO_ESTADO,
        titulo,
        f'Tu solicitud #{solicitud.pk} de "{solicitud.tipo_equipo_solicitado}" '
        f'cambió a estado {solicitud.get_estado_display()}.',
    )


def notify_pago_confirmado(pago):
    """Confirma al cliente el registro o confirmación de un pago (RF-18)."""
    cliente = pago.cliente
    if not (cliente and cliente.user):
        return
    es_abono = 'abono' if pago.es_abono else 'pago'
    notify_user(
        cliente.user,
        Notificacion.Tipo.SISTEMA,
        'Pago confirmado',
        f'Se registró tu {es_abono} por ${pago.monto:,.0f} '
        f'({pago.get_metodo_display()}) el {pago.fecha}.',
    )


def recordatorios_mantenimiento():
    """Crea recordatorios de mantenimientos próximos (RF-24).

    Se invoca al cargar el dashboard operativo; evita duplicados de los
    últimos 7 días por equipo.
    """
    desde_hoy = timezone.localdate()
    hasta = desde_hoy + timedelta(days=7)
    from apps.mantenimientos.models import Mantenimiento
    from django.contrib.auth import get_user_model

    qs = Mantenimiento.objects.filter(
        proxima_fecha__range=(desde_hoy, hasta),
        estado__in=['pendiente', 'en_proceso'],
    ).select_related('equipo', 'cliente', 'cliente__user')
    creados = 0
    limite = hasta - timedelta(days=7)
    for mtto in qs:
        if mtto.cliente and mtto.cliente.user:
            ya = Notificacion.objects.filter(
                usuario=mtto.cliente.user,
                titulo__startswith='Mantenimiento próximo',
                fecha__gte=limite,
            ).exists()
            if not ya:
                notify_user(
                    mtto.cliente.user,
                    Notificacion.Tipo.MANTENIMIENTO,
                    'Mantenimiento próximo',
                    f'Tu equipo {mtto.equipo} tiene un mantenimiento '
                    f'{mtto.get_tipo_display().lower()} programado para el '
                    f'{mtto.proxima_fecha:%d/%m/%Y}.',
                )
                creados += 1
    return creados


def notify_orden_estado(orden, estado_nuevo, comentario=''):
    """Crea notificaciones relevantes según el cambio de estado de una orden."""
    cliente = orden.cliente
    tecnico = orden.tecnico

    if estado_nuevo == 'asignada' and tecnico:
        notify_user(
            tecnico.user,
            Notificacion.Tipo.ASIGNACION,
            'Nueva orden asignada',
            f'Se te asignó la orden {orden.numero} para {cliente.nombre_completo}.',
        )
    elif estado_nuevo == 'en_proceso':
        notify_user(
            cliente.user,
            Notificacion.Tipo.CAMBIO_ESTADO,
            'Tu servicio está en proceso',
            f'La orden {orden.numero} se encuentra en proceso.'
        ) if cliente.user else None
    elif estado_nuevo == 'finalizada':
        if cliente.user:
            notify_user(
                cliente.user,
                Notificacion.Tipo.FINALIZACION,
                'Servicio finalizado',
                f'La orden {orden.numero} fue finalizada. '
                'Puedes evaluar la atención recibida.',
            )
        if tecnico:
            notify_user(
                tecnico.user,
                Notificacion.Tipo.FINALIZACION,
                'Orden finalizada',
                f'La orden {orden.numero} fue finalizada correctamente.',
            )


def notify_instalacion_estado(instalacion, estado_nuevo):
    cliente = instalacion.cliente
    tecnico = instalacion.tecnico
    if not cliente:
        return
    if estado_nuevo in ('asignada', 'en_proceso', 'finalizada', 'reprogramada'):
        if cliente.user:
            notify_user(
                cliente.user,
                Notificacion.Tipo.CAMBIO_ESTADO,
                f'Instalación {instalacion.get_estado_display().lower()}',
                f'Tu instalación #{instalacion.pk} cambió de estado a '
                f'"{instalacion.get_estado_display()}".',
            )
        if tecnico and estado_nuevo in ('asignada', 'reprogramada'):
            notify_user(
                tecnico.user,
                Notificacion.Tipo.ASIGNACION,
                'Instalación asignada',
                f'Se te asignó la instalación #{instalacion.pk} en '
                f'{instalacion.direccion}.',
            )
