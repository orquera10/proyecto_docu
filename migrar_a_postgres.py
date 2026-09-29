"""
Migración SQLite → PostgreSQL
=============================
Este script exporta todos los datos de la base SQLite local
y los importa en la base PostgreSQL configurada en el .env.

Uso: python migrar_a_postgres.py
"""
import os
import sys
import subprocess
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DUMP_FILE = BASE_DIR / 'datos_sqlite_backup.json'

def run(cmd, env=None):
    """Ejecutar un comando y mostrar la salida."""
    print(f"\n{'='*60}")
    print(f"▶ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    print('='*60)
    result = subprocess.run(
        cmd, cwd=str(BASE_DIR), env=env,
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode

def main():
    print("\n🔄 MIGRACIÓN SQLite → PostgreSQL")
    print("="*60)

    # Verificar que existe la base SQLite
    sqlite_path = BASE_DIR / 'db.sqlite3'
    if not sqlite_path.exists():
        print("❌ No se encontró db.sqlite3")
        sys.exit(1)
    print(f"✅ SQLite encontrada: {sqlite_path} ({sqlite_path.stat().st_size / 1024:.0f} KB)")

    # ----------------------------------------------------------
    # PASO 1: Exportar datos desde SQLite
    # ----------------------------------------------------------
    print("\n📦 PASO 1: Exportando datos desde SQLite...")

    # Crear un entorno sin las variables de PostgreSQL para forzar SQLite
    env_sqlite = os.environ.copy()
    # Eliminar variables que harían que settings.py use PostgreSQL
    for var in ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT',
                'DATABASE_URL', 'POSTGRES_DB', 'POSTGRES_HOST',
                'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_PORT']:
        env_sqlite.pop(var, None)
    env_sqlite['DEBUG'] = 'True'
    env_sqlite['PYTHONIOENCODING'] = 'utf-8'

    ret = run([
        sys.executable, 'manage.py', 'dumpdata',
        '--natural-foreign', '--natural-primary',
        '--exclude=contenttypes',
        '--exclude=auth.permission',
        '--indent', '2',
        '-o', str(DUMP_FILE)
    ], env=env_sqlite)

    if ret != 0:
        print("❌ Error al exportar datos de SQLite")
        sys.exit(1)

    # Verificar el dump
    size = DUMP_FILE.stat().st_size
    # Intentar utf-8 primero, luego cp1252 y finalmente latin-1
    for enc in ['utf-8', 'cp1252', 'latin-1']:
        try:
            with open(DUMP_FILE, 'r', encoding=enc) as f:
                data = json.load(f)
            # Si se leyó con encoding distinto a utf-8, reescribir como utf-8
            if enc != 'utf-8':
                with open(DUMP_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"   (Archivo re-codificado de {enc} a UTF-8)")
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    else:
        print("❌ No se pudo leer el archivo de backup")
        sys.exit(1)
    print(f"✅ Exportados {len(data)} objetos ({size / 1024:.0f} KB)")

    # Resumen por modelo
    modelos = {}
    for obj in data:
        modelo = obj.get('model', 'desconocido')
        modelos[modelo] = modelos.get(modelo, 0) + 1
    print("\n📊 Resumen de datos exportados:")
    for modelo, cantidad in sorted(modelos.items()):
        print(f"   • {modelo}: {cantidad}")

    # ----------------------------------------------------------
    # PASO 2: Crear tablas en PostgreSQL
    # ----------------------------------------------------------
    print("\n🏗️  PASO 2: Creando tablas en PostgreSQL...")

    # Cargar variables del .env manualmente para PostgreSQL
    env_pg = os.environ.copy()
    env_file = BASE_DIR / '.env'
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    env_pg[key.strip()] = value.strip()

    ret = run([sys.executable, 'manage.py', 'migrate', '--run-syncdb'], env=env_pg)
    if ret != 0:
        print("❌ Error al migrar PostgreSQL. Verificá la conexión en el .env")
        sys.exit(1)
    print("✅ Tablas creadas en PostgreSQL")

    # ----------------------------------------------------------
    # PASO 3: Importar datos en PostgreSQL
    # ----------------------------------------------------------
    print("\n📥 PASO 3: Importando datos en PostgreSQL...")

    ret = run([
        sys.executable, 'manage.py', 'loaddata', str(DUMP_FILE)
    ], env=env_pg)

    if ret != 0:
        print("❌ Error al importar datos. El archivo de backup se conserva:")
        print(f"   {DUMP_FILE}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("🎉 ¡MIGRACIÓN COMPLETADA!")
    print(f"{'='*60}")
    print(f"✅ {len(data)} objetos migrados de SQLite → PostgreSQL")
    print(f"📄 Backup conservado en: {DUMP_FILE}")
    print(f"\nPodés eliminar el backup cuando confirmes que todo funciona:")
    print(f"   del {DUMP_FILE}")

if __name__ == '__main__':
    main()
