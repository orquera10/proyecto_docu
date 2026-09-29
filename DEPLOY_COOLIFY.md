# 🚀 Guía de Despliegue en Coolify – Docu IT

Esta guía explica paso a paso cómo desplegar la plataforma **Docu IT** en **Coolify** con:
- Conexión a base de datos **PostgreSQL**.
- Almacenamiento persistente de PDFs y archivos escaneados en una **carpeta compartida de Windows (SMB/CIFS)** o volumen Docker.
- Recolección automática de archivos estáticos (`WhiteNoise`).
- Servidor de producción `Gunicorn` y certificados SSL automáticos vía Traefik.

---

## 📁 Archivos de Configuración Incluidos

1. **`Dockerfile`**: Imagen optimizada (`python:3.12-slim`) con librerías C de sistema para OpenCV headless, Pillow, xhtml2pdf y PostgreSQL (`libpq-dev`).
2. **`entrypoint.sh`**: Script de arranque que espera activamente la disponibilidad de PostgreSQL, corre migraciones (`migrate`), recolecta estáticos (`collectstatic`), crea superusuario inicial y arranca Gunicorn.
3. **`docker-compose.yml`**: Orquestación lista para Coolify con soporte de variables de PostgreSQL y definición de volúmenes (estándar y CIFS/SMB).
4. **`.env.example`**: Catálogo completo de variables de entorno.
5. **`.dockerignore`**: Optimiza el build excluyendo cachés y entornos virtuales locales.

---

## 🐘 1. Configuración de PostgreSQL

Docu IT soporta PostgreSQL tanto si está alojado en el mismo Coolify como en un servidor externo (o red local). Admite **dos modalidades**:

### Modalidad A: Variables Individuales (Recomendado para servidores externos o VMs dedicadas)
En Coolify, en la pestaña **Environment Variables**:
```ini
DB_NAME=docu_db
DB_USER=docu_user
DB_PASSWORD=tu_password_seguro
DB_HOST=192.168.1.50
DB_PORT=5432
```

### Modalidad B: `DATABASE_URL` única (Ideal al crear una base PostgreSQL en Coolify)
Si creás una base de datos PostgreSQL en Coolify dentro del mismo proyecto, Coolify suele generar una variable de conexión:
```ini
DATABASE_URL=postgresql://docu_user:tu_password_seguro@docu-postgres:5432/docu_db
```

> [!NOTE]
> `config/settings.py` detecta automáticamente si existe `DATABASE_URL` o el conjunto `DB_NAME`/`DB_HOST`. Si no se define ninguno, recurre a SQLite de forma segura.

---

## 🗄️ 2. ¿Se puede usar una Carpeta Compartida de Windows para los PDFs?

**¡Sí, totalmente!** Es una práctica muy común en empresas para que los documentos generados y escaneados se guarden directamente en un file server Windows existente (`\\192.168.X.X\Compartida`).

Para conectar la carpeta compartida de Windows con el contenedor de Coolify (`/app/media`), existen dos métodos:

---

### Método 1 (Recomendado): Montaje en el Host Linux de Coolify (Máxima estabilidad)

Este método es el más robusto, ya que Linux gestiona la reconexión de red de forma transparente mediante el kernel y Coolify simplemente mapea una ruta local al contenedor.

#### Paso A: En el servidor Linux donde corre Coolify
Instalá la utilidad de soporte CIFS/SMB:
```bash
sudo apt update && sudo apt install -y cifs-utils
```

Creá la carpeta donde se montará el recurso:
```bash
sudo mkdir -p /mnt/docu_media
```

Creá un archivo seguro con las credenciales de Windows:
```bash
sudo nano /etc/win-credentials
```
Agregá el usuario y contraseña de Windows (y dominio si aplica):
```ini
username=usuario_windows
password=contraseña_windows
domain=WORKGROUP
```
Asegurá los permisos del archivo de credenciales:
```bash
sudo chmod 600 /etc/win-credentials
```

