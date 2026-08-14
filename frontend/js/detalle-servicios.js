/* ==========================================================================
   RefriMaster — Detalle público de servicios de Mantenimiento y Reparaciones
   - URL: /servicio/?seccion=mantenimiento|reparacion&tipo=<slug>
   - Renderiza la información de cada servicio SIN requerir autenticación.
   - La autenticación solo se pide al pulsar "Solicitar servicio/reparación"
     (flujo gestionado por servicios-publicos.js).
   ========================================================================== */

(function () {
  'use strict';

  var SERVICIOS = {
    mantenimiento: {
      titulo: 'Mantenimiento',
      chip: 'MANTENIMIENTO 4.0',
      dataServicio: 'mantenimiento',
      cta: 'Solicitar servicio',
      volver: '/mantenimiento/',
      volverLabel: 'Ver todos los tipos de mantenimiento',
      seccionEquipos: 'Equipos a los que aplica',
      tipos: {
        preventivo: {
          nombre: 'Mantenimiento preventivo',
          tagline: 'Visitas programadas para mantener tus equipos en óptimas condiciones y evitar fallas costosas.',
          descripcion: 'El mantenimiento preventivo consiste en visitas técnicas programadas (mensual, bimestral o trimestral) en las que se realiza limpieza profunda, ajuste y verificación de todos los componentes, detectando desgastes tempranos antes de que se conviertan en fallas.',
          precio: 'RD$ 1,500',
          precioEtiqueta: 'Desde',
          incluye: [
            'Limpieza y/o cambio de filtros de aire',
            'Limpieza de serpentina evaporadora y condensadora',
            'Verificación de presiones y carga de refrigerante',
            'Revisión de drenaje, bandeja y dren',
            'Medición de amperaje, voltaje y consumo eléctrico',
            'Revisión de capacitores, arrancadores y contactores',
            'Verificación del termostato y controles electrónicos',
            'Lubricación de motores y ventiladores',
            'Reporte técnico con estado del equipo y recomendaciones',
          ],
          beneficios: [
            'Hasta un 30% de ahorro energético',
            'Menor probabilidad de fallas inesperadas',
            'Mayor vida útil del compresor y componentes',
            'Mejor calidad del aire interior',
            'Programación flexible según tu operación',
          ],
          equipos: [
            'Aires acondicionados split, cassette, ventana y centrales',
            'Refrigeradores y vitrinas comerciales',
            'Neveras y congeladores',
            'Cámaras frigoríficas pequeñas y medianas',
          ],
          adicional: [
            'Garantía del servicio por escrito',
            'Cobertura en Santiago y regiones',
            'Reporte técnico digital por cada visita',
          ],
          equipoSolicitud: 'Servicio de mantenimiento preventivo de equipos de refrigeración',
        },
        correctivo: {
          nombre: 'Mantenimiento correctivo',
          tagline: 'Reparación de fallas ya detectadas para devolver la operación de tu equipo lo antes posible.',
          descripcion: 'Cuando el equipo ya presenta una falla —falta de enfriamiento, fugas, ruidos o componentes dañados— el mantenimiento correctivo interviene para diagnosticar la causa, repararla y dejar el sistema funcionando con pruebas de rendimiento.',
          precio: 'RD$ 2,000',
          precioEtiqueta: 'Desde',
          incluye: [
            'Diagnóstico y localización de la falla',
            'Corrección de fugas de refrigerante',
            'Recarga de refrigerante con verificación',
            'Cambio de capacitores, motores, sensores o tarjetas',
            'Limpieza de componentes afectados',
            'Pruebas de arranque y funcionamiento',
            'Reporte técnico y recomendaciones',
          ],
          beneficios: [
            'Restauración rápida de la operación',
            'Previene daños mayores al compresor',
            'Diagnóstico transparente y cotización previa',
            'Repuestos originales o certificados',
            'Garantía escrita sobre el trabajo',
          ],
          equipos: [
            'Aires acondicionados de todo tipo',
            'Vitrinas, neveras y congeladores comerciales',
            'Equipos de refrigeración industrial',
            'Unidades de refrigeración de transporte',
          ],
          adicional: [
            'La mano de obra y repuestos se cotizan antes de intervenir',
            'Atención prioritaria para comercios y cadenas de frío',
            'Disponibilidad 24/7 para emergencias',
          ],
          equipoSolicitud: 'Servicio de mantenimiento correctivo de equipos de refrigeración',
        },
        predictivo: {
          nombre: 'Mantenimiento predictivo',
          tagline: 'Análisis técnico de tendencias para anticipar fallas antes de que ocurran.',
          descripcion: 'El mantenimiento predictivo utiliza mediciones precisas de presiones, temperaturas, consumo eléctrico y vibraciones para evaluar el estado real de los equipos y programar intervenciones justo antes de que ocurra una falla.',
          precio: 'RD$ 6,000',
          precioEtiqueta: 'Desde',
          incluye: [
            'Medición de presiones y temperaturas de operación',
            'Análisis de consumo eléctrico y amperaje',
            'Termografía básica de componentes',
            'Inspección de vibraciones y ruidos',
            'Análisis de tendencias históricas',
            'Informe técnico con plan de acción',
          ],
          beneficios: [
            'Reduce paradas no planificadas',
            'Optimiza el ciclo de vida de los equipos',
            'Prioriza inversiones con datos reales',
            'Mayor control y trazabilidad operativa',
          ],
          equipos: [
            'Plantas industriales y cuartos fríos',
            'Cámaras frigoríficas y túneles',
            'Sistemas de climatización central',
            'Sistemas de refrigeración de precisión',
          ],
          adicional: [
            'Ideal para operaciones críticas y cadenas de frío',
            'Se puede combinar con planes preventivos',
            'Reporte con recomendaciones por equipo',
          ],
          equipoSolicitud: 'Servicio de mantenimiento predictivo de equipos de refrigeración',
        },
        'plan-anual': {
          nombre: 'Plan anual completo',
          tagline: 'Programa integral con visitas programadas, prioridad de atención y descuentos durante todo el año.',
          descripcion: 'Es la forma más conveniente de proteger tus equipos: un contrato de mantenimiento que incluye visitas preventivas programadas, atención prioritaria ante emergencias, descuentos en reparaciones y seguimiento documentado de cada equipo.',
          precio: 'RD$ 18,000',
          precioEtiqueta: 'Desde',
          incluye: [
            'Visitas preventivas programadas durante el año',
            'Prioridad en la atención de emergencias',
            'Descuento en reparaciones y repuestos',
            'Seguimiento documentado por equipo',
            'Asesoría técnica continua',
            'Reportes anuales de estado de tu flota',
          ],
          beneficios: [
            'Costo predecible y presupuestable',
            'Atención prioritaria para tu operación',
            'Máxima vida útil de los equipos',
            'Tranquilidad operativa todo el año',
            'Un solo aliado para toda tu flota',
          ],
          equipos: [
            'Todos los equipos de refrigeración y climatización de tu empresa',
            'Múltiples equipos con tarifas preferenciales',
            'Sucursales y flota bajo un mismo plan',
          ],
          adicional: [
            'Planes personalizados según cantidad y tipo de equipos',
            'Ideal para empresas, comercios y cadenas',
            'Incluye reporte técnico en cada visita',
          ],
          equipoSolicitud: 'Plan anual de mantenimiento de equipos de refrigeración',
        },
      },
    },
    reparacion: {
      titulo: 'Reparaciones',
      chip: 'REPARACIÓN ESPECIALIZADA',
      dataServicio: 'reparacion',
      cta: 'Solicitar reparación',
      volver: '/reparaciones/',
      volverLabel: 'Ver todos los tipos de reparación',
      seccionEquipos: 'Equipos que reparamos',
      tipos: {
        'aire-acondicionado': {
          nombre: 'Reparación de aire acondicionado',
          tagline: 'Diagnóstico y reparación profesional de aires acondicionados residenciales y comerciales.',
          descripcion: 'Reparamos todo tipo de aires acondicionados: split, cassette, ventana, piso-techo, paquete y centrales, tanto convencionales como inverter. Realizamos diagnóstico completo, reparación mecánica y eléctrica, y pruebas de funcionamiento.',
          precio: 'RD$ 800',
          precioEtiqueta: 'Diagnóstico desde',
          problemas: [
            'No enfría o baja capacidad',
            'Fugas de agua por drenajes obstruidos',
            'Ruidos y vibraciones anormales',
            'Compresor quemado o sobrecalentado',
            'Problemas eléctricos y de arranque',
            'Códigos de error en pantalla',
            'Olores y mala calidad del aire',
          ],
          equipos: [
            'Split y multi-split',
            'Cassette y piso-techo',
            'Unidades de ventana',
            'Paquetes (package) y centrales',
            'Sistemas inverter y convencionales',
          ],
          incluye: [
            'Diagnóstico con mediciones de presión y temperatura',
            'Reparación mecánica y eléctrica',
            'Recarga de refrigerante con verificación',
            'Cambio de repuestos originales o certificados',
            'Pruebas de arranque y ciclo de enfriamiento',
            'Garantía escrita del servicio',
          ],
          diagnostico: 'Realizamos una revisión integral del equipo: presiones, temperaturas, amperaje y estado de componentes. Con el resultado te presentamos una cotización clara antes de intervenir; si apruebas la reparación, el diagnóstico se descuenta.',
          adicional: [
            'Atención urgente para comercios y oficinas',
            'Repuestos disponibles en nuestro almacén',
            'Servicio técnico certificado',
          ],
          equipoSolicitud: 'Reparación de equipo de aire acondicionado',
        },
        comercial: {
          nombre: 'Reparación de refrigeración comercial',
          tagline: 'Reparación de vitrinas, neveras, congeladores y cuartos fríos para tu negocio.',
          descripcion: 'Especialistas en mantener operativa la cadena de frío de supermercados, colmados, restaurantes y farmacias. Reparamos fugas, fallas de compresor, problemas de temperatura y controles, con el menor impacto en tu operación.',
          precio: 'RD$ 1,000',
          precioEtiqueta: 'Diagnóstico desde',
          problemas: [
            'Temperatura fuera de rango',
            'Ciclado excesivo del compresor',
            'Fugas de refrigerante',
            'Hielo excesivo en el evaporador',
            'Ruidos del compresor',
            'Controles y descongelación fallando',
          ],
          equipos: [
            'Vitrinas refrigeradas',
            'Neveras de puerta y congeladores verticales',
            'Islas de congelados',
            'Bodegas de bebidas',
            'Cuartos fríos pequeños y medianos',
          ],
          incluye: [
            'Diagnóstico completo del sistema',
            'Reparación y recarga de refrigerante',
            'Cambio de componentes y empaques',
            'Limpieza y revisión de condensación',
            'Pruebas de temperatura y rendimiento',
            'Garantía escrita del servicio',
          ],
          diagnostico: 'Verificamos temperaturas, presiones, consumo eléctrico, sellos de puertas y flujo de aire. Con el diagnóstico te entregamos una cotización clara; si apruebas, se descuenta del total de la reparación.',
          adicional: [
            'Horarios flexibles para no detener la operación',
            'Soporte y planes de mantenimiento comercial',
            'Atención a cadenas y negocios múltiples',
          ],
          equipoSolicitud: 'Reparación de equipo de refrigeración comercial',
        },
        industrial: {
          nombre: 'Reparación de refrigeración industrial',
          tagline: 'Soluciones para cámaras frigoríficas, túneles de congelación y sistemas de amoníaco.',
          descripcion: 'Atendemos la refrigeración industrial de alto rendimiento: cámaras frigoríficas, cuartos de congelación, túneles y sistemas con amoníaco o CO2. Nuestros técnicos diagnostican el ciclo completo y ejecutan reparaciones con equipos de medición especializados.',
          precio: 'RD$ 1,500',
          precioEtiqueta: 'Diagnóstico desde',
          problemas: [
            'Caídas de temperatura en cámaras',
            'Fallos en compresores de alta capacidad',
            'Sistemas con amoníaco o CO2',
            'Pérdida de carga de refrigerante',
            'Controles y PLCs desconfigurados',
            'Descongelación deficiente',
          ],
          equipos: [
            'Cámaras frigoríficas y cuartos fríos',
            'Túneles de congelación',
            'Cuartos de maduración y secado',
            'Sistemas de amoníaco y CO2',
            'Centrales de enfriamiento',
          ],
          incluye: [
            'Diagnóstico del sistema completo',
            'Reparación mecánica, eléctrica y de controles',
            'Recarga y balance de refrigerante',
            'Calibración de controladores',
            'Puesta en marcha y pruebas de rendimiento',
            'Reporte técnico y garantía escrita',
          ],
          diagnostico: 'Realizamos análisis del ciclo de refrigeración, balance de refrigerante, aislamiento eléctrico y rendimiento térmico. Presentamos un informe y cotización antes de cualquier intervención.',
          adicional: [
            'Personal con experiencia en entornos industriales',
            'Planes de mantenimiento continuo',
            'Disponibilidad 24/7 para operaciones críticas',
          ],
          equipoSolicitud: 'Reparación de equipo de refrigeración industrial',
        },
        transporte: {
          nombre: 'Reparación de refrigeración de transporte',
          tagline: 'Reparación de unidades de frío para camiones, furgones y contenedores.',
          descripcion: 'Reparamos unidades de refrigeración montadas en camiones, furgones y contenedores para que la cadena de frío no se detenga en ruta. Atención en planta o en sitio según lo requiera tu operación.',
          precio: 'RD$ 1,200',
          precioEtiqueta: 'Diagnóstico desde',
          problemas: [
            'Unidad sin enfriar en ruta',
            'Compresor del camión no arranca',
            'Fugas de refrigerante',
            'Controlador de temperatura fallando',
            'Falta de mantenimiento pre-trip',
            'Sobrecalentamiento del motor de la unidad',
          ],
          equipos: [
            'Unidades de frío para camiones',
            'Furgones refrigerados',
            'Contenedores refrigerados (reefer)',
            'Transporte de alimentos y medicamentos',
          ],
          incluye: [
            'Diagnóstico del sistema completo',
            'Reparación mecánica y eléctrica',
            'Recarga de refrigerante',
            'Cambio de repuestos y sensores',
            'Pruebas de enfriamiento y autonomía',
            'Reporte técnico y garantía escrita',
          ],
          diagnostico: 'Revisamos la unidad en planta o en ruta: compresor, controlador, registros de temperatura y estado general. Con el diagnóstico entregamos una cotización clara antes de reparar.',
          adicional: [
            'Atención en ruta o en planta',
            'Soporte 24/7 para no detener la cadena de frío',
            'Contratos de soporte para flotas',
          ],
          equipoSolicitud: 'Reparación de unidad de refrigeración de transporte',
        },
      },
    },
  };

  /* ---------- Utilidades ---------- */
  function $(sel) {
    return document.querySelector(sel);
  }

  function lista(items, icono) {
    return items.map(function (item) {
      return '<li class="flex items-start gap-3">' +
        '<span class="material-symbols-outlined text-primary">' + (icono || 'check_circle') + '</span>' +
        '<p class="text-sm leading-relaxed text-on-surface-variant">' + item + '</p>' +
        '</li>';
    }).join('');
  }

  function listaEquipos(items) {
    return items.map(function (item) {
      return '<span class="inline-flex items-center gap-2 rounded-full bg-primary-container px-4 py-2 text-sm font-semibold text-on-primary-container ring-1 ring-inset ring-primary/20">' +
        '<span class="material-symbols-outlined text-base">electrical_services</span>' + item +
        '</span>';
    }).join('');
  }

  function seccionIncluye(items) {
    return '<section class="bg-surface-container py-16">' +
      '<div class="mx-auto max-w-container-max px-lg">' +
      '<span class="font-label-md font-bold text-primary">COBERTURA</span>' +
      '<h2 class="mt-2 font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">Qué incluye</h2>' +
      '<ul class="mt-6 grid gap-3 sm:grid-cols-2">' + lista(items) + '</ul>' +
      '</div></section>';
  }

  function seccionProblemas(items) {
    return '<section class="bg-white py-16">' +
      '<div class="mx-auto max-w-container-max px-lg">' +
      '<span class="font-label-md font-bold text-primary">DETECCIÓN</span>' +
      '<h2 class="mt-2 font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">Tipos de problemas que atendemos</h2>' +
      '<ul class="mt-6 grid gap-3 sm:grid-cols-2">' + lista(items, 'build') + '</ul>' +
      '</div></section>';
  }

  function seccionBeneficios(items) {
    return '<section class="bg-white py-16">' +
      '<div class="mx-auto max-w-container-max px-lg">' +
      '<span class="font-label-md font-bold text-primary">BENEFICIOS</span>' +
      '<h2 class="mt-2 font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">Beneficios del servicio</h2>' +
      '<ul class="mt-6 grid gap-3 sm:grid-cols-2">' + lista(items, 'auto_awesome') + '</ul>' +
      '</div></section>';
  }

  function seccionEquipos(items, titulo) {
    return '<section class="bg-surface-container py-16">' +
      '<div class="mx-auto max-w-container-max px-lg">' +
      '<span class="font-label-md font-bold text-primary">ALCANCE</span>' +
      '<h2 class="mt-2 font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">' + titulo + '</h2>' +
      '<div class="mt-6 flex flex-wrap gap-3">' + listaEquipos(items) + '</div>' +
      '</div></section>';
  }

  function seccionDiagnostico(texto) {
    return '<section class="bg-white py-16">' +
      '<div class="mx-auto max-w-container-max px-lg">' +
      '<div class="rounded-3xl border border-outline-variant bg-surface-container-low p-8 sm:p-10">' +
      '<span class="inline-flex w-fit items-center gap-2 rounded-full bg-primary-container px-4 py-1.5 font-label-md font-bold text-on-primary-container ring-1 ring-inset ring-primary/20">' +
      '<span class="material-symbols-outlined text-sm">search</span>DIAGNÓSTICO</span>' +
      '<h2 class="mt-4 font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">¿Cómo diagnosticamos tu equipo?</h2>' +
      '<p class="mt-3 max-w-3xl font-body-md leading-relaxed text-on-surface-variant">' + texto + '</p>' +
      '</div></div></section>';
  }

  function seccionPrecioAdicional(precio, etiqueta, items) {
    return '<section class="bg-surface-container py-16">' +
      '<div class="mx-auto grid max-w-container-max gap-6 px-lg lg:grid-cols-2">' +
      '<div class="rounded-3xl border-2 border-primary/40 bg-primary-container/40 p-8">' +
      '<span class="font-label-md font-bold text-primary">PRECIO ORIENTATIVO</span>' +
      '<p class="mt-3 text-sm text-on-surface-variant">' + etiqueta + '</p>' +
      '<p class="font-headline-lg text-4xl font-extrabold tracking-tight text-on-surface md:text-5xl">' + precio + '</p>' +
      '<p class="mt-2 text-sm text-on-surface-variant">Los precios son orientativos y pueden variar según tipo, cantidad y capacidad de los equipos. Incluye visita y reporte técnico.</p>' +
      '</div>' +
      '<div class="rounded-3xl border border-outline-variant bg-white p-8">' +
      '<span class="font-label-md font-bold text-primary">INFORMACIÓN ADICIONAL</span>' +
      '<ul class="mt-6 space-y-4">' + lista(items, 'info') + '</ul>' +
      '</div>' +
      '</div></section>';
  }

  function render(seccion, slug) {
    var cfg = SERVICIOS[seccion];
    var tipo = cfg && cfg.tipos[slug];
    var detalle = $('#detalle');
    var notFound = $('#detalle-notfound');
    if (!cfg || !tipo) {
      if (detalle) detalle.classList.add('hidden');
      if (notFound) {
        notFound.classList.remove('hidden');
        notFound.classList.add('flex');
      }
      if (detalle) detalle.scrollIntoView();
      return;
    }

    document.title = tipo.nombre + ' | RefriMaster';
    var meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', tipo.tagline);

    var hero = '<section class="relative overflow-hidden bg-surface-container">' +
      '<div class="pointer-events-none absolute inset-0">' +
      '<div class="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-primary-container opacity-80 blur-3xl"></div>' +
      '<div class="absolute right-0 top-1/4 h-80 w-80 rounded-full bg-secondary-container opacity-70 blur-3xl"></div>' +
      '</div>' +
      '<div class="relative z-10 mx-auto w-full max-w-container-max px-lg py-16 md:py-20">' +
      '<a href="' + cfg.volver + '" class="inline-flex items-center gap-1.5 font-label-md font-bold text-primary transition-colors hover:text-primary-hover">' +
      '<span class="material-symbols-outlined text-base">arrow_back</span>' + cfg.volverLabel + '</a>' +
      '<div class="mt-8 flex flex-wrap items-center gap-3">' +
      '<span class="inline-flex w-fit items-center gap-2 rounded-full bg-primary-container px-4 py-1.5 font-label-md font-bold text-on-primary-container ring-1 ring-inset ring-primary/20">' +
      '<span class="material-symbols-outlined text-sm">' + (seccion === 'reparacion' ? 'build' : 'settings') + '</span>' + cfg.chip + '</span>' +
      '<span class="inline-flex w-fit items-center gap-2 rounded-full bg-emerald-50 px-4 py-1.5 font-label-md font-bold text-emerald-700 ring-1 ring-inset ring-emerald-200">' +
      '<span class="material-symbols-outlined text-sm">verified</span>PÚBLICO</span>' +
      '</div>' +
      '<h1 class="mt-6 max-w-3xl font-headline-lg text-4xl font-extrabold leading-tight tracking-tight text-on-surface md:text-5xl">' + tipo.nombre + '</h1>' +
      '<p class="mt-4 max-w-2xl text-lg leading-relaxed text-on-surface-variant">' + tipo.tagline + '</p>' +
      '<div class="mt-8 flex flex-wrap items-center gap-4">' +
      '<button class="solicitar-btn inline-flex items-center gap-2 rounded-xl bg-primary px-xl py-md font-headline-md font-bold text-white transition-all hover:bg-primary-hover active:scale-95" ' +
      'data-servicio="' + cfg.dataServicio + '" data-equipo="' + tipo.equipoSolicitud + '">' +
      '<span class="material-symbols-outlined">request_quote</span>' + cfg.cta + '</button>' +
      '<span class="font-body-md text-on-surface-variant">' + tipo.precioEtiqueta + ' <strong class="font-headline-md text-headline-md text-primary">' + tipo.precio + '</strong></span>' +
      '</div>' +
      '</div></section>';

    var desc = '<section class="bg-white py-16">' +
      '<div class="mx-auto max-w-container-max px-lg">' +
      '<span class="font-label-md font-bold text-primary">EL SERVICIO</span>' +
      '<h2 class="mt-2 font-headline-lg text-headline-lg font-extrabold tracking-tight text-on-surface">Descripción</h2>' +
      '<p class="mt-4 max-w-3xl font-body-md leading-relaxed text-on-surface-variant">' + tipo.descripcion + '</p>' +
      '</div></section>';

    var html = hero + desc;
    if (tipo.incluye) html += seccionIncluye(tipo.incluye);
    if (tipo.problemas) html += seccionProblemas(tipo.problemas);
    if (tipo.beneficios) html += seccionBeneficios(tipo.beneficios);
    if (tipo.equipos) html += seccionEquipos(tipo.equipos, cfg.seccionEquipos);
    if (tipo.diagnostico) html += seccionDiagnostico(tipo.diagnostico);
    if (tipo.precio) html += seccionPrecioAdicional(tipo.precio, tipo.precioEtiqueta || 'Desde', tipo.adicional || []);

    html += '<section class="relative overflow-hidden bg-inverse-surface py-16">' +
      '<div class="relative z-10 mx-auto max-w-3xl px-lg text-center">' +
      '<h2 class="font-headline-lg text-headline-lg font-extrabold tracking-tight text-white">¿Listo para empezar?</h2>' +
      '<p class="mx-auto mt-3 max-w-2xl font-body-md text-slate-300">Solicita este servicio y nuestro equipo técnico certificado se comunicará contigo.</p>' +
      '<button class="solicitar-btn mt-8 inline-flex items-center gap-2 rounded-xl bg-primary px-xl py-md font-headline-md font-bold text-white transition-all hover:bg-primary-hover active:scale-95" ' +
      'data-servicio="' + cfg.dataServicio + '" data-equipo="' + tipo.equipoSolicitud + '">' +
      '<span class="material-symbols-outlined">request_quote</span>' + cfg.cta + '</button>' +
      '</div></section>';

    detalle.innerHTML = html;
    detalle.classList.remove('hidden');
    if (notFound) notFound.classList.add('hidden');

    var nav = document.querySelector('[data-nav="' + seccion + '"]');
    if (nav) {
      nav.classList.remove('text-slate-700', 'hover:text-primary');
      nav.classList.add('border-b-2', 'border-primary', 'py-1', 'font-semibold', 'text-primary');
    }
    window.scrollTo(0, 0);
  }

  var params = new URLSearchParams(window.location.search);
  render(params.get('seccion') || '', params.get('tipo') || '');
})();
