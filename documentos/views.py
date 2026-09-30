import os
import base64
from datetime import date, timedelta
from pathlib import Path
from io import BytesIO

from django.contrib.staticfiles import finders
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from xhtml2pdf import pisa
from pypdf import PdfReader
from django.contrib.auth.models import User
from .models import Documento, ItemActa, Adjunto, NotaRecibida

from .forms import DocumentoForm, ItemActaFormSet, NotaRecibidaForm
from .formato import cuerpo_html
from .utils import generar_numero, generar_numero_recepcion
from .scanner import compilar_imagenes_a_pdf

# ─── Preformatos y Plantillas Oficiales SNAF Informática ─────────────────────
PLANTILLAS_SNAF = {
    'insumos': {
        'tipo': 'NOTA',
        'asunto': 'Solicitud urgente de adquisición de diversos insumos y equipamiento para Informática',
        'destinatario': 'A la Secretaria de Niñez, Adolescencia y Familia\nDra. MARTA IRIARTE\nSu Despacho:',
        'cuerpo': (
            'Me dirijo a usted a fin de reiterar con carácter urgente la solicitud de adquisición '
            'de diversos elementos esenciales para el correcto funcionamiento y mantenimiento del equipamiento '
            'informático en todas las áreas que conforman esta Secretaría.\n\n'
            'Dado que estos recursos son esenciales para asegurar la operatividad, eficiencia y mantenimiento, '
            'se detalla a continuación el listado de materiales requeridos, organizados por categoría para mayor claridad:\n\n'
            '1. Almacenamiento y componentes de hardware\n'
            '• Discos SSD (120 GB / 240 GB / 480 GB SATA) para agilizar tareas administrativas en equipos existentes.\n'
            '• Discos duros para servidor (4 TB / 8 TB SATA 7200 RPM para NAS) necesarios para almacenamiento centralizado y copias de seguridad.\n\n'
            '2. Periféricos\n'
            '• Teclados y mouse ópticos USB para recambio en puestos de trabajo.\n'
            '• Monitores LED de 19" / 22" para reemplazo de unidades fuera de servicio.\n\n'
            '3. Equipamiento de red y energía\n'
            '• Placas de red Wi-Fi (USB o PCI-Express) para dependencias sin cableado estructurado.\n'
            '• Estabilizadores de tensión para protección eléctrica de puestos informáticos.\n'
            '• Bobina de cable de red UTP Cat 6 y conectores RJ45.\n\n'
            'Todos estos insumos y componentes tienen como objetivo mejorar el rendimiento, la estabilidad y la capacidad '
            'de respuesta del Departamento de Informática, impactando de manera directa en el soporte y funcionamiento '
            'tecnológico de todas las áreas de la Secretaría de Niñez, Adolescencia y Familia.\n\n'
            'Sin otro particular y en espera de una respuesta favorable me despido de Ud. con atenta consideración y respeto.-'
        ),
    },
    'herramientas': {
        'tipo': 'NOTA',
        'asunto': 'Solicitud de adquisición de herramientas de mantenimiento técnico para Informática',
        'destinatario': 'A la Secretaria de Niñez, Adolescencia y Familia\nDra. MARTA IRIARTE\nSu Despacho:',
        'cuerpo': (
            'Me dirijo a usted a fin de solicitar la adquisición de herramientas de mantenimiento técnico esenciales '
            'para el correcto funcionamiento del equipamiento informático en todas las áreas que conforman esta Secretaría.\n\n'
            'Dado que estos recursos son esenciales para asegurar la operatividad, eficiencia y tareas de mantenimiento '
            'preventivo y correctivo, se detalla a continuación el listado de herramientas requeridas:\n\n'
            '• Tester probador de cable de red RJ45 / RJ11\n'
            '• Pinza crimpeadora profesional para fichas RJ45\n'
            '• Juego de destornilladores de precisión para equipos informáticos y notebooks\n'
            '• Soplador térmico / aspirador antiestático para limpieza de servidores y switches\n'
            '• Pulseras y alfombrillas antiestáticas ESD para banco de trabajo\n'
            '• Multímetro digital para diagnóstico de fuentes de alimentación\n\n'
            'Todas estas herramientas tienen como objetivo mejorar el rendimiento, la estabilidad y la capacidad de respuesta '
            'del Departamento de Informática, impactando de manera directa en el soporte y funcionamiento tecnológico de todas las áreas.\n\n'
            'Sin otro particular y en espera de una respuesta favorable me despido de Ud. con atenta consideración y respeto.-'
        ),
    },
    'opd': {
        'tipo': 'NOTA',
        'asunto': 'Solicitud de adquisición de discos SSD, placas Wi-Fi y puntos de acceso para Oficinas de Protección de Derechos (OPD)',
        'destinatario': 'A la Coordinadora de OPD de la\nSecretaría de Niñez, Adolescencia y Familia\nDra. DELIA ALANCAY\nSu Despacho:',
        'cuerpo': (
            'Me dirijo a usted con el fin de informar la situación actual de distintos equipos informáticos y de la infraestructura '
            'de conectividad perteneciente a las Oficinas de Protección de Derechos (OPD), y solicitar la adquisición de componentes '
            'necesarios para su reparación, puesta en funcionamiento y mejora de la conectividad.\n\n'
            'Durante las tareas de revisión y mantenimiento realizadas sobre los equipos informáticos de las distintas dependencias, '
            'se detectaron fallas y deterioro en unidades de almacenamiento, encontrándose algunos discos en condición de inoperatividad '
            'debido a daños en sus componentes, mientras que otros presentan signos de degradación y disminución de su vida útil. '
            'Esta situación puede provocar errores de funcionamiento, pérdida de información y eventuales fallas definitivas de los equipos.\n\n'
            'Asimismo, se verificó que determinados equipos no cuentan con adaptadores de red inalámbrica (Wi-Fi) o presentan inconvenientes '
            'con los dispositivos actualmente instalados, dificultando su conexión a las redes disponibles en las dependencias.\n\n'
            'Por otra parte, se identificó la necesidad de ampliar y mejorar la cobertura de las redes inalámbricas en distintas OPD, '
            'especialmente en sectores donde la distribución física de las instalaciones, la distancia respecto de los equipos de red o '
            'las características edilicias generan una señal Wi-Fi insuficiente o inestable.\n\n'
            'Sin otro particular y a la espera de una resolución favorable, saludo a usted atentamente.-'
        ),
    },
    'servidor': {
        'tipo': 'NOTA',
        'asunto': 'Solicitud de provisión de servidor virtualizado para Datacenter SNAF',
        'destinatario': 'C.P. Santiago Besin\nSecretaría Informática de la Provincia de Jujuy\nSan Salvador de Jujuy',
        'cuerpo': (
            'Me dirijo a usted en mi calidad de responsable de Informática de la Secretaría de Niñez, Adolescencia y Familia, '
            'con el fin de solicitar la provisión de un servidor virtualizado para nuestra institución en el Datacenter Provincial.\n\n'
            'Esta solicitud responde a la necesidad de mejorar la eficiencia y la seguridad de nuestros sistemas informáticos y bases '
            'de datos documentales, lo que es crucial para el correcto funcionamiento de nuestra labor institucional.\n\n'
            'Requerimientos técnicos especificados:\n'
            '• Entorno: Servidor virtualizado KVM / VMware\n'
            '• Procesamiento: 4 vCPU o superior\n'
            '• Memoria RAM: 16 GB DDR4\n'
            '• Almacenamiento: 500 GB en arreglo redundante SSD de alto rendimiento\n'
            '• Sistema Operativo: Ubuntu Server 24.04 LTS / Debian 12\n'
            '• Conectividad: IP fija en la red provincial con acceso seguro VPN/SSH\n\n'
            'Agradeciendo de antemano su atención y colaboración, quedo a su disposición para coordinar los detalles técnicos necesarios.\n\n'
            'Sin otro particular, saludo a usted muy atentamente.-'
        ),
    },
    'diagnostico_pc': {
        'tipo': 'INFORME',
        'asunto': 'Informe de diagnóstico técnico y solicitud de repuesto - Puesto de trabajo',
        'destinatario': 'Coordinación de OPD / Dirección de Despacho\nSecretaría de Niñez, Adolescencia y Familia',
        'cuerpo': (
            '1. OBJETO\n'
            'El presente informe tiene como finalidad documentar el estado técnico de una unidad central de proceso (PC) '
            'perteneciente a la dependencia solicitante y detallar los componentes necesarios para su inmediata puesta en funcionamiento.\n\n'
            '2. REVISIÓN Y DIAGNÓSTICO\n'
            'Se recibió en este departamento técnico el equipo informático, el cual no presentaba señal de encendido ni respuesta operativa. '
            'Tras la inspección técnica especializada en banco de prueba, se determinó lo siguiente:\n\n'
            '• Falla Identificada: Fallo total en la fuente de alimentación original debido a sobretensión y degradación en capacitores.\n'
            '• Prueba de Validación: Para confirmar el diagnóstico, se procedió a realizar pruebas de encendido y carga utilizando una fuente '
            'de alimentación de testeo y disco de prueba.\n'
            '• Resultado de la Prueba: Con la fuente de prueba, el equipo funcionó correctamente, logrando un inicio exitoso del sistema '
            'operativo y validando la integridad del resto de los componentes (Placa madre, Microprocesador, Memoria RAM).\n\n'
            '3. CONCLUSIONES Y RECOMENDACIONES\n'
            'Se requiere la provisión de una fuente de alimentación ATX de 500W para proceder al reemplazo definitivo y restituir la operatividad '
            'del equipo en su sector.\n\n'
            'Sin otro particular, se eleva el presente informe para su conocimiento y los fines que correspondan.'
        ),
    },
    'switch_red': {
        'tipo': 'INFORME',
        'asunto': 'Informe técnico sobre estado de switch de red y solicitud de reemplazo',
        'destinatario': 'Dirección de Adultos Mayores / Despacho\nSecretaría de Niñez, Adolescencia y Familia',
        'cuerpo': (
            '1. OBJETO\n'
            'Informar el estado operativo del switch de red que interconecta los puestos de trabajo del sector, y solicitar su reemplazo '
            'debido a una falla técnica irreversible que impide su correcto funcionamiento.\n\n'
            '2. DIAGNÓSTICO TÉCNICO\n'
            'El switch de red principal del sector se encuentra inoperativo y fuera de servicio como consecuencia de descargas eléctricas, '
            'ocasionando la interrupción de la conectividad de los equipos informáticos que dependen de dicho dispositivo para acceder a la red institucional e Internet.\n\n'
            '3. REQUERIMIENTO Y PROCEDIMIENTO\n'
            'Por tal motivo, se solicita la provisión de un switch de red de 16/24 puertos Gigabit 10/100/1000 Mbps. Una vez provisto el nuevo '
            'dispositivo, este Departamento de Informática procederá con su montaje en rack, conectorización, configuración de VLANs y verificación '
            'del normal acceso a los sistemas.\n\n'
            'Sin otro particular, se eleva el presente informe para su conocimiento y los fines que correspondan.'
        ),
    },
    'mantenimiento': {
        'tipo': 'INFORME',
        'asunto': 'Informe periódico de mantenimiento preventivo y verificación de infraestructura de servidores',
        'destinatario': 'Gerencia de TI / Dirección General\nSecretaría de Niñez, Adolescencia y Familia',
        'cuerpo': (
            '1. INTRODUCCIÓN\n'
            'Se presenta el informe de mantenimiento preventivo programado y control de operatividad ejecutado sobre la infraestructura de servidores, '
            'enlaces de fibra óptica y sistemas de almacenamiento centralizado (NAS) del Departamento de Informática.\n\n'
            '2. DIAGNÓSTICO Y TAREAS REALIZADAS\n'
            '• Verificación de logs del sistema operativo y estado de salud de arreglos RAID.\n'
            '• Limpieza física de gabinetes de servidores, ventiladores y filtros de aire.\n'
            '• Aplicación de parches críticos de seguridad y actualización del motor de base de datos.\n'
            '• Comprobación y prueba de restauración de copias de seguridad (backups) automáticas.\n'
            '• Verificación de tensión y autonomía de los sistemas de alimentación ininterrumpida (UPS).\n\n'
            '3. CONCLUSIONES\n'
            'Todos los servicios se encuentran operando dentro de los parámetros de disponibilidad esperados, con óptimo rendimiento en la red interna de la Secretaría.\n\n'
            'Sin otro particular, se eleva el presente informe para su conocimiento y los fines que correspondan.'
        ),
    },
    'impresoras': {
        'tipo': 'INFORME',
        'asunto': 'Estado de impresoras HP LaserJet P1005',
        'destinatario': 'Dirección General de Despacho\nSecretaría de Niñez, Adolescencia y Familia',
        'cuerpo': (
            '1. OBJETO\n'
            'El presente informe tiene por objeto detallar el estado técnico y operativo de las impresoras '
            'marca HP modelo LaserJet P1005 asignadas a las distintas dependencias de esta Secretaría.\n\n'
            '2. REVISIÓN Y DIAGNÓSTICO\n'
            'Se procedió a la revisión técnica integral en el banco de pruebas del Departamento de Informática, '
            'constatando el estado de los componentes mecánicos, rodillos de tracción (pick-up rollers) y consumibles de tóner.\n\n'
            '3. CONCLUSIONES Y RECOMENDACIONES\n'
            'Se recomienda el mantenimiento preventivo y reemplazo de kits de mantenimiento en las unidades con desgaste '
            'para asegurar su continuidad operativa en los sectores administrativos.\n\n'
            'Sin otro particular, se eleva el presente informe para su conocimiento y los fines que correspondan.'
        ),
    },
    'laptop': {
        'tipo': 'ACTA',
        'asunto': 'Acta de entrega y asignación de equipamiento portátil (Notebook)',
        'destinatario': 'Dirección de Recursos Humanos / Despacho de Niñez',
        'cuerpo': 'Recibí del Área de Informática los bienes que se detallan a continuación.-',
    },
    'estabilizador': {
        'tipo': 'ACTA',
        'asunto': 'Acta de entrega de estabilizadores de tensión para protección de equipos',
        'destinatario': 'Oficinas de Protección de Derechos (OPD) / CDI',
        'cuerpo': 'Recibí del Área de Informática los bienes que se detallan a continuación.-',
    },
    'prestamo_cpu': {
        'tipo': 'ACTA',
        'asunto': 'Acta de entrega por préstamo de CPU en reparación',
        'destinatario': 'Dirección de Administración / Secretaría de Niñez, Adolescencia y Familia',
        'cuerpo': 'Recibí del Área de Informática los bienes que se detallan a continuación.-',
    },
    'incidente': {
        'tipo': 'NOTA',
        'asunto': 'Reporte de Incidente Crítico y Plan de Contingencia',
        'destinatario': 'Equipo de Infraestructura & DevOps',
        'cuerpo': '1. ANTECEDENTES Y PROPÓSITO\nSe notifica la contingencia técnica registrada en la infraestructura de red y servicios de datos.\n\n2. VENTANA DE TIEMPO Y RESOLUCIÓN\nSe ejecutaron los procedimientos de contingencia y aislamiento de fallas restableciendo la totalidad de los servicios.',
    },
}


