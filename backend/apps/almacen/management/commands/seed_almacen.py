"""Sembrado de la vitrina de Almacén: categorías, productos e imágenes SVG."""
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.almacen.models import Categoria, Producto

FRONTEND_ASSETS = Path(__file__).resolve().parents[4].parent / 'frontend' / 'assets' / 'img' / 'productos'

CATEGORIAS = [
    ('Tubería de cobre', 'Tuberías flexibles y rígidas para líneas de refrigeración', 'polyline'),
    ('Refrigerantes', 'Gases refrigerantes para sistemas de climatización', 'propane_tank'),
    ('Equipos de aire acondicionado', 'Split, centrales y unidades de techo', 'ac_unit'),
    ('Manejadoras', 'Unidades manejadoras de aire para climatización', 'air'),
    ('Condensadoras', 'Condensadoras para instalaciones comerciales e industriales', 'heat_pump'),
    ('Evaporadores', 'Evaporadores para cuartos fríos y vitrinas', 'air'),
    ('Compresores', 'Compresores herméticos y semi-herméticos', 'compress'),
    ('Capacitores', 'Capacitores de arranque y marcha para motores', 'bolt'),
    ('Controles y termostatos', 'Controles de temperatura y termostatos digitales', 'tune'),
    ('Filtros', 'Filtros deshidratadores y de aire', 'filter_alt'),
    ('Productos de limpieza de aire', 'Limpiadores, desinfectantes y sprays para sistemas de aire', 'cleaning_services'),
    ('Motores y ventiladores', 'Motores y ventiladores para condensación y evaporación', 'toys_fan'),
    ('Materiales de instalación', 'Abrazaderas, aislantes, soldadura y accesorios de línea', 'handyman'),
    ('Herramientas de refrigeración', 'Herramientas profesionales para instalación y servicio', 'handyman'),
    ('Accesorios de refrigeración', 'Accesorios y repuestos complementarios', 'inventory_2'),
]

PRODUCTOS = {
    'Tubería de cobre': [
        ('Tubería de cobre 1/4" x 1/2"', 'ROLLO DE TUBERÍA',
         'Tubería de cobre recocido para líneas de succión y líquido.', 145000, 60),
        ('Tubería de cobre 3/8" x 3/4"', 'ROLLO DE TUBERÍA',
         'Tubería de cobre grado refrigeración, alta resistencia.', 198000, 35),
    ],
    'Refrigerantes': [
        ('Gas refrigerante R-410A', 'CILINDRO 25 LB',
         'Refrigerante para equipos de aire acondicionado modernos.', 890000, 12),
        ('Gas refrigerante R-134a', 'CILINDRO 30 LB',
         'Refrigerante ecológico para sistemas de media temperatura.', 760000, 8),
        ('Gas refrigerante R-22', 'CILINDRO 30 LB',
         'Refrigerante para sistemas de refrigeración comercial.', None, 0),
    ],
    'Equipos de aire acondicionado': [
        ('Aire acondicionado split 12.000 BTU', 'UNIDAD',
         'Split inverter de alta eficiencia para espacios hasta 25 m².', 2450000, 15),
        ('Aire acondicionado split 24.000 BTU', 'UNIDAD',
         'Split inverter para oficinas y salas comerciales.', 3850000, 9),
        ('Aire central 36.000 BTU', 'UNIDAD',
         'Sistema centralizado por conductos para locales amplios.', 6900000, 4),
    ],
    'Manejadoras': [
        ('Manejadora de aire MHP-300', 'UNIDAD',
         'Unidad manejadora de aire para climatización central.', None, 3),
        ('Manejadora de aire MHP-600', 'UNIDAD',
         'Manejadora de doble entrada para proyectos industriales.', None, 2),
    ],
    'Condensadoras': [
        ('Condensadora R-410A 36.000 BTU', 'UNIDAD',
         'Condensadora monofásica para split y central.', 4350000, 6),
        ('Condensadora industrial 10 HP', 'UNIDAD',
         'Condensadora trifásica para cámaras de refrigeración.', None, 2),
    ],
    'Evaporadores': [
        ('Evaporador para cuarto frío 1.500 BTU/h', 'UNIDAD',
         'Evaporador de baja temperatura con descongelación eléctrica.', 2950000, 5),
        ('Evaporador de vitrina exhibidora', 'UNIDAD',
         'Evaporador compacto para vitrinas refrigeradas.', 1450000, 7),
    ],
    'Compresores': [
        ('Compresor hermético 1/3 HP R-134a', 'UNIDAD',
         'Compresor rotativo para refrigeración comercial.', 680000, 10),
        ('Compresor scroll 3 HP R-410A', 'UNIDAD',
         'Compresor scroll de alta eficiencia para acondicionamiento.', 2400000, 4),
    ],
    'Capacitores': [
        ('Capacitor de marcha 35 µF 450 V', 'UNIDAD',
         'Capacitor de marcha para motores de condensación.', 48000, 80),
        ('Capacitor de arranque 88-108 µF', 'UNIDAD',
         'Capacitor de arranque para compresores monofásicos.', 56000, 45),
    ],
    'Controles y termostatos': [
        ('Termostato digital de pared', 'UNIDAD',
         'Termostato digital programable para split y central.', 145000, 25),
        ('Control de temperatura para cuarto frío', 'UNIDAD',
         'Control digital con sensor NTC y alarma de alta temperatura.', 210000, 18),
    ],
    'Filtros': [
        ('Filtro deshidratador 1/4"', 'UNIDAD',
         'Filtro deshidratador para línea de líquido, conexión 1/4".', 25000, 120),
        ('Filtro deshidratador 3/8"', 'UNIDAD',
         'Filtro deshidratador bi-flow para sistemas inverter.', 32000, 90),
    ],
    'Productos de limpieza de aire': [
        ('Limpiador de evaporadores spray 500 ml', 'UNIDAD',
         'Spray limpiador para aletas de evaporadores y condensadores.', 35000, 60),
        ('Desinfectante de conductos aerosol', 'UNIDAD',
         'Aerosol desinfectante para conductos de aire acondicionado.', 42000, 45),
    ],
    'Motores y ventiladores': [
        ('Motor ventilador de condensación 1/4 HP', 'UNIDAD',
         'Motor con hélice de 3 aspas para condensadoras.', 420000, 14),
        ('Ventilador evaporador 220V', 'UNIDAD',
         'Ventilador axial para evaporadores de cuartos fríos.', 380000, 11),
    ],
    'Materiales de instalación': [
        ('Kit de instalación acondicionador', 'KIT',
         'Kit completo: tubería, aislante, cableado y accesorios.', 185000, 40),
        ('Aislante térmico para tubería 1/2"', 'METRO',
         'Aislante elastomérico para líneas de refrigeración.', 12000, 200),
    ],
    'Herramientas de refrigeración': [
        ('Manifold con mangueras', 'KIT',
         'Manifold de doble vía con mangueras de 60".', 460000, 9),
        ('Bomba de vacío 3 CFM', 'UNIDAD',
         'Bomba de vacío de dos etapas para evacuación de sistemas.', 750000, 6),
    ],
    'Accesorios de refrigeración': [
        ('Presostato de alta y baja presión', 'UNIDAD',
         'Presostato ajustable para protección de compresores.', 185000, 22),
        ('Mirilla para línea de líquido', 'UNIDAD',
         'Indicador de humedad y nivel de refrigerante.', 65000, 30),
    ],
}

