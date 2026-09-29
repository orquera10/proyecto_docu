"""
Script de sincronización y auditoría entre la carpeta de red
\\snfserver2\Informatica\notas de pedido y la base de datos de Docu.
"""
import os
import re
import sys
from datetime import date
from pathlib import Path
import django

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from docx import Document as DocxDocument
from pypdf import PdfReader

from documentos.models import Documento, ItemActa
from documentos.formato import leer_docx_con_listas
from documentos.utils import generar_numero

CARPETA_RED = r'\\snfserver2\Informatica\notas de pedido'
CARPETA_LOCAL = str(Path(__file__).parent / 'para_analizar')


def get_user():
    user = User.objects.filter(username='dorquera').first()
    if not user:
        user = User.objects.filter(username='admin').first()
    if not user:
        user = User.objects.first()
    return user


def extract_items_from_acta_docx(fpath):
    """Extrae los ítems de las tablas de un acta Word de forma robusta."""
    doc = DocxDocument(fpath)
    acta_items = []
    for tabla in doc.tables:
        if len(tabla.columns) < 2:
            continue
        first_row_text = ' '.join([c.text.strip().lower() for c in tabla.rows[0].cells])
        if 'recibe' in first_row_text or 'firma' in first_row_text or 'autoriza' in first_row_text:
            continue

        for fila in tabla.rows:
            celdas = [c.text.strip() for c in fila.cells]
            # dedup celdas consecutivas idénticas (por celdas combinadas)
            u_cells = []
            for c in celdas:
                if not u_cells or c != u_cells[-1]:
                    u_cells.append(c)
            if len(u_cells) < 2:
                continue

            # Descartar filas de encabezado
            if u_cells[0].lower() in ['unidad', 'tipo', 'item', 'ítem'] and u_cells[1].lower() in ['cantidad', 'detalle', 'descripcion', 'descripción']:
                continue
            if u_cells[0].lower() in ['cantidad', 'detalle', 'descripcion']:
                continue

            # Determinar cantidad y detalle
            if len(u_cells) >= 3:
                cant_str = u_cells[1]
                detalle = u_cells[2]
            else:
                cant_str = u_cells[0]
                detalle = u_cells[1]

            if not detalle or detalle.lower() in ['detalle', 'descripcion', 'descripción']:
                continue

            cant_num = re.sub(r'\D', '', cant_str)
            cantidad = int(cant_num) if cant_num and 0 < int(cant_num) < 10000 else 1

            # Detectar número de serie o código
            serie = ''
            m_serie = re.search(r'(?:serie|s[/.]?n|codig[:o]?|s/n|código)[:\s]*([A-Z0-9-]{4,})', detalle, re.IGNORECASE)
            if not m_serie:
                m_serie = re.search(r'\b([A-Z]{2}[0-9]{4,}|[0-9]{6,})\b', detalle)
            if m_serie:
                serie = m_serie.group(1)[:100]

            acta_items.append({
                'cantidad': cantidad,
                'descripcion': detalle[:255],
                'numero_serie': serie,
                'condicion': 'USADO'
            })

        # Solo la primera tabla de bienes (para no duplicar original y copia)
        if acta_items:
            break

    # Deduplicar por si acaso
    vistos = set()
    items_finales = []
    for it in acta_items:
        key = (it['cantidad'], it['descripcion'][:60])
        if key not in vistos:
            vistos.add(key)
            items_finales.append(it)
    return items_finales