# ─── Dashboard ───────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    total = Documento.objects.count()
    por_tipo = {
        'NOTA': Documento.objects.filter(tipo='NOTA').count(),
        'INFORME': Documento.objects.filter(tipo='INFORME').count(),
        'ACTA': Documento.objects.filter(tipo='ACTA').count(),
    }
    emitidos = Documento.objects.filter(estado='EMITIDO').count()
    entregados = Documento.objects.filter(estado='ENTREGADO').count()
    recientes = Documento.objects.select_related('creado_por').order_by('-creado_en')[:6]

    # Mesa de Entrada / Notas Recibidas
    total_recibidas = NotaRecibida.objects.count()
    recibidas_pendientes = NotaRecibida.objects.filter(estado='PENDIENTE').count()
    recibidas_recientes = NotaRecibida.objects.select_related('recibido_por', 'documento_respuesta').order_by('-creado_en')[:6]

    return render(request, 'documentos/dashboard.html', {
        'total': total,
        'por_tipo': por_tipo,
        'emitidos': emitidos,
        'entregados': entregados,
        'recientes': recientes,
        'total_recibidas': total_recibidas,
        'recibidas_pendientes': recibidas_pendientes,
        'recibidas_recientes': recibidas_recientes,
    })


# ─── Lista de documentos ─────────────────────────────────────────────────────

