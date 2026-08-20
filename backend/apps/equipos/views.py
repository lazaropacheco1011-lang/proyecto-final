from django.db.models import Count
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.permissions import CLIENTE, TECNICO, has_role, is_admin
from apps.core.services import delete_or_conflict, register_audit, reject_if
from apps.equipos.models import Equipo, TipoEquipo
from apps.equipos.serializers import EquipoSerializer, TipoEquipoSerializer


class TipoEquipoViewSet(viewsets.ModelViewSet):
    """Catálogo de tipos de equipo."""
    queryset = TipoEquipo.objects.annotate(total_equipos=Count('equipos'))
    serializer_class = TipoEquipoSerializer
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre']

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        from apps.core.permissions import IsAdminOrAlmacen
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [perm() for perm in (IsAdminOrAlmacen,)]
        return [perm() for perm in (IsAuthenticated,)]

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='equipos.tipoequipo')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'actualizar', obj, model_name='equipos.tipoequipo')

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo el administrador puede eliminar tipos de equipo (RN-08).')
        reject_if(
            instance.equipos.exists(),
            'No se puede eliminar un tipo de equipo que tiene equipos asociados.',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='equipos.tipoequipo')
        delete_or_conflict(instance)


class EquipoViewSet(viewsets.ModelViewSet):
    """CRUD de equipos de refrigeración (RF-13, RF-14)."""
    queryset = Equipo.objects.select_related('cliente', 'tipo').all()
    serializer_class = EquipoSerializer
    filterset_fields = ['cliente', 'tipo', 'estado', 'marca', 'refrigerante']
    search_fields = [
        'marca', 'modelo', 'numero_serie', 'capacidad', 'refrigerante',
        'cliente__nombre', 'cliente__apellidos',
    ]
    ordering_fields = ['marca', 'modelo', 'created_at', 'updated_at']

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        from apps.core.permissions import IsAdminOrSupervisor
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [perm() for perm in (IsAdminOrSupervisor,)]
        return [perm() for perm in (IsAuthenticated,)]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        return qs

    def perform_create(self, serializer):
        obj = serializer.save()
        register_audit(self.request.user, 'crear', obj, model_name='equipos.equipo')

    def perform_update(self, serializer):
        obj = serializer.save()
        register_audit(
            self.request.user, 'actualizar', obj, model_name='equipos.equipo',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Solo el administrador puede eliminar equipos (RN-08).')
        reject_if(
            instance.mantenimientos.exists(),
            'No se puede eliminar el equipo porque tiene un historial de '
            'mantenimientos que debe conservarse.',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='equipos.equipo')
        delete_or_conflict(instance)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        """Historial completo del equipo (RF-13, RF-14b).

        Reúne instalación, cliente, técnico, mantenimientos, reparaciones,
        fotografías, firmas, garantía y observaciones en una sola respuesta.
        """
        from apps.core.serializers import EvidenciaSerializer, FirmaSerializer
        from apps.mantenimientos.models import Mantenimiento
        from apps.servicios.models import OrdenServicio

        equipo = self.get_object()

        instalaciones = []
        for ins in equipo.instalaciones.select_related('cliente', 'tecnico').prefetch_related(
            'evidencias', 'firmas', 'materiales_instalacion__material'
        ):
            instalaciones.append({
                'id': ins.id,
                'cliente': ins.cliente.nombre_completo,
                'fecha_programada': ins.fecha_programada,
                'fecha_instalacion': ins.fecha_instalacion,
                'estado': ins.estado,
                'estado_display': ins.get_estado_display(),
                'tecnico': ins.tecnico_nombre,
                'direccion': ins.direccion,
                'ciudad': ins.ciudad,
                'observaciones': ins.observaciones,
                'evidencias': EvidenciaSerializer(
                    ins.evidencias.all(), many=True, context={'request': request}
                ).data,
                'firmas': FirmaSerializer(
                    ins.firmas.all(), many=True, context={'request': request}
                ).data,
                'materiales': [
                    {'material': m.material.nombre, 'cantidad': str(m.cantidad)}
                    for m in ins.materiales_instalacion.all()
                ],
            })

        ordenes = []
        for ord in equipo.ordenes.select_related('cliente', 'tecnico').prefetch_related(
            'evidencias', 'firmas', 'materiales_utilizados__material'
        ):
            ordenes.append({
                'id': ord.id,
                'numero': ord.numero,
                'tipo_servicio': ord.tipo_servicio,
                'tipo_servicio_display': ord.get_tipo_servicio_display(),
                'fecha': ord.fecha,
                'estado': ord.estado,
                'estado_display': ord.get_estado_display(),
                'tecnico': ord.tecnico_nombre,
                'diagnostico': ord.diagnostico,
                'trabajo_realizado': ord.trabajo_realizado,
                'observaciones': ord.observaciones,
                'evidencias': EvidenciaSerializer(
                    ord.evidencias.all(), many=True, context={'request': request}
                ).data,
                'firmas': FirmaSerializer(
                    ord.firmas.all(), many=True, context={'request': request}
                ).data,
                'materiales': [
                    {'material': m.material.nombre, 'cantidad': str(m.cantidad)}
                    for m in ord.materiales_utilizados.all()
                ],
            })

        mantenimientos = [
            {
                'id': m.id,
                'tipo': m.tipo,
                'tipo_display': m.get_tipo_display(),
                'fecha': m.fecha,
                'proxima_fecha': m.proxima_fecha,
                'estado': m.estado,
                'estado_display': m.get_estado_display(),
                'tecnico': m.tecnico_nombre,
                'descripcion': m.descripcion,
                'trabajo_realizado': m.trabajo_realizado,
                'costo': str(m.costo),
                'observaciones': m.observaciones,
            }
            for m in Mantenimiento.objects.filter(equipo=equipo).select_related('tecnico')
        ]

        data = {
            'equipo': EquipoSerializer(equipo, context={'request': request}).data,
            'cliente': equipo.cliente.nombre_completo,
            'fecha_instalacion': equipo.fecha_instalacion,
            'garantia_meses': equipo.garantia_meses,
            'garantia_hasta': equipo.garantia_hasta,
            'garantia_activa': equipo.garantia_activa,
            'observaciones': equipo.descripcion,
            'instalaciones': instalaciones,
            'reparaciones': ordenes,
            'mantenimientos': mantenimientos,
        }
        return Response(data)
