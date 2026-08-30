from decimal import Decimal

from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.core.permissions import (
    ADMIN,
    SUPERVISOR,
    TECNICO,
    CLIENTE,
    get_supervisor_tecnico_ids,
    has_role,
    is_admin,
    is_staff_role,
    is_supervisor,
)
from apps.core.services import log_state_change, register_audit
from apps.materiales.services import reponer_inventario
from apps.notificaciones.services import notify_orden_estado
from apps.servicios.models import EstadoOrdenLog, MaterialUtilizado, OrdenServicio, VisitaTecnica
from apps.servicios.serializers import (
    EstadoOrdenLogSerializer,
    MaterialUtilizadoSerializer,
    OrdenServicioSerializer,
    VisitaTecnicaSerializer,
)


class OrdenServicioViewSet(viewsets.ModelViewSet):
    """Órdenes de trabajo / servicios (RF-08, RF-09, RF-21)."""
    queryset = OrdenServicio.objects.select_related(
        'cliente', 'equipo', 'tecnico'
    ).prefetch_related('materiales_utilizados__material', 'historial', 'evidencias').annotate(
        costo_materiales=Coalesce(
            Sum('materiales_utilizados__subtotal'), Value(Decimal('0.00'))
        )
    )
    serializer_class = OrdenServicioSerializer
    filterset_fields = [
        'estado', 'tipo_servicio', 'cliente', 'equipo', 'tecnico', 'fecha',
    ]
    search_fields = [
        'numero', 'problema_reportado', 'diagnostico', 'trabajo_realizado',
        'observaciones', 'cliente__nombre', 'cliente__apellidos',
        'equipo__numero_serie', 'equipo__marca',
    ]
    ordering_fields = ['fecha', 'created_at', 'estado']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(
                    Q(tecnico__user_id__in=tecnicos_ids) | Q(tecnico__isnull=True)
                )
            return qs
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if has_role(user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden crear órdenes de servicio.')
        orden = serializer.save()
        EstadoOrdenLog.objects.create(
            orden=orden,
            estado_anterior='',
            estado_nuevo=orden.estado,
            usuario=self.request.user,
            comentario='Creación de la orden',
        )
        register_audit(self.request.user, 'crear', orden, model_name='servicios.ordenservicio')
        notify_orden_estado(orden, orden.estado)

    def perform_update(self, serializer):
        prev_estado = serializer.instance.estado if serializer.instance else None
        orden = serializer.save()
        if prev_estado != orden.estado:
            EstadoOrdenLog.objects.create(
                orden=orden,
                estado_anterior=prev_estado,
                estado_nuevo=orden.estado,
                usuario=self.request.user,
                comentario='Actualización de estado',
            )
            log_state_change(self.request.user, orden, prev_estado, orden.estado)
            notify_orden_estado(orden, orden.estado)
        register_audit(
            self.request.user, 'actualizar', orden, model_name='servicios.ordenservicio',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        user = self.request.user
        if has_role(user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden eliminar órdenes de servicio.')
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if not instance.tecnico or instance.tecnico.user_id not in tecnicos_ids:
                raise PermissionDenied('Solo puedes eliminar órdenes asignadas a tus técnicos.')
        elif not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar órdenes (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='servicios.ordenservicio')
        instance.delete()

    # ------------------------------------------------------------------
    # Materiales de la orden (RN-06)
    # ------------------------------------------------------------------
    @action(detail=True, methods=['get', 'post'])
    def materiales(self, request, pk=None):
        """Lista o agrega materiales utilizados en la orden (RF-15)."""
        orden = self.get_object()
        if request.method == 'GET':
            qs = orden.materiales_utilizados.select_related('material')
            serializer = MaterialUtilizadoSerializer(qs, many=True, context={'request': request})
            return Response(serializer.data)

        if not is_staff_role(request.user):
            raise PermissionDenied('Solo el personal interno puede registrar materiales.')
        data = {**request.data, 'orden': orden.id}
        serializer = MaterialUtilizadoSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            uso = serializer.save()
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        register_audit(
            request.user, 'crear', uso, model_name='servicios.materialutilizado'
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def historial(self, request, pk=None):
        """Historial de cambios de estado de la orden (RN-09)."""
        orden = self.get_object()
        qs = orden.historial.select_related('usuario')
        serializer = EstadoOrdenLogSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado validando transiciones y reglas de negocio."""
        orden = self.get_object()
        nuevo_estado = request.data.get('estado')
        if not nuevo_estado:
            return Response(
                {'detail': 'El campo estado es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        comentario = request.data.get('comentario', '')
        serializer = self.get_serializer(
            orden, data={'estado': nuevo_estado, **request.data}, partial=True
        )
        serializer.is_valid(raise_exception=True)
        prev = orden.estado
        serializer.save()
        EstadoOrdenLog.objects.create(
            orden=orden,
            estado_anterior=prev,
            estado_nuevo=orden.estado,
            usuario=request.user,
            comentario=comentario,
        )
        log_state_change(request.user, orden, prev, orden.estado)
        notify_orden_estado(orden, orden.estado)
        return Response(self.get_serializer(orden).data)

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Órdenes pendientes de atención."""
        qs = self.get_queryset().filter(estado__in=['pendiente', 'asignada']).order_by('fecha')
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Genera PDF operativo de una orden (sin datos financieros)."""
        orden = self.get_object()
        if has_role(request.user, TECNICO):
            if not orden.tecnico or orden.tecnico.user_id != request.user.id:
                raise PermissionDenied('Esta orden no está asignada a ti.')
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
        )
        from django.utils import timezone
        import io

        BRAND = colors.HexColor('#0284C7')
        BRAND_DARK = colors.HexColor('#075985')
        BORDER = colors.HexColor('#CBD5E1')
        ZEBRA = colors.HexColor('#F1F5F9')
        MUTED = '#94A3B8'
        INK = colors.HexColor('#0F172A')

        def _esc(value):
            return (str(value or '')
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;'))

        def _fecha(dt):
            return dt.strftime('%d/%m/%Y') if dt else '—'

        def _fecha_hora(dt):
            return dt.strftime('%d/%m/%Y %H:%M') if dt else '—'

        R = getSampleStyleSheet()
        st_titulo = ParagraphStyle('Titulo', parent=R['Title'], fontSize=25, leading=28,
                                   fontName='Helvetica-Bold', textColor=BRAND_DARK,
                                   alignment=TA_CENTER, spaceAfter=0)
        st_sub = ParagraphStyle('Sub', parent=R['Normal'], fontSize=9, leading=12,
                                textColor=colors.HexColor('#475569'),
                                alignment=TA_CENTER, spaceAfter=0)
        st_codigo = ParagraphStyle('Cod', parent=R['Normal'], fontSize=16, leading=20,
                                   fontName='Helvetica-Bold', textColor=BRAND_DARK)
        st_estado = ParagraphStyle('Est', parent=R['Normal'], fontSize=9, leading=12,
                                   fontName='Helvetica-Bold', textColor=colors.white,
                                   backColor=BRAND, borderPadding=(4, 8, 4, 8))
        st_sec = ParagraphStyle('Sec', parent=R['Heading2'], fontSize=10, leading=13,
                                fontName='Helvetica-Bold', textColor=colors.white)
        st_label = ParagraphStyle('Lab', parent=R['Normal'], fontSize=9, leading=12,
                                  fontName='Helvetica-Bold', textColor=colors.HexColor('#475569'))
        st_valor = ParagraphStyle('Val', parent=R['Normal'], fontSize=9, leading=12,
                                  textColor=INK)
        st_mat = ParagraphStyle('Mat', parent=R['Normal'], fontSize=9, leading=12, textColor=INK)
        st_mat_h = ParagraphStyle('MatH', parent=st_mat, fontName='Helvetica-Bold', textColor=colors.white)

        def _barra(titulo):
            t = Table([[Paragraph(_esc(titulo), st_sec), '']], colWidths=[510], hAlign='LEFT')
            t.setStyle(TableStyle([
                ('SPAN', (0, 0), (-1, 0)),
                ('BACKGROUND', (0, 0), (-1, 0), BRAND),
                ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            return t

        def _seccion(titulo, pares):
            cuerpo = [[Paragraph(_esc(titulo), st_sec), '']]
            for label, valor in pares:
                vacio = (valor is None or valor == '' or valor == '—' or valor == '-')
                texto = '—' if vacio else _esc(valor)
                if vacio:
                    texto = f'<font color="{MUTED}">{texto}</font>'
                cuerpo.append([Paragraph(_esc(label), st_label), Paragraph(texto, st_valor)])
            t = Table(cuerpo, colWidths=[130, 380], hAlign='LEFT')
            t.setStyle(TableStyle([
                ('SPAN', (0, 0), (1, 0)),
                ('BACKGROUND', (0, 0), (-1, 0), BRAND),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
                ('INNERGRID', (0, 1), (-1, -2), 0.4, colors.HexColor('#E2E8F0')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            return t

        def _pie(canvas, doc):
            canvas.saveState()
            canvas.setStrokeColor(BORDER)
            canvas.setLineWidth(0.5)
            canvas.line(45, 36, letter[0] - 45, 36)
            canvas.setFont('Helvetica-Bold', 8)
            canvas.setFillColor(BRAND_DARK)
            canvas.drawString(45, 26, 'REFRIMASTER')
            canvas.setFont('Helvetica', 7.5)
            canvas.setFillColor(colors.HexColor(MUTED))
            canvas.drawString(
                45, 18,
                'Sistemas de Refrigeración  ·  Documento generado el '
                + timezone.now().strftime('%d/%m/%Y %H:%M')
                + f'  ·  Página {doc.page}',
            )
            canvas.restoreState()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=letter,
            rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=55,
        )
        elems = []

        # Encabezado
        elems.append(Paragraph('REFRIMASTER', st_titulo))
        elems.append(Paragraph('Sistemas de Refrigeración', st_sub))
        elems.append(Spacer(1, 4))
        elems.append(HRFlowable(width='100%', thickness=1.5, color=BRAND, spaceBefore=2, spaceAfter=10))

        # Código y estado destacados
        cabecera = Table(
            [[Paragraph(_esc('ORDEN DE SERVICIO'), st_codigo),
              Paragraph(_esc('Estado: ' + orden.get_estado_display()), st_estado)]],
            colWidths=[330, 180], hAlign='LEFT',
        )
        cabecera.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elems.append(cabecera)
        elems.append(Spacer(1, 12))

        # Información del cliente
        cliente = orden.cliente if orden.cliente_id else None
        elems.append(_seccion('Información del cliente', [
            ('Cliente', (cliente.nombre_completo if cliente else '—')),
            ('Documento', (cliente.documento_numero if cliente else '—')),
            ('Equipo', (orden.equipo_nombre or '—')),
        ]))
        elems.append(Spacer(1, 10))

        # Información del servicio
        elems.append(_seccion('Información del servicio', [
            ('Tipo de servicio', orden.get_tipo_servicio_display()),
            ('Problema reportado', orden.problema_reportado or '—'),
            ('Diagnóstico', orden.diagnostico or '—'),
            ('Trabajo realizado', orden.trabajo_realizado or '—'),
            ('Observaciones', orden.observaciones or '—'),
        ]))
        elems.append(Spacer(1, 10))

        # Técnico asignado
        tec = orden.tecnico
        if tec:
            nombre_tec = tec.user.get_full_name() or tec.user.username
            rol_tec = tec.user.get_role_display()
        else:
            nombre_tec, rol_tec = '', ''
        elems.append(_seccion('Técnico asignado', [
            ('Técnico', (nombre_tec or '—')),
            ('Rol', (rol_tec or '—')),
        ]))
        elems.append(Spacer(1, 10))

        # Fechas
        filas_fechas = [('Fecha de servicio', _fecha(orden.fecha))]
        if orden.fecha_asignacion:
            filas_fechas.append(('Fecha de asignación', _fecha_hora(orden.fecha_asignacion)))
        if orden.fecha_finalizacion:
            filas_fechas.append(('Fecha de finalización', _fecha_hora(orden.fecha_finalizacion)))
        elems.append(_seccion('Fechas', filas_fechas))
        elems.append(Spacer(1, 10))

        # Materiales necesarios (sin importes financieros)
        materiales = list(orden.materiales_utilizados.select_related('material').all())
        if materiales:
            mat_body = [['Material', 'Código', 'Cantidad']]
            for m in materiales:
                mat_body.append([
                    Paragraph(_esc(m.material.nombre), st_mat),
                    Paragraph(_esc(m.material.codigo), st_mat),
                    Paragraph(_esc(m.cantidad), st_mat),
                ])
            mat_body[0] = [Paragraph(x, st_mat_h) for x in mat_body[0]]
            mat_t = Table(mat_body, colWidths=[280, 120, 110], hAlign='LEFT', repeatRows=1)
            mat_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BRAND),
                ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
                ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E2E8F0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, ZEBRA]),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elems.append(_barra('Materiales necesarios'))
            elems.append(Spacer(1, 4))
            elems.append(mat_t)

        doc.build(elems, onFirstPage=_pie, onLaterPages=_pie)
        buf.seek(0)
        response = HttpResponse(buf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename=orden_{orden.numero}.pdf'
        return response


class VisitaTecnicaViewSet(viewsets.ModelViewSet):
    """Visitas técnicas al domicilio del cliente (RF-11)."""
    queryset = VisitaTecnica.objects.select_related('cliente', 'orden', 'tecnico').all()
    serializer_class = VisitaTecnicaSerializer
    filterset_fields = ['estado', 'cliente', 'tecnico', 'fecha']
    search_fields = [
        'numero', 'motivo', 'direccion',
        'cliente__nombre', 'cliente__apellidos', 'orden__numero',
    ]
    ordering_fields = ['fecha', 'created_at', 'estado']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(tecnico__user_id__in=tecnicos_ids)
            return qs.none()
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        if not is_staff_role(user):
            raise PermissionDenied('Solo el personal interno puede registrar visitas técnicas.')
        visita = serializer.save()
        register_audit(self.request.user, 'crear', visita, model_name='servicios.visitatecnica')

    def perform_update(self, serializer):
        user = self.request.user
        if not is_staff_role(user):
            raise PermissionDenied('Solo el personal interno puede modificar visitas técnicas.')
        visita = serializer.save()
        register_audit(
            self.request.user, 'actualizar', visita,
            model_name='servicios.visitatecnica',
            changes=serializer.validated_data,
        )

    def perform_destroy(self, instance):
        user = self.request.user
        if has_role(user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden eliminar visitas técnicas.')
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if not instance.tecnico or instance.tecnico.user_id not in tecnicos_ids:
                raise PermissionDenied('Solo puedes eliminar visitas asignadas a tus técnicos.')
        elif not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar visitas (RN-08).')
        register_audit(self.request.user, 'eliminar', instance, model_name='servicios.visitatecnica')
        instance.delete()


class MaterialUtilizadoViewSet(viewsets.ModelViewSet):
    """Actualizar o eliminar un material utilizado en una orden."""
    queryset = MaterialUtilizado.objects.select_related('material', 'orden')
    serializer_class = MaterialUtilizadoSerializer
    filterset_fields = ['orden', 'material']

    def get_permissions(self):
        from rest_framework.permissions import IsAuthenticated
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        if not is_staff_role(self.request.user):
            raise PermissionDenied('Solo el personal interno puede registrar materiales.')
        serializer.save()

    def perform_update(self, serializer):
        if not is_staff_role(self.request.user):
            raise PermissionDenied('Solo el personal interno puede modificar materiales.')
        uso = serializer.save()
        register_audit(self.request.user, 'actualizar', uso, model_name='servicios.materialutilizado')

    def perform_destroy(self, instance):
        user = self.request.user
        if has_role(user, TECNICO):
            raise PermissionDenied('Los técnicos no pueden eliminar ítems de materiales.')
        if not is_admin(user):
            raise PermissionDenied('Solo el administrador puede eliminar ítems de materiales (RN-08).')
        reponer_inventario(
            instance.material, instance.cantidad,
            usuario=self.request.user,
            motivo=f'Eliminación de ítem en orden {instance.orden.numero}',
        )
        register_audit(self.request.user, 'eliminar', instance, model_name='servicios.materialutilizado')
        instance.delete()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if has_role(user, CLIENTE):
            return qs.filter(cliente__user=user)
        if has_role(user, TECNICO):
            return qs.filter(tecnico__user=user)
        if is_supervisor(user):
            tecnicos_ids = get_supervisor_tecnico_ids(user)
            if tecnicos_ids:
                return qs.filter(
                    Q(tecnico__user_id__in=tecnicos_ids) | Q(tecnico__isnull=True)
                )
            return qs
        return qs
