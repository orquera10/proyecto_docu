"""Recupera listas/tablas sin reemplazar cuerpos editados. --aplicar para guardar."""
import json
import sqlite3
import sys
from datetime import datetime
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.conf import settings
from django.db import transaction
from documentos.models import Documento
from documentos.formato import leer_docx_con_listas
from importar_documentos import leer_texto_docx, extraer_cuerpo_limpio


def ejecutar(aplicar=False):
    fuentes = {}
    # Los reportes anteriores conservan el vínculo exacto con el original.
    for reporte in sorted((settings.BASE_DIR / 'respaldos').glob('metadatos-*.json')):
        datos = json.loads(reporte.read_text(encoding='utf-8'))
        if datos.get('aplicado'):
            for cambio in datos['cambios']:
                fuentes[cambio['id']] = cambio['archivo']
    cambios, pendientes = [], []
    for doc in Documento.objects.exclude(tipo='ACTA'):
        nombre = fuentes.get(doc.pk)
        if not nombre:
            pendientes.append(doc.numero)
            continue
        ruta = settings.BASE_DIR / 'para_analizar' / nombre
        antiguo = extraer_cuerpo_limpio(leer_texto_docx(str(ruta)), doc.tipo)
        nuevo = extraer_cuerpo_limpio(leer_docx_con_listas(ruta), doc.tipo)
        if doc.cuerpo == nuevo:
            continue
        if doc.cuerpo not in (antiguo, antiguo[:3000]):
            pendientes.append(doc.numero)
            continue
        cambios.append({'id': doc.pk, 'numero': doc.numero, 'archivo': nombre,
                        'antes': doc.cuerpo, 'despues': nuevo})
    sello = datetime.now().strftime('%Y%m%d-%H%M%S')
    carpeta = settings.BASE_DIR / 'respaldos'
    if aplicar:
        with sqlite3.connect(str(settings.DATABASES['default']['NAME'])) as src:
            with sqlite3.connect(str(carpeta / f'db-listas-{sello}.sqlite3')) as dst:
                src.backup(dst)
        with transaction.atomic():
            for cambio in cambios:
                Documento.objects.filter(pk=cambio['id']).update(cuerpo=cambio['despues'])
    (carpeta / f'listas-{sello}.json').write_text(json.dumps({'aplicado': aplicar, 'cambios': cambios, 'pendientes': pendientes}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(cambios)} cuerpos recuperados; {len(pendientes)} sin modificar por diferencias con el original: {pendientes}')


if __name__ == '__main__':
    ejecutar('--aplicar' in sys.argv)