#### Paso B: Configurar el montaje automático en `/etc/fstab`
Editá `/etc/fstab`:
```bash
sudo nano /etc/fstab
```
Agregá al final la siguiente línea (reemplazando `192.168.1.200/DocumentosDocu` por la IP y recurso compartido de tu Windows):
```text
//192.168.1.200/DocumentosDocu /mnt/docu_media cifs credentials=/etc/win-credentials,iocharset=utf8,file_mode=0777,dir_mode=0777,noperm,_netdev 0 0
```
Probá el montaje sin reiniciar:
```bash
sudo mount -a
```
Verificá que se montó correctamente ejecutando `ls -la /mnt/docu_media`.

#### Paso C: Configurar el Almacenamiento en Coolify
1. En el panel de Coolify, abrí tu aplicación **Docu IT**.
2. Andá a la pestaña **Storages** (o **Persistent Storage**).
3. Hacé clic en **+ Add Storage**:
   - **Type**: `Bind Mount` (o Host Path)
   - **Host Path**: `/mnt/docu_media`
   - **Destination Path**: `/app/media`
4. Guardá los cambios y desplegá.

---

### Método 2: Montaje Directo mediante Volumen CIFS en Docker Compose

Si preferís que Docker gestione el montaje de Windows directamente sin tocar `/etc/fstab`:

1. Asegurate de tener `cifs-utils` instalado en el host (`sudo apt install -y cifs-utils`).
2. En `docker-compose.yml`, utilizá la configuración de volumen CIFS comentada:
   ```yaml
   volumes:
     docu_media:
       driver: local
       driver_opts:
         type: cifs
         o: "username=${SMB_USER},password=${SMB_PASS},domain=${SMB_DOMAIN:-},vers=3.0,file_mode=0777,dir_mode=0777"
         device: "//${SMB_SERVER_IP}/${SMB_SHARE_NAME}"
   ```
3. En las **Environment Variables** de Coolify definí:
   ```ini
   SMB_SERVER_IP=192.168.1.200
   SMB_SHARE_NAME=DocumentosDocu
   SMB_USER=usuario_windows
   SMB_PASS=contraseña_windows
   ```

---

## 🚀 3. Paso a Paso para Desplegar en Coolify

### Paso 1: Subir cambios a tu repositorio Git
```bash
git add .
git commit -m "Soporte PostgreSQL y configuración de volúmenes persistentes/SMB para Coolify"
git push origin main
```

### Paso 2: Crear el Recurso en Coolify
1. En Coolify: **+ New Resource** -> **Application** -> Elegí tu repositorio Git.
2. **Build Pack**: Seleccioná **Dockerfile** (o **Docker Compose** si preferís usar el compose).
3. **Ports Exposes**: Colocá `8000`.
4. **Domains**: Tu dominio o subdominio con HTTPS (ej. `https://docu.tuempresa.com`).

### Paso 3: Cargar las Variables de Entorno
En la pestaña **Environment Variables** de Coolify, copiá y ajustá las variables de `.env.example`:

| Variable | Valor de Ejemplo | Descripción |
| :--- | :--- | :--- |
| `SECRET_KEY` | *(cadena aleatoria de 50+ caracteres)* | Clave criptográfica obligatoria. |
| `DEBUG` | `False` | Producción. |
| `ALLOWED_HOSTS` | `docu.tuempresa.com,localhost` | Hosts permitidos. |
| `CSRF_TRUSTED_ORIGINS` | `https://docu.tuempresa.com` | **Obligatorio para formularios y login en HTTPS**. |
| `DB_NAME` | `docu_db` | Nombre de la base PostgreSQL. |
| `DB_USER` | `docu_user` | Usuario de PostgreSQL. |
| `DB_PASSWORD` | `tu_password_seguro` | Contraseña de PostgreSQL. |
| `DB_HOST` | `192.168.1.50` | IP o hostname del servidor PostgreSQL. |
| `DB_PORT` | `5432` | Puerto de PostgreSQL. |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Usuario administrador inicial. |
| `DJANGO_SUPERUSER_PASSWORD` | `tu_password_admin` | Contraseña del admin inicial. |
| `DJANGO_SUPERUSER_EMAIL` | `admin@tuempresa.com` | Email del admin inicial. |

### Paso 4: Desplegar
Hacé clic en **Deploy**. Coolify compilará la imagen, conectará a PostgreSQL, ejecutará las migraciones automáticamente, creará el superusuario y levantará la aplicación protegida con SSL.
