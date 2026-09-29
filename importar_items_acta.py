"""
Script auxiliar para extraer los ítems de las tablas de actas directamente
usando python-docx, y cargarlos en la BD.
"""
import os, sys, re, django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from docx import Document as DocxDocument
from documentos.models import Documento, ItemActa

CARPETA = r'\\snfserver2\Informatica\notas de pedido'

actas = Documento.objects.filter(tipo='ACTA').order_by('numero')
archivos_acta = [
    f for f in os.listdir(CARPETA)
    if f.lower().endswith('.docx') and not f.startswith('~')
    and (f.lower().startswith('acta') or f.lower().startswith('entrega'))
]

print(f"Procesando {actas.count()} actas...")
items_creados = 0


def clean(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


for acta in actas:
    # Busca el archivo por similitud de nombre
    asunto_c = clean(acta.asunto)
    match = None
    best = 0
    for arch in archivos_acta:
        arch_c = clean(arch.replace('.docx', ''))
        # longitud de prefijo comun
        comun = sum(1 for a, b in zip(asunto_c, arch_c) if a == b)
        if comun > best:
            best = comun
            match = arch
    if not match or best < 4:
        print(f"  SIN MATCH: {acta.numero} - {acta.asunto}")
        continue

    ruta = os.path.join(CARPETA, match)
    try:
        doc = DocxDocument(ruta)
        acta_items = []
        tablas_procesadas = 0
        for tabla in doc.tables:
            # Solo tablas con 3 columnas (Unidad | Cantidad | Detalle)
            if len(tabla.columns) < 2:
                continue
            # Ignorar tablas de firma
            primera_celda = tabla.rows[0].cells[0].text.strip().lower()
            if 'recibe' in primera_celda or 'firma' in primera_celda:
                continue
            # Solo la primera copia (evitar duplicado original/copia del acta)
            tablas_procesadas += 1
            if tablas_procesadas > 1:
                break

            for fila in tabla.rows:
                celdas = [c.text.strip() for c in fila.cells]
                # Eliminar merged cells duplicadas
                celdas_unicas = []
                for c in celdas:
                    if not celdas_unicas or c != celdas_unicas[-1]:
                        celdas_unicas.append(c)
                celdas = celdas_unicas

                if len(celdas) < 2:
                    continue
                # Saltar fila de encabezado
                if celdas[0].lower() in ['unidad', 'tipo', 'cantidad', 'detalle', 'descripcion']:
                    continue
                if len(celdas) > 1 and celdas[1].lower() in ['cantidad', 'detalle']:
                    continue

                # col0=Unidad/Tipo, col1=Cantidad, col2=Detalle
                if len(celdas) >= 3:
                    cant_str = celdas[1]
                    detalle = celdas[2]
                else:
                    cant_str = celdas[0]
                    detalle = celdas[1]

                if not detalle or detalle.lower() in ['detalle', 'descripcion']:
                    continue

                cant_num = re.sub(r'\D', '', cant_str)
                cantidad = int(cant_num) if cant_num and 0 < int(cant_num) < 10000 else 1

                serie = ''
                m_serie = re.search(r'(?:serie|s[/.]?n)[:\s]*([A-Z0-9]{5,})', detalle, re.IGNORECASE)
                if not m_serie:
                    m_serie = re.search(r'\b([A-Z]{2}[0-9]{4,}|[0-9]{6,})\b', detalle)
                if m_serie:
                    serie = m_serie.group(1)[:100]

                acta_items.append({
                    'cantidad': cantidad,
                    'descripcion': detalle[:255],
                    'numero_serie': serie,
                    'condicion': 'USADO',
                })

        # Eliminar ítems duplicados (la tabla del acta se repite: original y copia)
        vistos = set()
        items_finales = []
        for it in acta_items:
            key = (it['cantidad'], it['descripcion'][:50])
            if key not in vistos:
                vistos.add(key)
                items_finales.append(it)

        for it in items_finales:
            ItemActa.objects.create(
                documento=acta,
                cantidad=it['cantidad'],
                descripcion=it['descripcion'],
                numero_serie=it['numero_serie'],
                condicion=it['condicion'],
            )
            items_creados += 1

        marca = f"({len(items_finales)} items)" if items_finales else "(sin items en tabla)"
        print(f"  OK  {acta.numero} <- {match} {marca}")

    except Exception as e:
        print(f"  ERR {acta.numero}: {e}")

print(f"\nTotal items de actas creados: {items_creados}")
