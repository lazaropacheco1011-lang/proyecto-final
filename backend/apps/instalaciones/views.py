from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS
from rest_framework.response import Response

from apps.core.permissions import CLIENTE, TECNICO, has_role, is_admin
from apps.core.services import log_state_change, register_audit
from apps.instalaciones.models import Instalacion, InstalacionEstadoLog
from apps.instalaciones.serializers import (
    InstalacionEstadoLogSerializer,
    InstalacionSerializer,
    MaterialInstalacionSerializer,
)
from apps.instalaciones.services import sugerir_horarios
from apps.notificaciones.models import Notificacion
from apps.notificaciones.services import notify_instalacion_estado, notify_user


def _registrar_log_estado(user, instalacion, anterior, nuevo, comentario=''):
    """Persiste el cambio de estado en el historial de la instalación."""
    InstalacionEstadoLog.objects.create(
        instalacion=instalacion,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        usuario=user,
        comentario=comentario,
    )


def _notificar_asignacion(instalacion):
    """Avisa al técnico cuando se le asigna una instalación."""
    tecnico = instalacion.tecnico
    if tecnico and tecnico.user:
        notify_user(
            tecnico.user,
            Notificacion.Tipo.ASIGNACION,
            'Instalación asignada',
            f'Se te asignó la instalación #{instalacion.pk} en {instalacion.direccion} '
            f'({instalacion.ciudad or "sin ciudad"}).',
        )


