#!/bin/sh
set -e

echo "=========================================="
echo "==> Iniciando Docu IT (Gestión Documental)..."
echo "=========================================="

# Esperar a la base de datos si se configuró PostgreSQL
if [ -n "$DATABASE_URL" ] || [ -n "$POSTGRES_HOST" ] || [ -n "$DB_HOST" ]; then
    echo "==> Esperando conexión con PostgreSQL..."
    python - <<END
import os, time, sys, urllib.parse, socket
db_url = os.environ.get('DATABASE_URL')
host = os.environ.get('DB_HOST') or os.environ.get('POSTGRES_HOST', '')
port = int(os.environ.get('DB_PORT') or os.environ.get('POSTGRES_PORT', 5432))
if db_url:
    p = urllib.parse.urlparse(db_url)
    host = p.hostname or 'localhost'
    port = p.port or 5432
if host:
    for i in range(30):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((host, port))
            s.close()
            print(f"Base de datos conectada en {host}:{port}")
            sys.exit(0)
        except Exception:
            time.sleep(1)
    print(f"No se pudo conectar a la base de datos en {host}:{port} tras 30 segundos.")
    sys.exit(1)
END
fi

# Crear directorio para SQLite si está en una ruta personalizada
if [ -n "$SQLITE_DB_PATH" ]; then
    mkdir -p "$(dirname "$SQLITE_DB_PATH")"
fi

# Ejecutar migraciones
echo "==> Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

# Recolectar archivos estáticos para WhiteNoise
echo "==> Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# Crear superusuario automático si se definieron variables de entorno
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "==> Verificando superusuario inicial..."
    python manage.py shell -c "
from django.contrib.auth.models import User
import os
username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@docu.local')
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f'==> Superusuario \"{username}\" creado exitosamente.')
else:
    print(f'==> Superusuario \"{username}\" ya existe.')
"
fi

echo "==> Arrancando servidor de producción Gunicorn en 0.0.0.0:8000..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -
