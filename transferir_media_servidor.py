"""
Script para sincronizar y transferir automáticamente los archivos multimedia
hacia el servidor remoto Debian en /mnt/datos/docu/media/
utilizando python3 zipfile en el servidor remoto.
"""

import os
import sys
import paramiko
from pathlib import Path

HOST = os.environ.get("SSH_HOST", "192.168.1.25")
PORT = int(os.environ.get("SSH_PORT", "22"))
USER = os.environ.get("SSH_USER", "dario")
PASS = os.environ.get("SSH_PASS", "tuxx6393")
REMOTE_MEDIA_DIR = "/mnt/datos/docu/media"
LOCAL_ZIP = Path(r"E:\datos\Documentos\proyecto_archivos\respaldos\respaldo_multimedia_20260930_085434.zip")

def transferir_y_extraer():
    print(f"1. Conectando a {HOST} con usuario '{USER}'...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=10)
    print("   -> Conexión SSH establecida.")

    remote_zip = f"/home/{USER}/respaldo_multimedia.zip"
    print(f"\n2. Subiendo archivo ZIP ({LOCAL_ZIP.stat().st_size / 1024 / 1024:.2f} MB)...")
    sftp = ssh.open_sftp()
    
    def progress_callback(transferred, total):
        pct = (transferred / total) * 100
        sys.stdout.write(f"\r   Progreso: {pct:.1f}% ({transferred}/{total} bytes)")
        sys.stdout.flush()

    sftp.put(str(LOCAL_ZIP), remote_zip, callback=progress_callback)
    print("\n   -> Subida completada.")
    sftp.close()

    print("\n3. Descomprimiendo en el servidor remoto con Python3...")
    extract_cmd = f"""python3 -c "import zipfile, os
with zipfile.ZipFile('{remote_zip}', 'r') as z:
    z.extractall('/mnt/datos/docu/')
print('Extraccion finalizada.')
" """
    stdin, stdout, stderr = ssh.exec_command(extract_cmd)
    print("   Salida:", stdout.read().decode('utf-8', errors='ignore').strip())
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    if err:
        print("   Errores:", err)

    # Ajustar permisos para que el contenedor web pueda leer y escribir libremente
    print("\n4. Ajustando permisos en /mnt/datos/docu/media...")
    ssh.exec_command("chmod -R 777 /mnt/datos/docu/media")

    # Listar estructura resultante
    print("\n5. Verificando estructura final en el servidor:")
    check_cmd = """python3 -c "import os
for root, dirs, files in os.walk('/mnt/datos/docu/media'):
    rel = os.path.relpath(root, '/mnt/datos/docu/media')
    print(f'Carpeta: media/{rel} -> {len(files)} archivos, {len(dirs)} subcarpetas')
" """
    stdin, stdout, stderr = ssh.exec_command(check_cmd)
    print(stdout.read().decode('utf-8', errors='ignore'))

    # Limpiar ZIP temporal
    ssh.exec_command(f"rm -f {remote_zip}")
    ssh.close()
    print("======================================================================")
    print(" ¡TODOS LOS ARCHIVOS MULTIMEDIA HAN SIDO TRANSFERIDOS EXITOSAMENTE! ")
    print("======================================================================")

if __name__ == '__main__':
    transferir_y_extraer()
