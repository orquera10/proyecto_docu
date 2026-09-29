"""Listas de Word conservadas como texto editable y salida HTML escapada."""
import re
from collections import defaultdict

from docx import Document
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.table import Table
from docx.text.paragraph import Paragraph
from django.utils.html import escape
from django.utils.safestring import mark_safe


def leer_docx_con_listas(ruta, tablas_markdown=False):
    doc = Document(ruta)
    try:
        numbering = doc.part.part_related_by(RT.NUMBERING).element
    except KeyError:
        numbering = None
    contadores = defaultdict(dict)

    def marcador(p):
        props = [p._p.pPr]
        estilo = p.style
        while estilo is not None:
            props.append(estilo.element.pPr)
            estilo = estilo.base_style
        num_id, nivel = None, None
        for prop in props:
            if prop is None or prop.numPr is None:
                continue
            num = prop.numPr
            if num_id is None and num.numId is not None:
                num_id = num.numId.val
            if nivel is None and num.ilvl is not None:
                nivel = num.ilvl.val
        if num_id in (None, 0) or numbering is None:
            return ''
        nivel = nivel or 0
        nums = numbering.xpath(f'./w:num[@w:numId="{num_id}"]')
        if not nums:
            return ''
        abstract_id = nums[0].find(qn('w:abstractNumId')).get(qn('w:val'))
        niveles = numbering.xpath(f'./w:abstractNum[@w:abstractNumId="{abstract_id}"]/w:lvl[@w:ilvl="{nivel}"]')
        overrides = nums[0].xpath(f'./w:lvlOverride[@w:ilvl="{nivel}"]')
        if overrides and overrides[0].find(qn('w:lvl')) is not None:
            niveles = [overrides[0].find(qn('w:lvl'))]
        if not niveles:
            return ''
        lvl = niveles[0]
        fmt = lvl.find(qn('w:numFmt')).get(qn('w:val'))
        if fmt == 'bullet':
            return '  ' * nivel + '• '
        if fmt == 'none':
            return ''
        start = lvl.find(qn('w:start'))
        inicio = int(start.get(qn('w:val'))) if start is not None else 1
        if overrides:
            start = overrides[0].find(qn('w:startOverride'))
            if start is not None:
                inicio = int(start.get(qn('w:val')))
        estado = contadores[num_id]
        estado[nivel] = estado.get(nivel, inicio - 1) + 1
        for n in list(estado):
            if n > nivel:
                del estado[n]
        patron = lvl.find(qn('w:lvlText'))
        patron = patron.get(qn('w:val')) if patron is not None else f'%{nivel+1}.'
        def sustituir(m):
            n = int(m.group(1)) - 1
            valor = estado.get(n, 1)
            if n == nivel and fmt in ('lowerLetter', 'upperLetter'):
                letras = ''
                while valor:
                    valor, resto = divmod(valor - 1, 26)
                    letras = chr(97 + resto) + letras
                return letras.upper() if fmt == 'upperLetter' else letras
            if n == nivel and fmt in ('lowerRoman', 'upperRoman'):
                romano = ''
                for numero, letra in [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]:
                    while valor >= numero:
                        romano += letra
                        valor -= numero
                return romano.lower() if fmt == 'lowerRoman' else romano
            return str(valor)
        return '  ' * nivel + re.sub(r'%(\d+)', sustituir, patron) + ' '

    lineas = []
    for elemento in doc.element.body:
        if elemento.tag == qn('w:p'):
            p = Paragraph(elemento, doc)
            if p.text.strip():
                lineas.append(marcador(p) + p.text.strip())
        elif elemento.tag == qn('w:tbl'):
            tabla = Table(elemento, doc)
            filas = []
            for fila in tabla.rows:
                # Las celdas combinadas pueden aparecer varias veces.
                vistas, valores = set(), []
                for celda in fila.cells:
                    if celda._tc not in vistas:
                        vistas.add(celda._tc)
                        valores.append(' '.join(celda.text.split()))
                if any(valores):
                    filas.append(valores)
            if not filas:
                continue
            if tablas_markdown:
                max_cols = max(len(r) for r in filas)
                if max_cols >= 2:
                    header = [c.replace('|', r'\|') for c in filas[0]]
                    while len(header) < max_cols:
                        header.append('')
                    aligns = [':---:' if any(k in h.lower() for k in ['cant', 'n°', 'ítem', 'item']) else ':---' for h in header]
                    lineas.append('')
                    lineas.append('| ' + ' | '.join(header) + ' |')
                    lineas.append('| ' + ' | '.join(aligns) + ' |')
                    for f in filas[1:]:
                        clean_row = [c.replace('|', r'\|') for c in f]
                        while len(clean_row) < max_cols:
                            clean_row.append('')
                        lineas.append('| ' + ' | '.join(clean_row) + ' |')
                    lineas.append('')
                else:
                    for f in filas:
                        lineas.append(' '.join(f))
            else:
                encabezados = filas[0]
                es_cantidad = len(encabezados) == 2 and encabezados[0].lower() == 'cantidad'
                for fila in filas[1:] if es_cantidad else filas:
                    if es_cantidad:
                        lineas.append(f'• {fila[0]} — {fila[1]}')
                    else:
                        lineas.append('• ' + ' | '.join(fila))
    return '\n'.join(lineas)