@login_required
def lista_documentos(request):
    qs = Documento.objects.select_related('creado_por').all()

    tipo = request.GET.get('tipo', '')
    estado = request.GET.get('estado', '')
    anio = request.GET.get('anio', '')
    periodo = request.GET.get('periodo', '')
    busqueda = request.GET.get('q', '').strip()

    notas_recibidas_coincidentes = []
    total_recibidas_encontradas = 0

    if tipo:
        qs = qs.filter(tipo=tipo)
    if estado:
        qs = qs.filter(estado=estado)
    if anio:
        qs = qs.filter(fecha__year=anio)

    hoy = date.today()
    if periodo == 'hoy':
        qs = qs.filter(fecha=hoy)
    elif periodo == 'semana':
        qs = qs.filter(fecha__gte=hoy - timedelta(days=7))
    elif periodo == 'mes':
        qs = qs.filter(fecha__year=hoy.year, fecha__month=hoy.month)
    elif periodo == 'anio':
        qs = qs.filter(fecha__year=hoy.year)

    if busqueda:
        qs = qs.filter(
            Q(numero__icontains=busqueda) |
            Q(asunto__icontains=busqueda) |
            Q(remitente__icontains=busqueda) |
            Q(destinatario__icontains=busqueda)
        )
        # Búsqueda integrada también en Mesa de Entrada (Notas Recibidas)
        recibidas_qs = NotaRecibida.objects.select_related('recibido_por', 'documento_respuesta').filter(
            Q(numero_registro__icontains=busqueda) |
            Q(numero_origen__icontains=busqueda) |
            Q(remitente_origen__icontains=busqueda) |
            Q(asunto__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
        total_recibidas_encontradas = recibidas_qs.count()
        notas_recibidas_coincidentes = list(recibidas_qs[:10])

    # Ordenamiento
    orden = request.GET.get('orden', 'fecha')
    direccion = request.GET.get('dir', 'desc')

    if orden.startswith('-'):
        direccion = 'desc'
        orden = orden[1:]
    elif orden.startswith('+'):
        direccion = 'asc'
        orden = orden[1:]

    if orden == 'numero':
        if direccion == 'asc':
            qs = qs.order_by('fecha__year', 'numero', 'id')
        else:
            qs = qs.order_by('-fecha__year', '-numero', '-id')
    elif orden == 'fecha':
        if direccion == 'asc':
            qs = qs.order_by('fecha', 'id')
        else:
            qs = qs.order_by('-fecha', '-id')
    elif orden in ['tipo', 'destinatario', 'asunto', 'estado']:
        if direccion == 'asc':
            qs = qs.order_by(orden, '-fecha', '-id')
        else:
            qs = qs.order_by(f'-{orden}', '-fecha', '-id')
    else:
        orden = 'fecha'
        direccion = 'desc'
        qs = qs.order_by('-fecha', '-id')

    # Años disponibles para el filtro
    anios = Documento.objects.dates('fecha', 'year', order='DESC')
    total_filtrados = qs.count()

    # Paginación (10 documentos por página como en Figma)
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    filtros_activos_count = sum([
        bool(tipo),
        bool(estado),
        bool(periodo),
        bool(anio),
        bool(busqueda),
        bool(orden != 'fecha' or direccion != 'desc'),
    ])

    return render(request, 'documentos/lista.html', {
        'documentos': page_obj,
        'page_obj': page_obj,
        'paginator': paginator,
        'total_filtrados': total_filtrados,
        'filtros_activos_count': filtros_activos_count,
        'tipo_filtro': tipo,
        'estado_filtro': estado,
        'anio_filtro': anio,
        'periodo_filtro': periodo,
        'orden': orden,
        'dir': direccion,
        'busqueda': busqueda,
        'anios': [d.year for d in anios],
        'notas_recibidas_coincidentes': notas_recibidas_coincidentes,
        'total_recibidas_encontradas': total_recibidas_encontradas,
    })


# ─── Detalle ─────────────────────────────────────────────────────────────────

def guardar_adjuntos(request, doc):
    """Guarda los archivos adjuntos subidos en el formulario y vincula imágenes subidas por AJAX."""
    for f in request.FILES.getlist('archivos'):
        Adjunto.objects.create(
            documento=doc,
            archivo=f,
            nombre_original=f.name,
            tamano=f.size,
            subido_por=request.user,
        )
    adjuntos_ids_raw = request.POST.get('adjuntos_ids', '')
    if adjuntos_ids_raw:
        ids = [int(i.strip()) for i in adjuntos_ids_raw.split(',') if i.strip().isdigit()]
        if ids:
            Adjunto.objects.filter(id__in=ids, documento__isnull=True).update(documento=doc)


@login_required
def detalle_documento(request, pk):
    doc = get_object_or_404(Documento, pk=pk)

    # Acción para marcar como entregado / firmado con adjunto opcional escaneado o subido
    if request.method == 'POST' and 'accion_entregar' in request.POST:
        if doc.estado == 'EMITIDO':
            adjunto_creado = False

            # 1. Procesar fotos tomadas con celular / escaneadas
            imagenes = request.FILES.getlist('imagenes_escaneo')
            if imagenes:
                filtro = request.POST.get('filtro_escaneo', 'magic_color')
                autocrop = request.POST.get('autocrop', '1') == '1'
                nombre_pdf = f"FIRMADO_{doc.numero.replace('/', '-')}.pdf"
                pdf_content = compilar_imagenes_a_pdf(
                    imagenes,
                    nombre_archivo=nombre_pdf,
                    filtro=filtro,
                    autocrop=autocrop
                )
                if pdf_content:
                    adj = Adjunto(
                        documento=doc,
                        nombre_original=nombre_pdf,
                        subido_por=request.user,
                    )
                    adj.archivo.save(nombre_pdf, pdf_content, save=True)
                    adjunto_creado = True

            # 2. Procesar subida directa de PDF escaneado
            if 'archivo_pdf' in request.FILES and request.FILES['archivo_pdf']:
                f_pdf = request.FILES['archivo_pdf']
                Adjunto.objects.create(
                    documento=doc,
                    archivo=f_pdf,
                    nombre_original=f_pdf.name,
                    tamano=f_pdf.size,
                    subido_por=request.user,
                )
                adjunto_creado = True

            # 3. Guardar cualquier otro archivo adjunto enviado
            guardar_adjuntos(request, doc)

            # 4. Guardar detalle / constancia de entrega si se proporcionó
            detalle_entrega = request.POST.get('detalle_entrega', '').strip()
            if detalle_entrega:
                doc.detalle_entrega = detalle_entrega

            # 5. Cambiar estado a ENTREGADO
            doc.estado = 'ENTREGADO'
            doc.save()

            if adjunto_creado:
                messages.success(request, f'Documento {doc.numero} marcado como ENTREGADO y firmado con el adjunto digitalizado. Ha quedado protegido contra modificaciones.')
            else:
                messages.success(request, f'Documento {doc.numero} marcado como ENTREGADO y firmado. Ha quedado protegido contra modificaciones.')
            return redirect('detalle_documento', pk=doc.pk)

    items = doc.items.all() if doc.tipo == 'ACTA' else []
    adjuntos = doc.adjuntos.all()
    return render(request, 'documentos/detalle.html', {
        'doc': doc,
        'items': items,
        'adjuntos': adjuntos,
        'cuerpo_formateado': cuerpo_html(doc.cuerpo),
    })


def obtener_sugerencias_destinatarios():
    """
    Retorna listas únicas y ordenadas de cargos, nombres y sectores utilizados
    en documentos anteriores para poblar datalists de autocompletado y desplegables.
    """
    cargos = set()
    nombres = set()
    sectores = set()

    for doc in Documento.objects.only('destinatario_cargo', 'destinatario_nombre', 'destinatario').iterator():
        c = doc.cargo_display
        if c:
            cargos.add(c)
        n = doc.nombre_display
        if n:
            nombres.add(n)
        if doc.destinatario:
            sec = doc.destinatario.strip()
            if sec and '\n' not in sec:
                sectores.add(sec)

    return {
        'cargos_frecuentes': sorted(cargos),
        'nombres_frecuentes': sorted(nombres),
        'sectores_frecuentes': sorted(sectores),
    }


# ─── Crear documento ─────────────────────────────────────────────────────────

@login_required
def crear_documento(request):
    plantilla = request.GET.get('plantilla', '')
    plantilla_doc_id = request.GET.get('plantilla_doc') or request.GET.get('clonar')
    nota_recibida_id = request.GET.get('nota_recibida_id') or request.POST.get('nota_recibida_id')
    nota_recibida = None
    if nota_recibida_id:
        nota_recibida = NotaRecibida.objects.filter(pk=nota_recibida_id).first()

    tipo_param = request.POST.get('tipo', request.GET.get('tipo', 'NOTA')) if request.method == 'POST' else request.GET.get('tipo', 'NOTA')
    if tipo_param not in ['NOTA', 'INFORME', 'ACTA']:
        tipo_param = 'NOTA'

    nombre_completo = request.user.get_full_name().strip()
    nombre_emisor = nombre_completo if nombre_completo else request.user.username

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)
        tipo = tipo_param
        formset = ItemActaFormSet(request.POST, prefix='items') if tipo == 'ACTA' else None

        if form.is_valid():
            doc = form.save(commit=False)
            doc.creado_por = request.user
            doc.estado = 'EMITIDO'

            # Validar formset solo para ACTA
            if tipo == 'ACTA' and formset is not None:
                if formset.is_valid():
                    doc.save()
                    formset.instance = doc
                    formset.save()
                    guardar_adjuntos(request, doc)
                    if nota_recibida:
                        nota_recibida.documento_respuesta = doc
                        if nota_recibida.estado in ['PENDIENTE', 'EN_TRAMITE']:
                            nota_recibida.estado = 'RESPONDIDO'
                        nota_recibida.save(update_fields=['documento_respuesta', 'estado'])
                    messages.success(request, f'Acta {doc.numero} creada exitosamente.')
                    return redirect('detalle_documento', pk=doc.pk)
            else:
                doc.save()
                guardar_adjuntos(request, doc)
                if nota_recibida:
                    nota_recibida.documento_respuesta = doc
                    if nota_recibida.estado in ['PENDIENTE', 'EN_TRAMITE']:
                        nota_recibida.estado = 'RESPONDIDO'
                    nota_recibida.save(update_fields=['documento_respuesta', 'estado'])
                messages.success(request, f'Documento {doc.numero} creado exitosamente.')
                return redirect('detalle_documento', pk=doc.pk)
    else:
        # Para informes y notas, el remitente por defecto es 'Área de Informática'
        # Para actas de entrega, es el usuario que autoriza entrega
        if tipo_param in ['NOTA', 'INFORME']:
            remitente_default = 'Área de Informática'
        else:
            remitente_default = nombre_emisor

        initial_data = {
            'tipo': tipo_param,
            'fecha': date.today(),
            'remitente': remitente_default,
            'estado': 'EMITIDO',
        }

        formset = ItemActaFormSet(prefix='items')

        if nota_recibida:
            initial_data['asunto'] = f"Respuesta a Nota {nota_recibida.numero_registro}: {nota_recibida.asunto}"
            initial_data['destinatario'] = nota_recibida.remitente_origen
            initial_data['destinatario_cargo'] = nota_recibida.remitente_origen

        if tipo_param == 'ACTA':
            initial_data['cuerpo'] = 'Recibí del Área de Informática los bienes que se detallan a continuación.-'

        # Cargar datos desde documento base como plantilla si se solicitó
        if plantilla_doc_id and str(plantilla_doc_id).isdigit():
            doc_base = Documento.objects.filter(pk=plantilla_doc_id).first()
            if doc_base:
                tipo_param = doc_base.tipo
                initial_data.update({
                    'tipo': doc_base.tipo,
                    'asunto': doc_base.asunto,
                    'remitente': doc_base.remitente or remitente_default,
                    'destinatario': doc_base.destinatario,
                    'destinatario_cargo': doc_base.destinatario_cargo or doc_base.cargo_display,
                    'destinatario_nombre': doc_base.destinatario_nombre or doc_base.nombre_display,
                    'receptor_nombre': doc_base.receptor_nombre,
                    'receptor_dni': doc_base.receptor_dni,
                    'cuerpo': doc_base.cuerpo,
                })
                if doc_base.tipo == 'ACTA':
                    items_base = list(doc_base.items.values('cantidad', 'descripcion', 'numero_serie', 'codigo_inventario', 'condicion', 'observaciones'))
                    if items_base:
                        formset = ItemActaFormSet(prefix='items', initial=items_base)
                        formset.extra = max(1, len(items_base))
                messages.info(request, f'Se cargó el contenido del documento {doc_base.numero} como plantilla. Al guardar se registrará con un nuevo número correlativo.')

        # Diccionario de preformatos basados en los documentos reales de \\snfserver2\Informatica\notas de pedido
        elif plantilla in PLANTILLAS_SNAF:
            p_data = PLANTILLAS_SNAF[plantilla]
            initial_data.update({
                'tipo': p_data['tipo'],
                'asunto': p_data['asunto'],
                'destinatario': p_data['destinatario'],
                'cuerpo': p_data['cuerpo'],
            })
            tipo_param = p_data['tipo']
            if tipo_param in ['NOTA', 'INFORME']:
                initial_data['remitente'] = 'Área de Informática'
            else:
                initial_data['remitente'] = nombre_emisor

        form = DocumentoForm(initial=initial_data)

    # Estimación de próximo número para la vista previa
    try:
        proximo_numero = generar_numero(tipo_param, date.today().year)
    except Exception:
        proximo_numero = 'NOTE-2026-001'

    sugerencias = obtener_sugerencias_destinatarios()

    return render(request, 'documentos/formulario.html', {
        'form': form,
        'formset': formset,
        'accion': 'Redactar Nuevo Documento',
        'modo': 'crear',
        'proximo_numero': proximo_numero,
        'plantilla_seleccionada': plantilla,
        'nombre_emisor': nombre_emisor,
        'nota_recibida': nota_recibida,
        **sugerencias,
    })


# ─── Editar documento ─────────────────────────────────────────────────────────

@login_required
def editar_documento(request, pk):
    doc = get_object_or_404(Documento, pk=pk)

    if doc.estado == 'ENTREGADO':
        messages.error(request, f'El documento {doc.numero} se encuentra en estado ENTREGADO (firmado) y no puede ser modificado.')
        return redirect('detalle_documento', pk=doc.pk)

    nombre_completo = request.user.get_full_name().strip()
    nombre_emisor = nombre_completo if nombre_completo else request.user.username

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, instance=doc)
        formset = ItemActaFormSet(request.POST, instance=doc, prefix='items') if doc.tipo == 'ACTA' else None

        if form.is_valid():
            doc_obj = form.save(commit=False)
            doc_obj.estado = 'EMITIDO'

            # Procesar adjuntos marcados para eliminar
            eliminar_ids = request.POST.getlist('eliminar_adjunto')
            if eliminar_ids:
                Adjunto.objects.filter(id__in=eliminar_ids, documento=doc).delete()

            if doc.tipo == 'ACTA' and formset is not None:
                if formset.is_valid():
                    doc_obj.save()
                    formset.save()
                    guardar_adjuntos(request, doc_obj)
                    messages.success(request, f'Documento {doc.numero} actualizado.')
                    return redirect('detalle_documento', pk=doc.pk)
            else:
                doc_obj.save()
                guardar_adjuntos(request, doc_obj)
                messages.success(request, f'Documento {doc.numero} actualizado.')
                return redirect('detalle_documento', pk=doc.pk)
    else:
        form = DocumentoForm(instance=doc)
        formset = ItemActaFormSet(instance=doc, prefix='items') if doc.tipo == 'ACTA' else None

    sugerencias = obtener_sugerencias_destinatarios()

    return render(request, 'documentos/formulario.html', {
        'form': form,
        'formset': formset,
        'doc': doc,
        'adjuntos': doc.adjuntos.all(),
        'accion': f'Editar {doc.numero}',
        'modo': 'editar',
        'proximo_numero': doc.numero,
        'nombre_emisor': nombre_emisor,
        **sugerencias,
    })