SLUGS = {
    'Tubería de cobre': 'tuberia-cobre',
    'Refrigerantes': 'refrigerantes',
    'Equipos de aire acondicionado': 'aire-acondicionado',
    'Manejadoras': 'manejadoras',
    'Condensadoras': 'condensadoras',
    'Evaporadores': 'evaporadores',
    'Compresores': 'compresores',
    'Capacitores': 'capacitores',
    'Controles y termostatos': 'controles-termostatos',
    'Filtros': 'filtros',
    'Productos de limpieza de aire': 'limpieza-aire',
    'Motores y ventiladores': 'motores-ventiladores',
    'Materiales de instalación': 'materiales-instalacion',
    'Herramientas de refrigeración': 'herramientas',
    'Accesorios de refrigeración': 'accesorios',
}


def _svg(slug, nombre):
    name = nombre.replace('&', '&amp;')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560" width="800" height="560">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0EA5E9"/>
      <stop offset="1" stop-color="#06B6D4"/>
    </linearGradient>
  </defs>
  <rect width="800" height="560" fill="url(#bg)"/>
  <circle cx="680" cy="90" r="160" fill="#ffffff" opacity="0.08"/>
  <circle cx="90" cy="480" r="190" fill="#082F49" opacity="0.12"/>
  <rect x="40" y="40" width="720" height="480" rx="28" fill="none" stroke="#ffffff" stroke-opacity="0.25" stroke-width="3"/>
  <rect x="255" y="195" width="290" height="150" rx="18" fill="#ffffff" opacity="0.16"/>
  <path d="M380 215 L330 260 L365 260 L315 310 L335 335 L390 282 L360 282 L410 235 Z" fill="#ffffff" opacity="0.9"/>
  <rect x="170" y="420" width="460" height="44" rx="22" fill="#082F49" opacity="0.55"/>
  <text x="400" y="450" font-family="Inter, Arial, sans-serif" font-size="22" font-weight="600" fill="#ffffff" text-anchor="middle">{name}</text>
</svg>'''


class Command(BaseCommand):
    help = 'Crea las categorías y productos de la vitrina de Almacén con sus imágenes SVG.'

    def handle(self, *args, **options):
        FRONTEND_ASSETS.mkdir(parents=True, exist_ok=True)

        for idx, (nombre, descripcion, icono) in enumerate(CATEGORIAS):
            cat, _ = Categoria.objects.update_or_create(
                nombre=nombre,
                defaults={'descripcion': descripcion, 'icono': icono, 'orden': idx + 1},
            )

            slug = SLUGS[nombre]
            imagen = f'/assets/img/productos/{slug}.svg'
            (FRONTEND_ASSETS / f'{slug}.svg').write_text(_svg(slug, nombre), encoding='utf-8')

            for i, (pnombre, unidad, pdesc, precio, stock) in enumerate(PRODUCTOS.get(nombre, [])):
                defaults = {
                    'categoria': cat,
                    'descripcion': pdesc,
                    'imagen': imagen,
                    'precio': precio,
                    'disponible': stock > 0,
                    'stock': stock,
                    'destacado': i == 0,
                }

                existente = Producto.objects.filter(nombre=pnombre).first()
                if existente and existente.imagen:
                    del defaults['imagen']

                Producto.objects.update_or_create(
                    nombre=pnombre,
                    defaults=defaults,
                )

        self.stdout.write(self.style.SUCCESS(f'Vitrina de Almacén lista: {Categoria.objects.count()} categorías, {Producto.objects.count()} productos.'))
