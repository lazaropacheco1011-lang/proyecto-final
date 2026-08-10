"""
Carga datos de prueba para REFRIMASTE.

Uso:
    python manage.py seed_data
    python manage.py seed_data --flush   (borra los datos existentes primero)
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente, DireccionInstalacion
from apps.cotizaciones.models import Cotizacion, CotizacionDetalle
from apps.equipos.models import Equipo, TipoEquipo
from apps.evaluaciones.models import EvaluacionServicio
from apps.instalaciones.models import Instalacion
from apps.mantenimientos.models import Mantenimiento
from apps.materiales.models import Material
from apps.pagos.models import Factura, Pago
from apps.servicios.models import EstadoOrdenLog, MaterialUtilizado, OrdenServicio
from apps.solicitudes.models import SolicitudInstalacion

User = get_user_model()

PASSWORD = 'Refrimaste2026!'


class Command(BaseCommand):
    help = 'Carga datos de prueba del sistema REFRIMASTE.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Elimina los datos existentes antes de cargar los de prueba.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            self._flush()
            self.stdout.write('Datos previos eliminados.')

        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Ya existen datos de prueba. Usa --flush para recargar.'))
            return

        hoy = timezone.localdate()

        # ------------------------------------------------------------------
        # Usuarios y roles
        # ------------------------------------------------------------------
        admin = self._crear_usuario(
            'admin', 'admin@refrimaste.com', 'Carlos', 'Administrador',
            User.Roles.ADMINISTRADOR, is_staff=True, is_superuser=True,
        )
        supervisor = self._crear_usuario(
            'supervisor', 'supervisor@refrimaste.com', 'Laura', 'Gómez',
            User.Roles.SUPERVISOR, is_staff=True,
        )
        tec1 = self._crear_usuario('tecnico1', 'tecnico1@refrimaste.com', 'Pedro', 'Ramírez', User.Roles.TECNICO)
        tec2 = self._crear_usuario('tecnico2', 'tecnico2@refrimaste.com', 'Ana', 'Torres', User.Roles.TECNICO)
        almacen = self._crear_usuario(
            'almacen', 'almacen@refrimaste.com', 'Jorge', 'Mora', User.Roles.ALMACEN
        )
        cli_user1 = self._crear_usuario('cliente1', 'cliente1@mail.com', 'María', 'López', User.Roles.CLIENTE)
        cli_user2 = self._crear_usuario('cliente2', 'cliente2@mail.com', 'Empresa', 'Frío Norte', User.Roles.CLIENTE)

        # ------------------------------------------------------------------
        # Clientes
        # ------------------------------------------------------------------
        cli1 = Cliente.objects.create(
            user=cli_user1,
            tipo=Cliente.TIPO_PERSONA,
            nombre='María',
            apellidos='López',
            tipo_documento='cc',
            documento_numero='123456789',
            email='cliente1@mail.com',
            telefono='8091234567',
            direccion='Av. 27 de Febrero # 45',
            ciudad='Santiago de los Caballeros',
        )
        cli2 = Cliente.objects.create(
            user=cli_user2,
            tipo=Cliente.TIPO_EMPRESA,
            nombre='Frío Norte S.A.S.',
            apellidos='',
            tipo_documento='nit',
            documento_numero='901234567',
            email='cliente2@mail.com',
            telefono='8297654321',
            direccion='Av. Salvador Estrella Sadhalá',
            ciudad='Santiago de los Caballeros',
        )
        cli3 = Cliente.objects.create(
            tipo=Cliente.TIPO_EMPRESA,
            nombre='Supermercado El Ahorro',
            apellidos='',
            tipo_documento='nit',
            documento_numero='800200300',
            email='ahorro@mail.com',
            telefono='8491112233',
            direccion='Calle del Sol # 120',
            ciudad='Puerto Plata',
        )

        DireccionInstalacion.objects.create(
            cliente=cli1, etiqueta='Casa', direccion='Av. 27 de Febrero # 45',
            ciudad='Santiago de los Caballeros', principal=True,
        )
        DireccionInstalacion.objects.create(
            cliente=cli2, etiqueta='Bodega central', direccion='Av. Salvador Estrella Sadhalá',
            ciudad='Santiago de los Caballeros', principal=True,
        )

        # ------------------------------------------------------------------
        # Tipos de equipo y equipos
        # ------------------------------------------------------------------
        tipo_ac, _ = TipoEquipo.objects.get_or_create(nombre='Aire acondicionado split')
        tipo_nevera, _ = TipoEquipo.objects.get_or_create(nombre='Nevera comercial')
        tipo_cuarto, _ = TipoEquipo.objects.get_or_create(nombre='Cuarto frío')
        TipoEquipo.objects.get_or_create(nombre='Vitrina refrigerada')
        TipoEquipo.objects.get_or_create(nombre='Congelador')

        e1 = Equipo.objects.create(
            cliente=cli1, tipo=tipo_ac, marca='LG', modelo='Inverter 12000',
            numero_serie='LG-AC-0001', capacidad='12000 BTU', refrigerante='R-410A',
            estado=Equipo.Estado.INSTALADO, fecha_instalacion=hoy - timedelta(days=30),
            ubicacion='Sala principal',
        )
        e2 = Equipo.objects.create(
            cliente=cli2, tipo=tipo_nevera, marca='Haceb', modelo='NV-450',
            numero_serie='HAC-NV-0001', capacidad='450 L', refrigerante='R-134a',
            estado=Equipo.Estado.INSTALADO, fecha_instalacion=hoy - timedelta(days=90),
            ubicacion='Zona de lácteos',
        )
        e3 = Equipo.objects.create(
            cliente=cli3, tipo=tipo_cuarto, marca='Küpferberg', modelo='CF-8x8',
            numero_serie='KUP-CF-0001', capacidad='8 x 8 m', refrigerante='R-404A',
            estado=Equipo.Estado.AVERIADO, ubicacion='Bodega principal',
        )

        # ------------------------------------------------------------------
        # Materiales e inventario
        # ------------------------------------------------------------------
        m1 = Material.objects.create(
            nombre='Gas refrigerante R-410A', codigo='REF-R410A',
            categoria='Refrigerantes', unidad_medida='libra',
            cantidad_disponible=40, stock_minimo=10, precio=25000,
        )
        m2 = Material.objects.create(
            nombre='Tubería de cobre 1/2"', codigo='TUB-COBRE-12',
            categoria='Tuberías', unidad_medida='metro',
            cantidad_disponible=80, stock_minimo=20, precio=15000,
        )
        m3 = Material.objects.create(
            nombre='Cable eléctrico 12 AWG', codigo='CAB-12',
            categoria='Eléctrico', unidad_medida='metro',
            cantidad_disponible=150, stock_minimo=50, precio=8000,
        )
        m4 = Material.objects.create(
            nombre='Filtro secador 1/4"', codigo='FIL-SEC-14',
            categoria='Filtros', unidad_medida='unidad',
            cantidad_disponible=5, stock_minimo=15, precio=12000,
        )
        Material.objects.create(
            nombre='Válvula de expansión', codigo='VAL-EXP',
            categoria='Válvulas', unidad_medida='unidad',
            cantidad_disponible=8, stock_minimo=5, precio=45000,
        )
        Material.objects.create(
            nombre='Aislante térmico 3/4"', codigo='AIS-34',
            categoria='Aislantes', unidad_medida='metro',
            cantidad_disponible=60, stock_minimo=10, precio=7000,
        )

        # ------------------------------------------------------------------
        # Solicitudes de instalación
        # ------------------------------------------------------------------
        sol1 = SolicitudInstalacion.objects.create(
            cliente=cli1,
            tipo_equipo_solicitado='Aire acondicionado split 12000 BTU',
            descripcion='Instalación de aire en sala principal',
            prioridad=SolicitudInstalacion.Prioridad.ALTA,
            estado=SolicitudInstalacion.Estado.APROBADA,
            fecha_deseada=hoy + timedelta(days=2),
        )
        sol2 = SolicitudInstalacion.objects.create(
            cliente=cli3,
            tipo_equipo_solicitado='Cuarto frío 8x8',
            descripcion='Nueva instalación para almacenar productos cárnicos',
            prioridad=SolicitudInstalacion.Prioridad.URGENTE,
            estado=SolicitudInstalacion.Estado.PENDIENTE,
            fecha_deseada=hoy + timedelta(days=5),
        )
        SolicitudInstalacion.objects.create(
            cliente=cli2,
            tipo_equipo_solicitado='Nevera comercial 450 L',
            descripcion='Reemplazo de nevera en zona de lácteos',
            prioridad=SolicitudInstalacion.Prioridad.MEDIA,
            estado=SolicitudInstalacion.Estado.RECHAZADA,
            fecha_deseada=hoy + timedelta(days=1),
        )

        # ------------------------------------------------------------------
        # Instalaciones
        # ------------------------------------------------------------------
        instalacion1 = Instalacion.objects.create(
            cliente=cli1,
            equipo=e1,
            tecnico=tec1.perfil_tecnico,
            solicitud=sol1,
            fecha_programada=timezone.now() + timedelta(days=2),
            prioridad=Instalacion.Prioridad.ALTA,
            direccion='Av. 27 de Febrero # 45',
            ciudad='Santiago de los Caballeros',
            estado=Instalacion.Estado.ASIGNADA,
        )
        Instalacion.objects.create(
            cliente=cli3,
            equipo=e3,
            tecnico=tec2.perfil_tecnico,
            solicitud=sol2,
            fecha_programada=timezone.now() + timedelta(days=5),
            prioridad=Instalacion.Prioridad.URGENTE,
            direccion='Calle del Sol # 120',
            ciudad='Puerto Plata',
            estado=Instalacion.Estado.PENDIENTE,
        )
        Instalacion.objects.create(
            cliente=cli2,
            equipo=e2,
            tecnico=tec1.perfil_tecnico,
            fecha_programada=timezone.now() - timedelta(days=90),
            fecha_instalacion=timezone.now() - timedelta(days=89),
            prioridad=Instalacion.Prioridad.MEDIA,
            direccion='Av. Salvador Estrella Sadhalá',
            ciudad='Santiago de los Caballeros',
            estado=Instalacion.Estado.FINALIZADA,
            observaciones='Instalación finalizada sin novedades.',
        )

        # ------------------------------------------------------------------
        # Órdenes de servicio
        # ------------------------------------------------------------------
        orden1 = OrdenServicio.objects.create(
            cliente=cli1,
            equipo=e1,
            tecnico=tec1.perfil_tecnico,
            tipo_servicio=OrdenServicio.TipoServicio.MANTENIMIENTO_PREVENTIVO,
            fecha=hoy - timedelta(days=10),
            problema_reportado='No enfría adecuadamente',
            diagnostico='Fuga leve de refrigerante en la línea de succión',
            trabajo_realizado='Recarga de refrigerante y ajuste de presiones',
            estado=OrdenServicio.Estado.FINALIZADA,
            observaciones='El equipo quedó operando en parámetros normales.',
            fecha_asignacion=timezone.now() - timedelta(days=11),
            fecha_finalizacion=timezone.now() - timedelta(days=10),
        )
        orden2 = OrdenServicio.objects.create(
            cliente=cli3,
            equipo=e3,
            tecnico=tec2.perfil_tecnico,
            tipo_servicio=OrdenServicio.TipoServicio.REPARACION,
            fecha=hoy,
            problema_reportado='El cuarto frío no baja de temperatura',
            estado=OrdenServicio.Estado.ASIGNADA,
            fecha_asignacion=timezone.now(),
        )
        orden3 = OrdenServicio.objects.create(
            cliente=cli2,
            equipo=e2,
            tecnico=tec1.perfil_tecnico,
            tipo_servicio=OrdenServicio.TipoServicio.MANTENIMIENTO_CORRECTIVO,
            fecha=hoy - timedelta(days=3),
            problema_reportado='Ruido excesivo en el compresor',
            diagnostico='Compresor con desgaste en rodamientos',
            trabajo_realizado='Reemplazo de compresor',
            estado=OrdenServicio.Estado.EN_PROCESO,
            observaciones='Se espera repuesto adicional.',
        )

        # Materiales utilizados en orden1 (descuentan inventario)
        MaterialUtilizado.objects.create(
            orden=orden1, material=m1, cantidad=2, precio_unitario=25000,
        )
        MaterialUtilizado.objects.create(
            orden=orden1, material=m2, cantidad=3, precio_unitario=15000,
        )
        m1.cantidad_disponible -= 2
        m1.save(update_fields=['cantidad_disponible'])
        m2.cantidad_disponible -= 3
        m2.save(update_fields=['cantidad_disponible'])

        # Historial de estados (RN-09)
        for orden, transicion in [
            (orden1, ('pendiente', 'asignada')),
            (orden1, ('asignada', 'en_proceso')),
            (orden1, ('en_proceso', 'finalizada')),
            (orden2, ('pendiente', 'asignada')),
            (orden3, ('pendiente', 'asignada')),
            (orden3, ('asignada', 'en_proceso')),
        ]:
            EstadoOrdenLog.objects.create(
                orden=orden, estado_anterior=transicion[0],
                estado_nuevo=transicion[1], usuario=admin,
            )

        # ------------------------------------------------------------------
        # Mantenimientos
        # ------------------------------------------------------------------
        Mantenimiento.objects.create(
            equipo=e1, cliente=cli1, tecnico=tec1.perfil_tecnico,
            tipo='preventivo', fecha=hoy, proxima_fecha=hoy + timedelta(days=45),
            descripcion='Limpieza de filtros y verificación de presiones',
            estado='realizado', costo=80000,
        )
        Mantenimiento.objects.create(
            equipo=e2, cliente=cli2, tecnico=tec2.perfil_tecnico,
            tipo='preventivo', fecha=hoy, proxima_fecha=hoy + timedelta(days=10),
            descripcion='Mantenimiento preventivo trimestral',
            estado='pendiente', costo=120000,
        )
        Mantenimiento.objects.create(
            equipo=e3, cliente=cli3, tecnico=tec1.perfil_tecnico,
            tipo='correctivo', fecha=hoy - timedelta(days=2),
            descripcion='Corrección de fuga en evaporador',
            estado='en_proceso', costo=0,
        )
        Mantenimiento.objects.create(
            equipo=e1, cliente=cli1, tecnico=tec2.perfil_tecnico,
            tipo='preventivo', fecha=hoy - timedelta(days=15),
            proxima_fecha=hoy + timedelta(days=20),
            descripcion='Revisión semestral',
            estado='pendiente',
        )

        # ------------------------------------------------------------------
        # Cotizaciones
        # ------------------------------------------------------------------
        cot1 = Cotizacion.objects.create(
            cliente=cli1, solicitud=sol1, tecnico=tec1.perfil_tecnico,
            descuento=0, estado='pendiente', notas='Incluye mano de obra y tubería.',
        )
        CotizacionDetalle.objects.create(
            cotizacion=cot1, descripcion='Equipo LG Inverter 12000 BTU',
            cantidad=1, precio_unitario=2800000,
        )
        CotizacionDetalle.objects.create(
            cotizacion=cot1, descripcion='Instalación y puesta en marcha',
            cantidad=1, precio_unitario=350000,
        )
        CotizacionDetalle.objects.create(
            cotizacion=cot1, descripcion='Tubería de cobre y aislante',
            cantidad=1, precio_unitario=120000,
        )

        # ------------------------------------------------------------------
        # Pagos y facturas
        # ------------------------------------------------------------------
        pago1 = Pago.objects.create(
            cliente=cli1, orden=orden1, monto=400000, es_abono=False,
            metodo='transferencia', fecha=hoy - timedelta(days=9),
            estado='pagado', registrado_por=admin,
        )
        factura = Factura.objects.create(
            cliente=cli1, orden=orden1, iva=76000, creado_por=admin,
            notas='Factura por mantenimiento preventivo.',
        )
        factura.pagos.add(pago1)
        factura.calcular_totales()

        Pago.objects.create(
            cliente=cli3, orden=orden2, monto=0, es_abono=True,
            metodo='efectivo', fecha=hoy, estado='pendiente', registrado_por=admin,
        )

        # ------------------------------------------------------------------
        # Evaluaciones (RN-10)
        # ------------------------------------------------------------------
        EvaluacionServicio.objects.create(
            cliente=cli1, orden=orden1, calificacion=5,
            comentario='Excelente servicio, muy puntual.',
        )

        # ------------------------------------------------------------------
        # Resumen
        # ------------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS('Datos de prueba cargados correctamente.'))
        self.stdout.write('')
        self.stdout.write('Usuarios creados (contraseña: Refrimaste2026!):')
        self.stdout.write('  admin      -> Administrador (superusuario)')
        self.stdout.write('  supervisor -> Supervisor')
        self.stdout.write('  tecnico1   -> Técnico')
        self.stdout.write('  tecnico2   -> Técnico')
        self.stdout.write('  almacen    -> Almacén')
        self.stdout.write('  cliente1   -> Cliente (María López)')
        self.stdout.write('  cliente2   -> Cliente (Frío Norte S.A.S.)')

    def _crear_usuario(self, username, email, first_name, last_name, role,
                       is_staff=False, is_superuser=False):
        user = User.objects.create_user(
            username=username,
            email=email,
            password=PASSWORD,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_staff=is_staff,
            is_superuser=is_superuser,
        )
        return user

    def _flush(self):
        from django.core.management import call_command
        call_command('flush', interactive=False, verbosity=0)