@login_required
@require_POST
def subir_imagen_editor(request):
    """
    Endpoint AJAX para subir una imagen desde el botón del editor e incrustarla
    en el cuerpo del documento.
    """
    if 'imagen' not in request.FILES:
        return JsonResponse({'success': False, 'error': 'No se recibió ningún archivo de imagen.'}, status=400)

    f = request.FILES['imagen']
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        return JsonResponse({'success': False, 'error': 'Formato no compatible. Suba imágenes JPG, PNG, GIF o WEBP.'}, status=400)

    if f.size > 10 * 1024 * 1024:
        return JsonResponse({'success': False, 'error': 'La imagen no debe superar los 10 MB.'}, status=400)

    doc_id = request.POST.get('doc_id')
    doc = Documento.objects.filter(pk=doc_id).first() if doc_id and doc_id.isdigit() else None

    adjunto = Adjunto.objects.create(
        documento=doc,
        archivo=f,
        nombre_original=f.name,
        tamano=f.size,
        subido_por=request.user,
    )

    tag = f'[IMAGEN: {adjunto.archivo.url} | {adjunto.nombre_original}]'
    return JsonResponse({
        'success': True,
        'id': adjunto.id,
        'url': adjunto.archivo.url,
        'nombre': adjunto.nombre_original,
        'tag': tag,
    })


