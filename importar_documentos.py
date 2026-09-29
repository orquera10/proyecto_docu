"""
Script de importación de documentos de la carpeta de red al sistema GestDoc.
Lee archivos .docx, los clasifica (NOTA / INFORME / ACTA) y los carga en la BD Django.

Uso:
    python manage.py shell < importar_documentos.py
  o bien:
    python importar_documentos.py  (desde la raíz del proyecto)
"""

import os
import sys
import re
import django
from datetime import date, datetime
from pathlib import Path

# ─── Setup Django si se ejecuta directamente ──────────────────────────────────
if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()

from docx import Document as DocxDocument
from django.contrib.auth.models import User
from documentos.models import Documento, ItemActa
from documentos.formato import leer_docx_con_listas
from documentos.importacion import extraer_asunto_desde_nombre, extraer_asunto, extraer_destinatario

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

CARPETA = Path(__file__).parent / 'para_analizar'

# Usuario que figurará como "creado_por" en todos los documentos importados
USUARIO_IMPORTACION = 'admin'

# Archivos que NO son documentos del área (borradores, plantillas, datos personales)
EXCLUIR = {
    'membrete 2026 (temporal).docx',
    'datosLucas.docx',
    'Doc1.docx',
    'HIJA 01.docx',
    'HORARIOS DE INFINITO CURSO.docx',
}

# ─── UTILIDADES ───────────────────────────────────────────────────────────────

MESES_ES = {
    'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
    'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
    'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
}

def extraer_fecha(texto: str) -> date | None:
    """Intenta parsear fecha en formato 'DD de MMMM de AAAA' del texto."""
    patron = r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
    m = re.search(patron, texto, re.IGNORECASE)
    if m:
        dia = int(m.group(1))
        mes_str = m.group(2).lower().strip()
        anio = int(m.group(3))
        mes = MESES_ES.get(mes_str)
        if mes:
            try:
                return date(anio, mes, dia)
            except ValueError:
                pass
    return None


def leer_texto_docx(ruta: str) -> str:
    """Extrae el texto completo de un .docx como string limpio."""
    try:
        doc = DocxDocument(ruta)
        parrafos = []
        for p in doc.paragraphs:
            t = p.text.strip()
            if t:
                parrafos.append(t)
        # También tablas (para actas e informes con tablas)
        for tabla in doc.tables:
            for fila in tabla.rows:
                celdas = [c.text.strip() for c in fila.cells if c.text.strip()]
                if celdas:
                    parrafos.append(' | '.join(celdas))
        return '\n'.join(parrafos)
    except Exception as e:
        return ''


def clasificar(nombre_archivo: str) -> str:
    """Determina el tipo (NOTA / INFORME / ACTA) según el nombre del archivo."""
    n = nombre_archivo.lower()
    if n.startswith('acta') or n.startswith('entrega'):
        return 'ACTA'
    if n.startswith('informe') or n.startswith('informe'):
        return 'INFORME'
    if (n.startswith('nota') or n.startswith('pedido') or
            n.startswith('solicitud') or n.startswith('notaopd') or
            n.startswith('notaaire') or n.startswith('notacompra')):
        return 'NOTA'
    # fallback por contenido del nombre
    if 'informe' in n:
        return 'INFORME'
    if 'acta' in n or 'entrega' in n:
        return 'ACTA'
    return 'NOTA'


def extraer_remitente(texto: str) -> str:
    """Extrae el remitente / firmante del documento."""
    # Busca "Alex Magaña" o "Dario Orquera" o "Área de Informática"
    for nombre in ['Alex Magaña', 'Dario Orquera', 'Darío Orquera']:
        if nombre.lower() in texto.lower():
            return nombre
    # Busca patrones de firma
    m = re.search(r'Área de Informática.*?[\n\r]([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)', texto)
    if m:
        return m.group(1)
    return 'Área de Informática'