def sincronizar():
    usuario = get_user()
    print("=" * 70)
    print(f"SINCRONIZACIÓN Y CORRECCIÓN: Carpeta de red -> Base de Datos")
    print(f"Usuario: {usuario.username}")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. ACTUALIZAR INF-004/2026 con versión final de la red
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 1. Actualizando INF-004/2026 ---")
    doc_inf004 = Documento.objects.filter(numero='INF-004/2026').first()
    if doc_inf004:
        fpath_inf004 = os.path.join(CARPETA_RED, 'informe de entrega de equipos nuevos para secre.docx')
        if not os.path.exists(fpath_inf004):
            fpath_inf004 = os.path.join(CARPETA_LOCAL, 'informe de entrega de equipos nuevos para secre.docx')
        texto_completo = leer_docx_con_listas(fpath_inf004)

        # Extraer cuerpo limpio
        lineas = texto_completo.split('\n')
        inicio = 0
        for i, l in enumerate(lineas):
            if re.search(r'me dirijo|tengo el agrado|por medio|mediante|el presente', l, re.IGNORECASE):
                inicio = i
                break
        fin = len(lineas)
        for i in range(len(lineas) - 1, inicio, -1):
            if re.search(r'sin otro particular|atentamente|firma:', lineas[i], re.IGNORECASE):
                fin = i
                break
        cuerpo_nuevo = '\n'.join(lineas[inicio:fin]).strip()

        doc_inf004.fecha = date(2026, 8, 12)
        doc_inf004.cuerpo = cuerpo_nuevo
        doc_inf004.save()
        print(f"  OK INF-004/2026 actualizado: fecha={doc_inf004.fecha}, largo cuerpo={len(cuerpo_nuevo)}")
    else:
        print("  AVISO: No se encontró INF-004/2026")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. IMPORTAR LOS 8 DOCUMENTOS NUEVOS
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 2. Importando Documentos Nuevos de la Red ---")

    nuevos_docs = [
        # 1. Acta Fabian Arias
        {
            'tipo': 'ACTA',
            'fecha': date(2026, 9, 15),
            'asunto': 'Acta Entrega estabilizador despacho fabian arias',
            'remitente': 'Alex Magaña',
            'destinatario': 'Despacho – Fabian Arias',
            'receptor_nombre': 'Fabian Arias',
            'archivo': 'actaEntrega estabilizador despacho fabian arias.docx',
            'cuerpo': 'Recibí del Área de Informática los bienes que se detallan a continuación.-',
        },
        # 2. Acta Monterrico
        {
            'tipo': 'ACTA',
            'fecha': date(2026, 9, 21),
            'asunto': 'Acta Entrega teclado y pc monterrico',
            'remitente': 'Dario Orquera',
            'destinatario': 'OPD Monterrico',
            'receptor_nombre': '',
            'archivo': 'actaEntrega teclado y pc monterrico.docx',
            'cuerpo': 'Recibí del Área de Informática los bienes que se detallan a continuación.-',
        },
        # 3. Informe OPD Cuyaya
        {
            'tipo': 'INFORME',
            'fecha': date(2026, 9, 23),
            'asunto': 'Informe Técnico – Falla y reemplazo de unidad SSD OPD Cuyaya',
            'remitente': 'Área de Informática',
            'destinatario': 'Oficina de Protección de Derechos (OPD) Cuyaya',
            'archivo': 'informeTecnico_informe disco opd cuyaya.docx',
            'cuerpo': (
                "Por medio del presente, se informa la situación relacionada con el equipo informático asignado a la Oficina de Protección de Derechos (OPD) Cuyaya.\n\n"
                "En una primera instancia, la CPU que se encontraba asignada a dicha dependencia presentó inconvenientes relacionados con su unidad de almacenamiento, motivo por el cual se procedió al reemplazo de la CPU por otro equipo de similares características, a fin de garantizar la continuidad de las tareas administrativas.\n\n"
                "Posteriormente, el equipo actualmente asignado a la OPD Cuyaya presentó nuevamente una falla en su unidad de almacenamiento SSD. De acuerdo con la revisión realizada, dicha unidad resultó dañada luego de producirse un corte del suministro eléctrico.\n\n"
                "En esta oportunidad, y a diferencia de la situación anterior, no resulta necesario reemplazar la CPU completa, sino únicamente la unidad de almacenamiento SSD afectada.\n\n"
                "Por tal motivo, se deja constancia de que, en caso de que el equipo vuelva a presentar este inconveniente en el futuro, la adquisición de la nueva unidad de almacenamiento SSD quedará a cargo del responsable de la OPD Cuyaya.\n\n"
                "Sin otro particular, se emite el presente informe para dejar debidamente justificada la adecuación de las especificaciones técnicas incorporadas en el presupuesto presentado."
            ),
        },
        # 4. Nota Delia Alancay (Último pedido ampliado)
        {
            'tipo': 'NOTA',
            'fecha': date(2026, 9, 18),
            'asunto': 'Solicitud de adquisición de discos SSD, placas Wi-Fi y Access Points UniFi para OPD',
            'remitente': 'Área de Informática',
            'destinatario': 'A la Coordinadora de OPD de la Secretaría de Niñez, Adolescencia y Familia\nDra. Delia Alancay\nSu despacho:',
            'archivo': 'nota dra DELIA ALANCAY opd ULTIMO.docx',
            'cuerpo': None,  # se lee del archivo
        },
        # 5. Nota Aire Acondicionado Servidores 2026
        {
            'tipo': 'NOTA',
            'fecha': date(2026, 8, 15),
            'asunto': 'Solicitud urgente de adquisición e instalación de equipo de aire acondicionado para servidores',
            'remitente': 'Área de Informática',
            'destinatario': 'A la Secretaria de Niñez, Adolescencia y Familia\nDra. Marta Iriarte\nSu despacho:',
            'archivo': 'nota_pedido_aire_2026.docx',
            'cuerpo': None,  # se lee del archivo
        },
        # 6. Nota Herramientas 2026
        {
            'tipo': 'NOTA',
            'fecha': date(2026, 7, 16),
            'asunto': 'Solicitud urgente de herramientas de mantenimiento técnico',
            'remitente': 'Área de Informática',
            'destinatario': 'A la Secretaria de Niñez, Adolescencia y Familia\nDra. Marta Iriarte\nSu despacho:',
            'archivo': 'nota_pedido_herramientas_2026.docx',
            'cuerpo': None,  # se lee del archivo
        },
        # 7. Nota Insumos y Hardware 2026
        {
            'tipo': 'NOTA',
            'fecha': date(2026, 7, 16),
            'asunto': 'Solicitud urgente de adquisición de insumos, periféricos y equipamiento de red',
            'remitente': 'Área de Informática',
            'destinatario': 'A la Secretaria de Niñez, Adolescencia y Familia\nDra. Marta Iriarte\nSu despacho:',
            'archivo': 'nota_pedido_insumos_2026.docx',
            'cuerpo': None,  # se lee del archivo
        },
        # 8. Nota Disco Línea 102 (2025 en PDF)
        {
            'tipo': 'NOTA',
            'fecha': date(2025, 4, 11),
            'asunto': 'Solicitud urgente de compra de disco externo 2TB para servidor de Línea 102',
            'remitente': 'Darío Joaquín Orquera / Alexander Magaña',
            'destinatario': 'Al Secretario de Niñez, Adolescencia y Familia\nDr. Sergio Jaime Armando Vidaurre\nSu despacho:',
            'archivo': 'nota_disco_102.pdf',
            'cuerpo': (
                "Me dirijo a usted con el fin de informarle y solicitar con carácter de urgencia la compra de un disco externo para el servidor correspondiente a la Línea 102. Cabe destacar que esta solicitud ya fue presentada el año pasado sin haber obtenido respuesta, motivo por el cual reiteramos la necesidad de su adquisición.\n\n"
                "La razón de esta solicitud radica en que el servidor en cuestión se encuentra actualmente saturado de grabaciones, lo que compromete su rendimiento y estabilidad. Para garantizar su correcto funcionamiento, es indispensable liberar espacio de almacenamiento interno de forma inmediata.\n\n"
                "Por lo tanto, se requiere la compra urgente de un (1) disco externo con las siguientes características mínimas:\n"
                "• Capacidad: 2TB\n"
                "• Interfaz de conexión: USB 3.2 GEN 2\n"
                "• Cache de datos: 1,05 Gb.\n\n"
                "Dejo constancia de que el servidor se encuentra operando al límite de su capacidad de almacenamiento, lo que afecta de manera directa su funcionamiento y confiabilidad.\n\n"
                "Sin otro particular y en espera de una respuesta favorable me despido de Ud. con atenta consideración y respeto.-"
            ),
        },
    ]

    for item in nuevos_docs:
        # Verificar si ya existe un documento con ese asunto o archivo
        existente = Documento.objects.filter(asunto=item['asunto']).first()
        if existente:
            print(f"  YA EXISTE: [{existente.numero}] {item['asunto']}")
            doc_obj = existente
        else:
            cuerpo = item['cuerpo']
            if not cuerpo:
                # Leer del archivo .docx
                fpath = os.path.join(CARPETA_RED, item['archivo'])
                if not os.path.exists(fpath):
                    fpath = os.path.join(CARPETA_LOCAL, item['archivo'])
                texto_raw = leer_docx_con_listas(fpath)

                # Extraer cuerpo limpio
                lineas = texto_raw.split('\n')
                inicio = 0
                for i, l in enumerate(lineas):
                    if re.search(r'me dirijo|tengo el agrado|por medio|mediante|el presente', l, re.IGNORECASE):
                        inicio = i
                        break
                fin = len(lineas)
                for i in range(len(lineas) - 1, inicio, -1):
                    if re.search(r'sin otro particular|atentamente|saludo a usted', lineas[i], re.IGNORECASE):
                        fin = i
                        break
                cuerpo = '\n'.join(lineas[inicio:fin]).strip()

            numero_nuevo = generar_numero(item['tipo'], item['fecha'].year)

            doc_obj = Documento(
                tipo=item['tipo'],
                numero=numero_nuevo,
                fecha=item['fecha'],
                asunto=item['asunto'],
                remitente=item['remitente'],
                destinatario=item['destinatario'],
                receptor_nombre=item.get('receptor_nombre', ''),
                receptor_dni='',
                cuerpo=cuerpo,
                estado='EMITIDO',
                creado_por=usuario,
            )
            doc_obj.save()
            print(f"  CREADO: [{doc_obj.numero}] [{doc_obj.tipo}] {doc_obj.asunto}")

        # Si es ACTA, extraer y cargar sus items
        if item['tipo'] == 'ACTA' and doc_obj.items.count() == 0:
            fpath_acta = os.path.join(CARPETA_RED, item['archivo'])
            if not os.path.exists(fpath_acta):
                fpath_acta = os.path.join(CARPETA_LOCAL, item['archivo'])
            items_acta = extract_items_from_acta_docx(fpath_acta)
            for it in items_acta:
                ItemActa.objects.create(
                    documento=doc_obj,
                    cantidad=it['cantidad'],
                    descripcion=it['descripcion'],
                    numero_serie=it['numero_serie'],
                    condicion=it['condicion'],
                )
            print(f"    -> {len(items_acta)} items creados para {doc_obj.numero}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. EXTRAER Y CARGAR ITEMS EN LAS 21 ACTAS EXISTENTES
    # ──────────────────────────────────────────────────────────────────────────
    print("\n--- 3. Extrayendo ítems para actas existentes en la BD ---")

    archivos_actas_red = [
        f for f in os.listdir(CARPETA_RED)
        if f.lower().endswith('.docx') and not f.startswith('~')
        and (f.lower().startswith('acta') or f.lower().startswith('entrega'))
    ]

    def norm_clean(s):
        return re.sub(r'[^a-z0-9]', '', s.lower())

    actas_db = Documento.objects.filter(tipo='ACTA').order_by('numero')
    items_total_creados = 0

    # Diccionario de inferencia de destinatario/sector si está vacío
    SECTORES_ACTAS = {
        'cdi rio blanco': 'CDI Río Blanco',
        'mario vacaflor': 'Dirección de Niñez – Dr. Mario Vacaflor',
        'mercedes carreras': 'Mercedes Carreras',
        'norma serrano': 'Norma Serrano',
        'claudia mamani': 'Claudia Mamani',
        'despacho ninez luciana': 'Despacho de Niñez – Luciana',
        'facundo compras': 'Área de Compras – Facundo',
        'sergio fernandez': 'Sergio Fernandez',
        'socio educativo': 'Centro Socio Educativo Alto Comedero',
        'atilio cruz': 'Atilio Cruz',
        'chara': 'Alex Chara',
        'impresora epson opd': 'Coordinación de OPD',
        'opd libertador': 'OPD Libertador',
        'pase cpu dire a despacho': 'Despacho de Niñez',
        'prestamo de cpu cuyaya': 'OPD Cuyaya',
        'teclado funcionando': 'OPD Monterrico',
        'opd san antonio': 'OPD San Antonio',
        'guillermon': 'Hogar Guillermón',
        'yala': 'OPD Yala',
        'lenovo despacho': 'Despacho de Niñez',
    }

    for acta in actas_db:
        # Completar destinatario si está vacío
        if not acta.destinatario or not acta.destinatario.strip():
            for key, val in SECTORES_ACTAS.items():
                if norm_clean(key) in norm_clean(acta.asunto):
                    acta.destinatario = val
                    acta.save(update_fields=['destinatario'])
                    print(f"  Destinatario actualizado para {acta.numero}: {val}")
                    break

        if acta.items.count() > 0:
            print(f"  {acta.numero} ya tiene {acta.items.count()} items. Omitiendo.")
            continue

        # Buscar el archivo correspondiente
        asunto_norm = norm_clean(acta.asunto)
        match_file = None
        best_score = 0
        for arch in archivos_actas_red:
            arch_norm = norm_clean(arch.replace('.docx', ''))
            # Medir coincidencia
            if asunto_norm == arch_norm or arch_norm in asunto_norm or asunto_norm in arch_norm:
                match_file = arch
                break
            score = sum(1 for a, b in zip(asunto_norm, arch_norm) if a == b)
            if score > best_score:
                best_score = score
                match_file = arch

        if not match_file or (best_score < 4 and match_file != arch):
            print(f"  SIN MATCH para {acta.numero}: {acta.asunto}")
            continue

        fpath = os.path.join(CARPETA_RED, match_file)
        if not os.path.exists(fpath):
            fpath = os.path.join(CARPETA_LOCAL, match_file)

        items_extraidos = extract_items_from_acta_docx(fpath)
        for it in items_extraidos:
            ItemActa.objects.create(
                documento=acta,
                cantidad=it['cantidad'],
                descripcion=it['descripcion'],
                numero_serie=it['numero_serie'],
                condicion=it['condicion'],
            )
            items_total_creados += 1

        print(f"  OK {acta.numero} <- {match_file} ({len(items_extraidos)} items cargados)")

    print(f"\nTotal nuevos items de actas creados: {items_total_creados}")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. RECUENTO Y ESTADO FINAL
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RECUENTO FINAL EN BASE DE DATOS:")
    total = Documento.objects.count()
    notas = Documento.objects.filter(tipo='NOTA').count()
    informes = Documento.objects.filter(tipo='INFORME').count()
    actas = Documento.objects.filter(tipo='ACTA').count()
    items = ItemActa.objects.count()
    print(f"  Total Documentos: {total}")
    print(f"    - Notas: {notas}")
    print(f"    - Informes: {informes}")
    print(f"    - Actas de Entrega: {actas}")
    print(f"  Total Ítems de Actas: {items}")
    print("=" * 70)


if __name__ == '__main__':
    sincronizar()