@login_required
@require_POST
def eliminar_adjunto(request, pk):
    """Elimina un adjunto individual."""
    adjunto = get_object_or_404(Adjunto, pk=pk)
    doc_pk = adjunto.documento.pk if adjunto.documento else None
    adjunto.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == '1':
        return JsonResponse({'success': True})
    messages.success(request, 'Archivo adjunto eliminado.')
    if doc_pk:
        return redirect('editar_documento', pk=doc_pk)
    return redirect('dashboard')


# ─── Eliminar documento ───────────────────────────────────────────────────────

@login_required
def eliminar_documento(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    if doc.estado in ['EMITIDO', 'ENTREGADO']:
        messages.error(request, f'No se puede eliminar un documento {doc.get_estado_display().lower()}.')
        return redirect('detalle_documento', pk=doc.pk)

    if request.method == 'POST':
        numero = doc.numero
        doc.delete()
        messages.success(request, f'Documento {numero} eliminado.')
        return redirect('lista_documentos')

    return render(request, 'documentos/confirmar_eliminar.html', {'doc': doc})


# ─── Generar PDF ─────────────────────────────────────────────────────────────

@login_required
def generar_pdf(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    items = doc.items.all() if doc.tipo == 'ACTA' else []

    template_map = {
        'NOTA': 'documentos/pdf/nota.html',
        'INFORME': 'documentos/pdf/informe.html',
        'ACTA': 'documentos/pdf/acta.html',
    }
    template_name = template_map.get(doc.tipo, 'documentos/pdf/nota.html')

    encabezado_path = finders.find('img/encabezado_institucional.png') or finders.find('img/membrete.png')
    encabezado_uri = ''
    if encabezado_path and Path(encabezado_path).exists():
        encabezado_uri = 'data:image/png;base64,' + base64.b64encode(Path(encabezado_path).read_bytes()).decode('ascii')

    def render_html(m_top=35):
        return render_to_string(template_name, {
            'doc': doc,
            'items': items,
            'cuerpo_html': cuerpo_html(doc.cuerpo, para_pdf=True),
            'encabezado_uri': encabezado_uri,
            'membrete_uri': encabezado_uri,
            'firma_margin_top': m_top,
        })

    buffer = BytesIO()
    if doc.tipo in ['NOTA', 'INFORME']:
        base_margin = 25
        html_pass1 = render_html(base_margin)
        pisa_status = pisa.CreatePDF(html_pass1, dest=buffer, encoding='utf-8')
        if not pisa_status.err:
            try:
                reader = PdfReader(buffer)
                orig_pages = len(reader.pages)
                y_coords = []
                def visitor(text, cm, tm, font_dict, font_size):
                    if text.strip() and 'Página' not in text and 'Secretaría de Niñez' not in text and 'Área de Informática' not in text:
                        if cm[5] > 70:
                            y_coords.append(cm[5])
                reader.pages[-1].extract_text(visitor_text=visitor)
                min_y = min(y_coords) if y_coords else 150
                target_bottom = 100
                extra_space = int(min_y - target_bottom)
                if extra_space > 15:
                    cand_margin = base_margin + extra_space - 10
                    cand_html = render_html(cand_margin)
                    buf_cand = BytesIO()
                    st_cand = pisa.CreatePDF(cand_html, dest=buf_cand, encoding='utf-8')
                    if not st_cand.err:
                        reader_cand = PdfReader(buf_cand)
                        if len(reader_cand.pages) == orig_pages:
                            buffer = buf_cand
                        else:
                            cand_margin = max(base_margin, cand_margin - 30)
                            buf_safe = BytesIO()
                            st_safe = pisa.CreatePDF(render_html(cand_margin), dest=buf_safe, encoding='utf-8')
                            if not st_safe.err:
                                buffer = buf_safe
            except Exception:
                pass
    else:
        html_string = render_html()
        pisa_status = pisa.CreatePDF(html_string, dest=buffer, encoding='utf-8')
        if pisa_status.err:
            return HttpResponse('Error al generar el PDF', status=500)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f'{doc.numero.replace("/", "-")}.pdf'
    disposition = 'attachment' if request.GET.get('descargar') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


# ─── Mesa de Entrada / Notas Recibidas ──────────────────────────────────────

@login_required
def lista_notas_recibidas(request):
    """
    Lista de notas y correspondencia recibidas en el Área de Informática.
    Permite filtrar por búsqueda general, estado, usuario receptor y rango de fechas.
    """
    queryset = NotaRecibida.objects.select_related('recibido_por', 'documento_respuesta').all()

    q = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '').strip()
    recibido_por = request.GET.get('recibido_por', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()

    if q:
        queryset = queryset.filter(
            Q(numero_registro__icontains=q) |
            Q(numero_origen__icontains=q) |
            Q(remitente_origen__icontains=q) |
            Q(asunto__icontains=q) |
            Q(descripcion__icontains=q)
        )

    if estado:
        queryset = queryset.filter(estado=estado)

    if recibido_por:
        queryset = queryset.filter(recibido_por_id=recibido_por)

    if fecha_desde:
        queryset = queryset.filter(fecha_recepcion__gte=fecha_desde)

    if fecha_hasta:
        queryset = queryset.filter(fecha_recepcion__lte=fecha_hasta)

    # Conteo por estados para estadísticas rápidas
    total_recibidas = NotaRecibida.objects.count()
    pendientes_count = NotaRecibida.objects.filter(estado='PENDIENTE').count()
    tramite_count = NotaRecibida.objects.filter(estado='EN_TRAMITE').count()
    respondidas_count = NotaRecibida.objects.filter(estado='RESPONDIDO').count()
    archivadas_count = NotaRecibida.objects.filter(estado='ARCHIVADO').count()

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    usuarios = User.objects.filter(notas_recibidas__isnull=False).distinct()
    if not usuarios.exists():
        usuarios = User.objects.filter(is_active=True).order_by('first_name', 'username')

    filtros_activos = [f for f in [q, estado, recibido_por, fecha_desde, fecha_hasta] if f]
    filtros_activos_count = len(filtros_activos)

    context = {
        'page_obj': page_obj,
        'q': q,
        'estado_sel': estado,
        'recibido_por_sel': recibido_por,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'usuarios': usuarios,
        'filtros_activos_count': filtros_activos_count,
        'total_recibidas': total_recibidas,
        'pendientes_count': pendientes_count,
        'tramite_count': tramite_count,
        'respondidas_count': respondidas_count,
        'archivadas_count': archivadas_count,
    }
    return render(request, 'documentos/recibidos/lista.html', context)


@login_required
def crear_nota_recibida(request):
    """
    Registra una nueva nota recibida. Soporta captura de fotos con cámara de celular,
    subida de imágenes escaneadas y subida directa de archivo PDF.
    """
    proximo_numero = generar_numero_recepcion(date.today().year)

    if request.method == 'POST':
        form = NotaRecibidaForm(request.POST, request.FILES)
        if form.is_valid():
            nota = form.save(commit=False)
            if not nota.recibido_por_id:
                nota.recibido_por = request.user
            nota.save()

            # Procesar fotos/escaneos desde el móvil o subidas directamente al PDF
            imagenes = request.FILES.getlist('imagenes_escaneo')
            if imagenes and not nota.archivo_pdf:
                filtro = request.POST.get('filtro_escaneo', 'magic_color')
                autocrop = request.POST.get('autocrop', '1') == '1'
                pdf_content = compilar_imagenes_a_pdf(
                    imagenes,
                    nombre_archivo=f"{nota.numero_registro.replace('/', '-')}.pdf",
                    filtro=filtro,
                    autocrop=autocrop
                )
                if pdf_content:
                    nota.archivo_pdf.save(f"{nota.numero_registro.replace('/', '-')}.pdf", pdf_content, save=True)

            messages.success(request, f'Nota recibida {nota.numero_registro} registrada exitosamente.')
            return redirect('detalle_nota_recibida', pk=nota.pk)
    else:
        form = NotaRecibidaForm(initial={'recibido_por': request.user, 'fecha_recepcion': date.today()})

    context = {
        'form': form,
        'modo': 'crear',
        'accion': 'Registrar Nota Recibida',
        'proximo_numero': proximo_numero,
    }
    return render(request, 'documentos/recibidos/formulario.html', context)


@login_required
def detalle_nota_recibida(request, pk):
    """
    Vista de detalle de una nota recibida con visor de PDF integrado
    y metadatos completos.
    """
    nota = get_object_or_404(NotaRecibida.objects.select_related('recibido_por', 'documento_respuesta'), pk=pk)
    context = {
        'nota': nota,
    }
    return render(request, 'documentos/recibidos/detalle.html', context)


@login_required
def editar_nota_recibida(request, pk):
    """
    Edita metadatos de una nota recibida y permite actualizar o reemplazar el PDF.
    """
    nota = get_object_or_404(NotaRecibida, pk=pk)

    if request.method == 'POST':
        form = NotaRecibidaForm(request.POST, request.FILES, instance=nota)
        if form.is_valid():
            nota = form.save()

            # Si solicitó quitar el PDF actual
            if request.POST.get('eliminar_pdf_actual') == '1':
                if nota.archivo_pdf:
                    nota.archivo_pdf.delete(save=False)
                    nota.archivo_pdf = None
                    nota.save(update_fields=['archivo_pdf'])

            # Si subió nuevas fotos del móvil para compilar o reemplazar PDF
            nuevas_imagenes = request.FILES.getlist('imagenes_escaneo')
            if nuevas_imagenes and 'archivo_pdf' not in request.FILES:
                filtro = request.POST.get('filtro_escaneo', 'magic_color')
                autocrop = request.POST.get('autocrop', '1') == '1'
                pdf_content = compilar_imagenes_a_pdf(
                    nuevas_imagenes,
                    nombre_archivo=f"{nota.numero_registro.replace('/', '-')}.pdf",
                    filtro=filtro,
                    autocrop=autocrop
                )
                if pdf_content:
                    nota.archivo_pdf.save(f"{nota.numero_registro.replace('/', '-')}.pdf", pdf_content, save=True)

            messages.success(request, f'Nota {nota.numero_registro} actualizada con éxito.')
            return redirect('detalle_nota_recibida', pk=nota.pk)
    else:
        form = NotaRecibidaForm(instance=nota)

    context = {
        'form': form,
        'nota': nota,
        'modo': 'editar',
        'accion': f'Editar Nota {nota.numero_registro}',
    }
    return render(request, 'documentos/recibidos/formulario.html', context)


@login_required
def eliminar_nota_recibida(request, pk):
    """
    Elimina una nota recibida junto a su archivo PDF asociado.
    """
    nota = get_object_or_404(NotaRecibida, pk=pk)
    if request.method == 'POST':
        numero = nota.numero_registro
        nota.delete()
        messages.success(request, f'La nota recibida {numero} ha sido eliminada correctamente.')
        return redirect('lista_notas_recibidas')

    context = {
        'nota': nota,
    }
    return render(request, 'documentos/recibidos/confirmar_eliminar.html', context)


@xframe_options_sameorigin
@login_required
def descargar_pdf_nota_recibida(request, pk):
    """
    Descarga o visualiza inline el PDF de la nota recibida.
    """
    nota = get_object_or_404(NotaRecibida, pk=pk)

    if not nota.archivo_pdf:
        messages.error(request, 'Esta nota no tiene ningún documento PDF adjunto.')
        return redirect('detalle_nota_recibida', pk=nota.pk)

    try:
        pdf_bytes = nota.archivo_pdf.read()
    except Exception:
        messages.error(request, 'No se pudo leer el archivo PDF.')
        return redirect('detalle_nota_recibida', pk=nota.pk)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"{nota.numero_registro.replace('/', '-')}.pdf"
    disposition = 'attachment' if request.GET.get('descargar') == '1' else 'inline'
    response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
    return response