import os
import base64
from pathlib import Path
from django.conf import settings


def resolver_src_imagen(url_o_archivo, para_pdf=False):
    url_limpia = (url_o_archivo or '').strip().strip('\'"')
    if not url_limpia:
        return ''

    if para_pdf:
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        media_root = getattr(settings, 'MEDIA_ROOT', None)
        if media_root:
            media_root_path = Path(media_root)
            if url_limpia.startswith(media_url):
                rel_path = url_limpia[len(media_url):].lstrip('/')
                local_path = media_root_path / rel_path
                if local_path.exists():
                    ext = local_path.suffix.lower()
                    mime = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/webp' if ext == '.webp' else 'image/gif'
                    try:
                        b64 = base64.b64encode(local_path.read_bytes()).decode('ascii')
                        return f'data:{mime};base64,{b64}'
                    except Exception:
                        pass
            local_path = media_root_path / url_limpia.lstrip('/')
            if local_path.exists():
                ext = local_path.suffix.lower()
                mime = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/webp' if ext == '.webp' else 'image/gif'
                try:
                    b64 = base64.b64encode(local_path.read_bytes()).decode('ascii')
                    return f'data:{mime};base64,{b64}'
                except Exception:
                    pass

    if not (url_limpia.startswith('http://') or url_limpia.startswith('https://') or url_limpia.startswith('/') or url_limpia.startswith('data:')):
        media_url = getattr(settings, 'MEDIA_URL', '/media/')
        url_limpia = f'{media_url.rstrip("/")}/{url_limpia.lstrip("/")}'
    return url_limpia


def formatear_linea_texto(texto_linea):
    """Escapa HTML y luego aplica formato seguro para negrita, cursiva, subrayado y tachado."""
    escaped = escape(texto_linea)
    escaped = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escaped)
    escaped = re.sub(r'(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)', r'<em>\1</em>', escaped)
    escaped = re.sub(r'&lt;u&gt;(.+?)&lt;/u&gt;', r'<u>\1</u>', escaped, flags=re.IGNORECASE)
    escaped = re.sub(r'~~(.+?)~~', r'<s>\1</s>', escaped)
    return escaped


def es_linea_separadora_tabla(linea):
    """Detecta si una línea es la fila separadora de columnas de una tabla Markdown (| :--- | :---: | ---: |)."""
    linea_strip = (linea or '').strip()
    if not linea_strip or '|' not in linea_strip:
        return False
    clean = linea_strip.strip('|')
    partes = [p.strip() for p in clean.split('|')]
    if not partes:
        return False
    return all(re.match(r'^:?-{2,}:?$', p) for p in partes)


