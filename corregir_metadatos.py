"""Repara únicamente registros identificados por el asunto original.

Ejecutar sin argumentos para revisar; --aplicar guarda respaldo y aplica cambios.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.conf import settings
from django.db import transaction
from documentos.models import Documento
from documentos.importacion import extraer_asunto, extraer_destinatario
from importar_documentos import EXCLUIR, clasificar, leer_texto_docx


def clave(texto):
    return re.sub(r'[^\w]', '', texto.lower()).replace('_', '')


def ejecutar(aplicar=False):
    fuentes = {}
    for ruta in (settings.BASE_DIR / 'para_analizar').glob('*.docx'):
        if ruta.name not in EXCLUIR:
            fuentes.setdefault((clasificar(ruta.name), clave(ruta.stem)), []).append(ruta)
            nueva = (clasificar(ruta.name), clave(extraer_asunto(leer_texto_docx(str(ruta)), ruta.name)))
            if ruta not in fuentes.get(nueva, []):
                fuentes.setdefault(nueva, []).append(ruta)
    cambios, pendientes = [], []
    for doc in Documento.objects.all():
        candidatos = fuentes.get((doc.tipo, clave(doc.asunto)), [])
        if len(candidatos) != 1:
            pendientes.append({'numero': doc.numero, 'motivo': 'Sin coincidencia única con nombre original'})
            continue
        ruta = candidatos[0]
        texto = leer_texto_docx(str(ruta))
        if not texto:
            pendientes.append({'numero': doc.numero, 'motivo': 'No se pudo leer el original'})
            continue
        asunto = extraer_asunto(texto, ruta.name)
        destinatario = extraer_destinatario(texto)
        if not destinatario:
            pendientes.append({'numero': doc.numero, 'archivo': ruta.name, 'motivo': 'El original no identifica un destinatario explícito'})
        # Conservar correcciones manuales: comparar con la extracción histórica.
        lineas = texto.split('\n')
        anterior = None
        for i, linea in enumerate(lineas[:20]):
            if re.search(r'^(AL SR\.|A LA SRA\.|AL DR\.|A LA DRA\.|AL LIC\.|A LA LIC\.|PARA:)|(COORDINADORA?|DIRECTOR[AO]?|SECRETARI[OA]?)\s+DE\s+', linea, re.I):
                anterior = re.split(r'SU DESPACHO|Me dirijo', ' '.join(lineas[i:i+3]).strip(), flags=re.I)[0].strip()[:150]
                break
        if anterior is None:
            anterior = lineas[1][:150] if len(lineas) > 1 else 'Área destinataria'
        campos = {}
        if doc.tipo == 'NOTA':
            # Algunos cuerpos importados empiezan con una copia del encabezado.
            cuerpo_lineas = doc.cuerpo.splitlines()
            if cuerpo_lineas and re.match(r'^San Salvador de Jujuy', cuerpo_lineas[0], re.I):
                for i, linea in enumerate(cuerpo_lineas[:12]):
                    if re.match(r'^Su\s*/?\s*Despacho\s*:', linea, re.I):
                        campos['cuerpo'] = '\n'.join(cuerpo_lineas[i+1:]).strip()
                        break
        if asunto != doc.asunto and len(asunto) <= 255:
            campos['asunto'] = asunto
        if doc.destinatario == anterior and destinatario != doc.destinatario:
            campos['destinatario'] = destinatario
        elif destinatario != doc.destinatario:
            pendientes.append({'numero': doc.numero, 'motivo': 'Destinatario editado: se conserva para revisión'})
        if campos:
            cambios.append({'id': doc.pk, 'numero': doc.numero, 'archivo': ruta.name,
                            'antes': {k: getattr(doc, k) for k in campos}, 'despues': campos})
    carpeta = settings.BASE_DIR / 'respaldos'
    carpeta.mkdir(exist_ok=True)
    sello = datetime.now().strftime('%Y%m%d-%H%M%S')
    reporte = carpeta / f'metadatos-{sello}.json'
    reporte.write_text(json.dumps({'aplicado': aplicar, 'cambios': cambios, 'pendientes': pendientes}, ensure_ascii=False, indent=2), encoding='utf-8')
    if aplicar:
        with sqlite3.connect(str(settings.DATABASES['default']['NAME'])) as origen:
            with sqlite3.connect(str(carpeta / f'db-{sello}.sqlite3')) as destino:
                origen.backup(destino)
        with transaction.atomic():
            for cambio in cambios:
                Documento.objects.filter(pk=cambio['id']).update(**cambio['despues'])
    print(f'{len(cambios)} documentos con cambios; {len(pendientes)} observaciones. Reporte: {reporte}')


if __name__ == '__main__':
    ejecutar('--aplicar' in sys.argv)
