# ==========================================
# Docu IT - Dockerfile para Producción / Coolify
# ==========================================
FROM python:3.12-slim

# Evitar prompts interactivos y buffers de Python
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Instalar dependencias del sistema operativo requeridas para:
# - OpenCV headless y Pillow: libglib2.0-0, libsm6, libxext6, libxrender-dev, libgomp1
# - ReportLab / xhtml2pdf: librerías de fuentes y renderizado
# - PostgreSQL: libpq-dev
# - Herramientas de red y build: curl, build-essential
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY . /app/

# Crear directorios para archivos estáticos, media subidos y base de datos persistente
RUN mkdir -p /app/staticfiles /app/media /app/data && \
    chmod +x /app/entrypoint.sh

# Exponer el puerto de la aplicación (8000)
EXPOSE 8000

# Script de arranque (migraciones, collectstatic, gunicorn)
ENTRYPOINT ["/app/entrypoint.sh"]