def parsear_fila_tabla(linea):
    """Divide una fila de tabla Markdown en celdas individuales limpias."""
    clean = (linea or '').strip()
    if clean.startswith('|'):
        clean = clean[1:]
    if clean.endswith('|'):
        clean = clean[:-1]
    placeholder = "___ESCAPED_PIPE___"
    clean = clean.replace(r'\|', placeholder)
    partes = [p.strip().replace(placeholder, '|') for p in clean.split('|')]
    return partes


def extraer_alineaciones_tabla(sep_line):
    """Extrae las alineaciones CSS ('left', 'center', 'right') de la fila separadora."""
    partes = parsear_fila_tabla(sep_line)
    aligns = []
    for p in partes:
        if p.startswith(':') and p.endswith(':'):
            aligns.append('center')
        elif p.endswith(':'):
            aligns.append('right')
        else:
            aligns.append('left')
    return aligns


def cuerpo_html(texto, para_pdf=False):
    """Renderiza texto plano, listas, tablas Markdown, formato y bloques de imagen sin aceptar HTML malicioso."""
    salida = []
    lineas = (texto or '').splitlines()
    i = 0
    total = len(lineas)

    while i < total:
        linea = lineas[i]
        linea_strip = linea.strip()
        if not linea_strip:
            i += 1
            continue

        # 1. Detección de Tabla Markdown
        if '|' in linea_strip and (i + 1 < total) and es_linea_separadora_tabla(lineas[i + 1]):
            header_cells = parsear_fila_tabla(linea_strip)
            aligns = extraer_alineaciones_tabla(lineas[i + 1])
            num_cols = len(header_cells)
            i += 2  # Saltear encabezado y fila separadora

            data_rows = []
            while i < total:
                curr_strip = lineas[i].strip()
                if not curr_strip or '|' not in curr_strip:
                    break
                row_cells = parsear_fila_tabla(curr_strip)
                # Normalizar cantidad de columnas
                if len(row_cells) < num_cols:
                    row_cells.extend([''] * (num_cols - len(row_cells)))
                else:
                    row_cells = row_cells[:num_cols]
                data_rows.append(row_cells)
                i += 1

            if para_pdf:
                table_lines = [
                    '<table class="tabla-cuerpo-pdf" style="width: 100%; border-collapse: collapse; margin: 10pt 0 12pt 0; page-break-inside: avoid;">',
                    '  <thead>',
                    '    <tr>'
                ]
                for idx, h in enumerate(header_cells):
                    align = aligns[idx] if idx < len(aligns) else 'left'
                    th_text = formatear_linea_texto(h)
                    table_lines.append(f'      <th style="border: 0.75pt solid #333333; padding: 4pt 6pt; background-color: #f1f5f9; font-weight: bold; font-size: 10pt; text-align: {align};">{th_text}</th>')
                table_lines.append('    </tr>')
                table_lines.append('  </thead>')
                table_lines.append('  <tbody>')
                for row in data_rows:
                    table_lines.append('    <tr>')
                    for idx, c in enumerate(row):
                        align = aligns[idx] if idx < len(aligns) else 'left'
                        td_text = formatear_linea_texto(c)
                        table_lines.append(f'      <td style="border: 0.75pt solid #333333; padding: 4pt 6pt; font-size: 10pt; line-height: 1.35; text-align: {align};">{td_text}</td>')
                    table_lines.append('    </tr>')
                table_lines.append('  </tbody>')
                table_lines.append('</table>')
                salida.append('\n'.join(table_lines))
            else:
                table_lines = [
                    '<div class="table-responsive doc-table-wrapper" style="overflow-x: auto; margin: 14px 0 18px 0;">',
                    '  <table class="doc-markdown-table" style="width: 100%; border-collapse: collapse; font-size: 13.5px; line-height: 1.5;">',
                    '    <thead>',
                    '      <tr style="background-color: #f8fafc; border-bottom: 2px solid #cbd5e1;">'
                ]
                for idx, h in enumerate(header_cells):
                    align = aligns[idx] if idx < len(aligns) else 'left'
                    th_text = formatear_linea_texto(h)
                    table_lines.append(f'        <th style="padding: 8px 12px; font-weight: 700; color: #1e293b; border: 1px solid #cbd5e1; text-align: {align};">{th_text}</th>')
                table_lines.append('      </tr>')
                table_lines.append('    </thead>')
                table_lines.append('    <tbody>')
                for r_idx, row in enumerate(data_rows):
                    bg = 'background-color: #ffffff;' if r_idx % 2 == 0 else 'background-color: #f8fafc;'
                    table_lines.append(f'      <tr style="{bg}">')
                    for idx, c in enumerate(row):
                        align = aligns[idx] if idx < len(aligns) else 'left'
                        td_text = formatear_linea_texto(c)
                        table_lines.append(f'        <td style="padding: 8px 12px; border: 1px solid #e2e8f0; color: #334155; text-align: {align};">{td_text}</td>')
                    table_lines.append('      </tr>')
                table_lines.append('    </tbody>')
                table_lines.append('  </table>')
                table_lines.append('</div>')
                salida.append('\n'.join(table_lines))
            continue

        # 2. Detección de Bloques de Imagen
        m_img1 = re.match(r'^\[IMAGEN:\s*([^|\]]+)(?:\s*\|\s*([^\]]+))?\]$', linea_strip, re.IGNORECASE)
        m_img2 = re.match(r'^!\[(.*?)\]\((.*?)\)$', linea_strip)
        if m_img1 or m_img2:
            if m_img1:
                img_url = m_img1.group(1).strip()
                caption = (m_img1.group(2) or '').strip()
            else:
                caption = (m_img2.group(1) or '').strip()
                img_url = m_img2.group(2).strip()

            src = resolver_src_imagen(img_url, para_pdf=para_pdf)
            caption_esc = escape(caption)

            if para_pdf:
                img_html = f'<div style="text-align:center; margin:12pt 0; page-break-inside:avoid;"><img src="{src}" width="380" />'
                if caption_esc:
                    img_html += f'<p style="font-size:8.5pt; color:#555555; margin-top:4pt; font-style:italic; text-align:center;">{caption_esc}</p>'
                img_html += '</div>'
            else:
                img_html = f'<div class="doc-inline-img-container" style="text-align:center; margin:18px 0;">'
                img_html += f'<img src="{src}" alt="{caption_esc}" style="max-width:85%; max-height:420px; border-radius:6px; box-shadow:0 2px 10px rgba(0,0,0,0.08); border:1px solid #e2e8f0; display:inline-block;">'
                if caption_esc:
                    img_html += f'<p class="img-caption" style="font-size:12px; color:#64748b; margin-top:6px; font-style:italic;">{caption_esc}</p>'
                img_html += '</div>'

            salida.append(img_html)
            i += 1
            continue

        # 3. Detección de Listas con Viñetas o Numeración
        m = re.match(r'^(\s*)([•●▪◦*\-\x95]|\d+(?:\.\d+)*[.)]|[a-zA-Z][.)]|[ivxlcdmIVXLCDM]+[.)])\s+(.+)$', linea)
        if m:
            nivel = min(len(m.group(1)) // 2, 5)
            marca = '•' if m.group(2) in '•●▪◦*-\x95' else m.group(2)
            contenido = formatear_linea_texto(m.group(3))
            # Usar entidad HTML para bullets en vez del carácter directo (evita cuadrados en servidores sin fuentes)
            marca_html = '&bull;' if marca == '•' else escape(marca)
            salida.append(f'<p class="doc-list-item" style="margin-left:{18 + nivel*14}pt; text-indent:-12pt; text-align:left; margin-bottom:4pt;">{marca_html}&nbsp; {contenido}</p>')
        else:
            contenido = formatear_linea_texto(linea_strip)
            salida.append(f'<p style="margin-bottom:6pt;">{contenido}</p>')

        i += 1

    return mark_safe('\n'.join(salida))