class InstalacionViewSet(viewsets.ModelViewSet):
    """Instalaciones y agenda de instalaciones (RF-08, RF-10, RF-12)."""
    queryset = Instalacion.objects.select_related(
        'cliente', 'equipo', 'tecnico', 'solicitud'
    ).prefetch_related('evidencias', 'firmas', 'materiales_instalacion__material', 'historial')
    serializer_class = InstalacionSerializer
    filterset_fields = [
        'estado', 'prioridad', 'cliente', 'equipo', 'tecnico', 'ciudad',
    ]
    search_fields = [
        'direccion', 'ciudad', 'observaciones', 'cliente__nombre',
        'cliente__apellidos', 'equipo__numero_serie', 'equipo__marca',
    ]
    ordering_fields = ['fecha_programada', 'fecha_instalacion', 'prioridad', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        return qs

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in SAFE_METHODS and has_role(request.user, CLIENTE):
            raise PermissionDenied(
                'Los clientes no pueden crear ni modificar instalaciones (RN-08).'
            )

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'request': self.request}

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='instalaciones.instalacion')
        if obj.tecnico:
            _notificar_asignacion(obj)

    def perform_update(self, serializer):
        prev_estado = serializer.instance.estado if serializer.instance else None
        prev_tecnico = serializer.instance.tecnico_id if serializer.instance else None
        obj = serializer.save()
        if prev_estado != obj.estado:
            _registrar_log_estado(self.request.user, obj, prev_estado, obj.estado)
            log_state_change(self.request.user, obj, prev_estado, obj.estado)
            notify_instalacion_estado(obj, obj.estado)
        if prev_tecnico != obj.tecnico_id and obj.tecnico:
            _notificar_asignacion(obj)
        register_audit(
            self.request.user, 'actualizar', obj, model_name='instalaciones.instalacion',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            raise PermissionDenied('Solo el administrador puede eliminar instalaciones (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='instalaciones.instalacion')
        instance.delete()

    @action(detail=False, methods=['get'])
    def agenda(self, request):
        """Agenda de instalaciones filtrable por fecha, técnico o cliente (RF-10)."""
        fecha = request.query_params.get('fecha')
        tecnico = request.query_params.get('tecnico')
        cliente = request.query_params.get('cliente')
        estado = request.query_params.get('estado')

        qs = self.get_queryset()
        if fecha:
            qs = qs.filter(fecha_programada__date=fecha)
        if tecnico:
            qs = qs.filter(tecnico_id=tecnico)
        if cliente:
            qs = qs.filter(cliente_id=cliente)
        if estado:
            qs = qs.filter(estado=estado)

        qs = qs.filter(estado__in=['pendiente', 'asignada', 'en_proceso', 'reprogramada'])
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de la instalación validando las reglas de negocio."""
        instalacion = self.get_object()
        nuevo_estado = request.data.get('estado')
        if not nuevo_estado:
            return Response({'message': 'El campo estado es obligatorio.'}, status=400)

        serializer = self.get_serializer(
            instalacion,
            data={'estado': nuevo_estado, **request.data},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        prev = instalacion.estado
        serializer.save()
        _registrar_log_estado(request.user, instalacion, prev, nuevo_estado)
        log_state_change(request.user, instalacion, prev, nuevo_estado)
        notify_instalacion_estado(instalacion, nuevo_estado)
        return Response(self.get_serializer(instalacion).data)

    @action(detail=True, methods=['patch'])
    def reprogramar(self, request, pk=None):
        """Reprograma una instalación y notifica al cliente y al técnico (RF-10)."""
        instalacion = self.get_object()
        nueva_fecha = request.data.get('fecha_programada')
        motivo = request.data.get('motivo', '')
        if not nueva_fecha:
            return Response(
                {'detail': 'El campo fecha_programada es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if instalacion.estado in ('cancelada', 'finalizada'):
            return Response(
                {'detail': f'No se puede reprogramar una instalación {instalacion.get_estado_display().lower()}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        prev = instalacion.estado
        serializer = self.get_serializer(
            instalacion,
            data={'estado': 'reprogramada', 'fecha_programada': nueva_fecha, 'observaciones': motivo},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _registrar_log_estado(request.user, instalacion, prev, instalacion.estado, motivo or 'Reprogramación')
        log_state_change(request.user, instalacion, prev, instalacion.estado)
        register_audit(
            request.user, 'actualizar', instalacion,
            model_name='instalaciones.instalacion',
            changes={'accion': 'reprogramar', 'fecha_programada': nueva_fecha, 'motivo': motivo},
        )
        if instalacion.cliente and instalacion.cliente.user:
            notify_user(
                instalacion.cliente.user,
                Notificacion.Tipo.CAMBIO_ESTADO,
                'Tu instalación fue reprogramada',
                f'La instalación #{instalacion.pk} fue reprogramada para '
                f'el {timezone.localtime(instalacion.fecha_programada):%d/%m/%Y %H:%M}.',
            )
        if instalacion.tecnico and instalacion.tecnico.user:
            notify_user(
                instalacion.tecnico.user,
                Notificacion.Tipo.ASIGNACION,
                'Instalación reprogramada',
                f'La instalación #{instalacion.pk} fue reprogramada para '
                f'el {timezone.localtime(instalacion.fecha_programada):%d/%m/%Y %H:%M}.',
            )
        return Response(self.get_serializer(instalacion).data)

    @action(detail=False, methods=['get'])
    def disponibilidad(self, request):
        """Sugiere horarios libres de un técnico para una fecha (agenda inteligente)."""
        fecha = request.query_params.get('fecha')
        tecnico = request.query_params.get('tecnico')
        duracion = request.query_params.get('duracion_minutos')
        excluir = request.query_params.get('instalacion')
        try:
            slots = sugerir_horarios(
                fecha=fecha,
                tecnico_id=tecnico,
                duracion_minutos=int(duracion) if duracion else 120,
                excluir_instalacion=int(excluir) if excluir else None,
            )
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'fecha': fecha, 'tecnico': tecnico, 'slots': slots})

    @action(detail=True, methods=['get', 'post'])
    def materiales(self, request, pk=None):
        """Lista o agrega materiales utilizados en la instalación (RF-15b)."""
        instalacion = self.get_object()
        if request.method == 'GET':
            qs = instalacion.materiales_instalacion.select_related('material')
            serializer = MaterialInstalacionSerializer(qs, many=True, context={'request': request})
            return Response(serializer.data)

        data = {**request.data, 'instalacion': instalacion.id}
        serializer = MaterialInstalacionSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            uso = serializer.save()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        register_audit(
            request.user, 'crear', uso, model_name='instalaciones.materialinstalacion'
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        """Historial de cambios de estado de la instalación (RN-09)."""
        instalacion = self.get_object()
        qs = instalacion.historial.select_related('usuario')
        serializer = InstalacionEstadoLogSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def mapa(self, request):
        """Instalaciones con coordenadas para visualizarlas en el mapa (RF-10b)."""
        qs = self.get_queryset().filter(latitud__isnull=False, longitud__isnull=False)
        return Response([
            {
                'id': i.id,
                'cliente': i.cliente.nombre_completo,
                'direccion': i.direccion,
                'ciudad': i.ciudad,
                'latitud': str(i.latitud),
                'longitud': str(i.longitud),
                'estado': i.estado,
                'estado_display': i.get_estado_display(),
                'fecha_programada': i.fecha_programada,
            }
            for i in qs[:500]
        ])

    @action(detail=False, methods=['get'])
    def proximos(self, request):
        """Instalaciones programadas desde hoy (próximos 30 días)."""
        desde = timezone.now()
        hasta = desde + timezone.timedelta(days=30)
        qs = self.get_queryset().filter(
            fecha_programada__range=(desde, hasta),
            estado__in=['pendiente', 'asignada', 'reprogramada'],
        ).order_by('fecha_programada')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
