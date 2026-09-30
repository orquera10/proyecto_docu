"""
Script para Exportar y Respaldar Elementos Multimedia de GestDoc / Docu IT.

Empaqueta toda la carpeta 'media/' (imágenes incrustadas, adjuntos, firmas, PDFs de notas recibidas)
en un archivo ZIP portátil, y realiza un diagnóstico de archivos referenciados en la Base de Datos.

Uso:
    python exportar_multimedia.py
"""

import os
import sys
import re
import zipfile
import django
from datetime import datetime
from pathlib import Path

# Asegurar encoding UTF-8 en consola Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Configurar entorno Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings
from documentos.models import Documento, Adjunto, NotaRecibida


def diagnosticar_y_exportar():
    media_root = Path(settings.MEDIA_ROOT)
    print("=" * 70)
    print(" [EXPORTADOR Y DIAGNOSTICO DE MULTIMEDIA - GESTDOC]")
    print("=" * 70)
    print(f"Directorio Media (MEDIA_ROOT): {media_root}")

    if not media_root.exists():
        print(f"[!] El directorio {media_root} no existe. Creándolo...")
        media_root.mkdir(parents=True, exist_ok=True)

    # 1. Diagnóstico de Base de Datos vs Archivos Físicos
    print("\nVerificando referencias en la Base de Datos...")

    referencias_totales = 0
    archivos_encontrados = 0
    archivos_faltantes = []

    # a) Adjuntos de Documentos
    adjuntos = Adjunto.objects.all()
    for adj in adjuntos:
        if adj.archivo:
            referencias_totales += 1
            ruta = media_root / adj.archivo.name
            if ruta.exists():
                archivos_encontrados += 1
            else:
                archivos_faltantes.append({
                    'tipo': 'Adjunto de Documento',
                    'origen': f"{adj.documento.tipo} {adj.documento.numero}",
                    'nombre_original': adj.nombre_original,
                    'ruta_esperada': str(adj.archivo.name)
                })

    # b) PDFs de Notas Recibidas
    notas_recibidas = NotaRecibida.objects.all()
    for nr in notas_recibidas:
        if nr.archivo_pdf:
            referencias_totales += 1
            ruta = media_root / nr.archivo_pdf.name
            if ruta.exists():
                archivos_encontrados += 1
            else:
                archivos_faltantes.append({
                    'tipo': 'PDF Nota Recibida',
                    'origen': f"Nota Recibida {nr.numero_registro}",
                    'nombre_original': nr.archivo_pdf.name,
                    'ruta_esperada': str(nr.archivo_pdf.name)
                })

    # c) Imágenes incrustadas en el cuerpo Markdown de los Documentos
    patron_img1 = re.compile(r'\[IMAGEN:\s*([^|\]]+)(?:\s*\|\s*([^\]]+))?\]', re.IGNORECASE)
    patron_img2 = re.compile(r'!\[(.*?)\]\((.*?)\)')
    
    media_url = getattr(settings, 'MEDIA_URL', '/media/')

    for doc in Documento.objects.all():
        cuerpo = doc.cuerpo or ''
        # Buscar coincidencias de [IMAGEN: ...]
        imgs = patron_img1.findall(cuerpo)
        for img_url, caption in imgs:
            url_limpia = img_url.strip().strip('\'"')
            if url_limpia.startswith(media_url):
                rel_path = url_limpia[len(media_url):].lstrip('/')
            else:
                rel_path = url_limpia.lstrip('/')
            
            referencias_totales += 1
            ruta = media_root / rel_path
            if ruta.exists():
                archivos_encontrados += 1
            else:
                archivos_faltantes.append({
                    'tipo': 'Imagen Incrustada',
                    'origen': f"{doc.tipo} {doc.numero}",
                    'nombre_original': caption or Path(rel_path).name,
                    'ruta_esperada': rel_path
                })

    print(f" -> Referencias en BD: {referencias_totales}")
    print(f" -> Archivos presentes en disco: {archivos_encontrados}")
    if archivos_faltantes:
        print(f" [!] Archivos faltantes en disco ({len(archivos_faltantes)}):")
        for f in archivos_faltantes:
            print(f"     * [{f['tipo']}] {f['origen']}: {f['ruta_esperada']} ({f['nombre_original']})")
    else:
        print(" [OK] Todos los archivos referenciados en la base de datos estan presentes en disco.")

    # 2. Empaquetado ZIP de todo MEDIA_ROOT
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta_respaldos = BASE_DIR / 'respaldos'
    carpeta_respaldos.mkdir(exist_ok=True)
    
    nombre_zip = f"respaldo_multimedia_{timestamp}.zip"
    ruta_zip = carpeta_respaldos / nombre_zip

    print(f"\nCreando archivo ZIP comprimido...")
    total_archivos_zip = 0
    total_bytes = 0

    with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(media_root):
            for file in files:
                archivo_path = Path(root) / file
                # Ruta relativa dentro del ZIP (empezando con 'media/...')
                rel_path = archivo_path.relative_to(media_root)
                arcname = Path('media') / rel_path
                zipf.write(archivo_path, arcname)
                total_archivos_zip += 1
                total_bytes += archivo_path.stat().st_size

    tamano_mb = total_bytes / (1024 * 1024)
    print(f"[OK] Respaldo generado con exito:")
    print(f"     Archivo: {ruta_zip}")
    print(f"     Archivos incluidos: {total_archivos_zip}")
    print(f"     Tamano total: {tamano_mb:.2f} MB")
    print("\n" + "=" * 70)
    print("INSTRUCCIONES PARA IMPORTAR EN DOCKER / SERVIDOR PRODUCCION:")
    print("=" * 70)
    print("1. Copiar el archivo ZIP al servidor:")
    print(f"   scp respaldos/{nombre_zip} usuario@servidor:/ruta/destino/")
    print("\n2. Extraer los archivos dentro del volumen de media:")
    print(f"   unzip {nombre_zip} -d /mnt/datos/docu/")
    print("   (Esto colocara los archivos directamente en /mnt/datos/docu/media)")
    print("\n3. Si usa Docker directamente:")
    print("   docker cp media/. docu_app:/app/media/")
    print("=" * 70)


if __name__ == '__main__':
    diagnosticar_y_exportar()