def extraer_cuerpo_limpio(texto: str, tipo: str) -> str:
    """
    Extrae el cuerpo principal del documento, quitando encabezado y pie.
    Para ACTA devuelve el cuerpo estándar oficial de entrega.
    """
    if tipo == 'ACTA':
        return 'Recibí del Área de Informática los bienes que se detallan a continuación.-'

    lineas = texto.split('\n')
    # Eliminar las primeras líneas de encabezado (fecha, destinatario, etc.)
    inicio = 0
    for i, l in enumerate(lineas):
        if re.search(r'me dirijo|tengo el agrado|por medio|mediante|el presente|desde el área|se informa', l, re.IGNORECASE):
            inicio = i
            break
        if i > 8:  # si no encuentra nada, empieza desde la línea 3
            inicio = min(3, len(lineas)-1)
            break

    # Eliminar pie (firma, "Sin otro particular", etc.)
    fin = len(lineas)
    for i in range(len(lineas)-1, max(inicio, 0), -1):
        l = lineas[i]
        if re.search(r'sin otro particular|atentamente|firma:|aclaración:|dni|autoriza entrega', l, re.IGNORECASE):
            fin = i
            break

    cuerpo = '\n'.join(lineas[inicio:fin]).strip()
    return cuerpo if cuerpo else ''


def extraer_items_acta(texto: str) -> list[dict]:
    """
    Extrae los ítems de la tabla de un acta de entrega.
    Devuelve lista de dicts con {cantidad, descripcion, numero_serie, condicion}
    """
    items = []
    lineas = texto.split('\n')
    for linea in lineas:
        if ' | ' not in linea:
            continue
        partes = [p.strip() for p in linea.split(' | ')]
        if len(partes) < 2:
            continue
        # Detectar si la primera parte es un número (cantidad)
        cantidad_str = partes[0]
        if re.match(r'^\d+m?$', cantidad_str):
            cantidad = int(re.sub(r'\D', '', cantidad_str)) if re.sub(r'\D', '', cantidad_str) else 1
            descripcion = ' | '.join(partes[1:])
            # Intenta detectar número de serie (formato largo alfanumérico)
            serie = ''
            m = re.search(r'[Nn]°?\s*(?:DE\s+SERIE\s+)?([A-Z0-9]{5,})', descripcion)
            if m:
                serie = m.group(1)
            items.append({
                'cantidad': cantidad,
                'descripcion': descripcion[:255],
                'numero_serie': serie[:100],
                'condicion': 'USADO',
            })
    return items


# ─── IMPORTACIÓN PRINCIPAL ────────────────────────────────────────────────────

def importar():
    try:
        usuario = User.objects.get(username=USUARIO_IMPORTACION)
    except User.DoesNotExist:
        usuario = User.objects.filter(is_superuser=True).first()
        if not usuario:
            usuario = User.objects.first()

    print(f"\n{'='*60}")
    print(f"  Importando documentos -> usuario: {usuario.username}")
    print(f"  Carpeta: {CARPETA}")
    print(f"{'='*60}\n")

    archivos = sorted([
        f for f in os.listdir(CARPETA)
        if f.lower().endswith('.docx') and f not in EXCLUIR
    ])

    creados = 0
    errores = 0
    omitidos = 0

    for nombre in archivos:
        ruta = os.path.join(CARPETA, nombre)
        tipo = clasificar(nombre)
        texto = leer_texto_docx(ruta)

        if not texto.strip():
            print(f"  SKIP (vacio): {nombre}")
            omitidos += 1
            continue

        fecha = extraer_fecha(texto) or date.today()
        asunto = extraer_asunto(texto, nombre)
        destinatario = extraer_destinatario(texto)
        remitente = extraer_remitente(texto)
        texto_cuerpo = leer_docx_con_listas(ruta) if tipo != 'ACTA' else texto
        cuerpo = extraer_cuerpo_limpio(texto_cuerpo, tipo)

        try:
            doc = Documento(
                tipo=tipo,
                fecha=fecha,
                asunto=asunto,
                remitente=remitente,
                destinatario=destinatario,
                cuerpo=cuerpo,
                estado='EMITIDO',
                creado_por=usuario,
            )
            doc.save()  # genera número correlativo automáticamente

            # Para ACTA: intentar cargar ítems
            if tipo == 'ACTA':
                items_data = extraer_items_acta(texto)
                for item_d in items_data:
                    ItemActa.objects.create(
                        documento=doc,
                        cantidad=item_d['cantidad'],
                        descripcion=item_d['descripcion'],
                        numero_serie=item_d.get('numero_serie', ''),
                        condicion=item_d.get('condicion', 'USADO'),
                    )
                items_str = f" ({len(items_data)} ítems)" if items_data else ""
            else:
                items_str = ""

            print(f"  OK  [{doc.numero}] [{tipo}] {asunto[:60]}{items_str}")
            creados += 1

        except Exception as e:
            print(f"  ERR en '{nombre}': {e}")
            errores += 1

    print(f"\n{'='*60}")
    print(f"  RESULTADO: {creados} importados | {omitidos} omitidos | {errores} errores")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    importar()
