import io
import cv2
import numpy as np
from PIL import Image, ImageOps
from django.core.files.base import ContentFile

# Dimensiones A4 estándar en píxeles a ~150 DPI (calidad nítida y peso optimizado)
A4_WIDTH = 1240
A4_HEIGHT = 1754


def remover_marco_captura(img):
    """
    Si la imagen proviene de una captura de pantalla del móvil,
    detecta y recorta franjas negras o gris oscuro en los bordes exteriores.
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = gray > 45
    coords = np.argwhere(mask)
    if len(coords) > 0:
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1
        # Solo recortar si hay una franja exterior notable (> 2.5% del ancho o alto)
        if x0 > w * 0.025 or y0 > h * 0.025 or (w - x1) > w * 0.025 or (h - y1) > h * 0.025:
            return img[y0:y1, x0:x1]
    return img


def ordenar_puntos(pts):
    """
    Ordena 4 puntos en orden: Top-Left, Top-Right, Bottom-Right, Bottom-Left.
    """
    pts = pts.reshape(4, 2).astype('float32')
    s = pts.sum(axis=1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype='float32')


def detectar_y_recortar_documento(img):
    """
    Detecta los 4 vértices de una hoja de papel en la fotografía (sobre mesas, escritorios, etc.),
    rechaza bordes o marcos de la cámara/pantalla, y aplica transformación de perspectiva
    (homografía / deskew) con margen de seguridad interior para eliminar por completo el fondo.
    """
    img_trabajo = remover_marco_captura(img)
    h_orig, w_orig = img_trabajo.shape[:2]

    # Trabajar sobre resolución estandarizada para estabilidad de filtros y rapidez
    max_dim = 1200
    scale = 1.0
    if max(h_orig, w_orig) > max_dim:
        scale = max_dim / float(max(h_orig, w_orig))
        proc_w, proc_h = int(w_orig * scale), int(h_orig * scale)
        proc_img = cv2.resize(img_trabajo, (proc_w, proc_h), interpolation=cv2.INTER_AREA)
    else:
        proc_img = img_trabajo
        proc_w, proc_h = w_orig, h_orig

    img_area = proc_w * proc_h
    gray = cv2.cvtColor(proc_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 1. Estrategia Canny con dilación
    edges = cv2.Canny(blurred, 35, 120)
    dilated_canny = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7)), iterations=2)

    # 2. Estrategia Otsu con clausura morfológica para borrar texto interno
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
    closed = cv2.morphologyEx(blurred, cv2.MORPH_CLOSE, k_close)
    _, otsu = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 3. Estrategia HSV para fotos sobre escritorios de madera/color
    hsv = cv2.cvtColor(proc_img, cv2.COLOR_BGR2HSV)
    s_ch = hsv[:, :, 1]
    v_ch = hsv[:, :, 2]
    hsv_mask = ((s_ch < 80) & (v_ch > 65)).astype(np.uint8) * 255
    hsv_clean = cv2.morphologyEx(hsv_mask, cv2.MORPH_CLOSE, k_close)

    binary_maps = [
        ('Canny', dilated_canny),
        ('Otsu', otsu),
        ('HSV', hsv_clean)
    ]

    valid_quads = []

    for name, bmap in binary_maps:
        cnts, _ = cv2.findContours(bmap, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        for c in cnts:
            area = cv2.contourArea(c)
            # El documento debe ser al menos el 18% del área de la imagen
            if area < (img_area * 0.18):
                continue

            x, y, bw, bh = cv2.boundingRect(c)
            ar = max(bw, bh) / float(max(1, min(bw, bh)))
            if ar > 2.4:  # Descartar formas demasiado alargadas
                continue

            hull = cv2.convexHull(c)
            peri = cv2.arcLength(hull, True)

            quad = None
            # Probar varios niveles de aproximación poligonal
            for eps in np.linspace(0.015, 0.07, 12):
                approx = cv2.approxPolyDP(hull, eps * peri, True)
                if len(approx) == 4 and cv2.isContourConvex(approx):
                    quad = approx
                    break

            # Si no cerró en 4 puntos exactos pero es una masa grande, usar rectángulo de área mínima
            if quad is None and area > (img_area * 0.28):
                rect_min = cv2.minAreaRect(hull)
                box = cv2.boxPoints(rect_min)
                quad = np.int32(box).reshape(4, 1, 2)

            if quad is not None:
                pct = area / float(img_area)
                # Detectar si es el marco o captura externa completa (ocupa >86% y toca los bordes)
                is_frame = (pct > 0.86 and x <= (proc_w * 0.05) and y <= (proc_h * 0.05) and
                            (x + bw) >= (proc_w * 0.95) and (y + bh) >= (proc_h * 0.95))

                # Medir brillo interior
                mask_quad = np.zeros((proc_h, proc_w), dtype=np.uint8)
                cv2.drawContours(mask_quad, [quad], -1, 255, -1)
                mean_br = cv2.mean(gray, mask=mask_quad)[0]

                # Similitud a formato A4 (~1.41)
                ar_diff = abs(ar - 1.41)
                ar_weight = max(0.6, 1.0 - (ar_diff * 0.2))

                # Penalización por tocar bordes exteriores
                touch_edges = (1 if x <= 3 else 0) + (1 if y <= 3 else 0) + \
                              (1 if (x + bw) >= proc_w - 3 else 0) + (1 if (y + bh) >= proc_h - 3 else 0)
                touch_mult = 1.0 - (touch_edges * 0.15)

                score = area * (mean_br / 128.0) * ar_weight * touch_mult

                valid_quads.append({
                    'quad': quad.reshape(4, 2) / scale,
                    'area': area,
                    'pct': pct,
                    'is_frame': is_frame,
                    'score': score
                })

    if not valid_quads:
        return img_trabajo

    # Priorizar candidatos que NO sean el marco general
    non_frames = [q for q in valid_quads if not q['is_frame']]
    if non_frames:
        non_frames.sort(key=lambda x: x['score'], reverse=True)
        chosen = non_frames[0]
    else:
        valid_quads.sort(key=lambda x: x['score'], reverse=True)
        chosen = valid_quads[0]
        # Si el único elegido es el marco completo (ocupa más del 90%), no distorsionar
        if chosen['pct'] > 0.90:
            return img_trabajo

    raw_pts = chosen['quad'].astype('float32')
    ordered = ordenar_puntos(raw_pts)

    # Inset de seguridad hacia el centro (1.2%) para eliminar cualquier vestigio de borde/mesa
    center = ordered.mean(axis=0)
    rect = ordered + (center - ordered) * 0.012

    tl, tr, br, bl = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    if maxWidth > 100 and maxHeight > 100:
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype='float32')
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img_trabajo, M, (maxWidth, maxHeight))
        return warped

    return img_trabajo


def mejorar_contraste_camscanner(img, modo='magic_color'):
    """
    Aplica filtros de realce y nivelación de sombras estilo CamScanner:
    - 'magic_color': Fondo blanco puro, texto negro nítido y preservación de logos/firmas en color.
    - 'escala_grises': Escala de grises con iluminación normalizada.
    - 'blanco_negro': Alto contraste binario (B/N puro).
    - 'original': Conserva la imagen original sin alteración tonal.
    """
    if modo == 'original':
        return img

    if modo == 'magic_color':
        planes = cv2.split(img)
        out_planes = []
        for p in planes:
            dil = cv2.dilate(p, np.ones((7, 7), np.uint8))
            bg = cv2.medianBlur(dil, 21)
            diff = cv2.absdiff(p, bg)
            norm = 255 - diff
            low = np.percentile(norm, 1)
            high = np.percentile(norm, 99)
            if high > low:
                stretched = np.clip((norm - low) * (255.0 / (high - low)), 0, 255).astype(np.uint8)
            else:
                stretched = norm
            out_planes.append(stretched)
        res = cv2.merge(out_planes)
        # Máscara de enfoque suave para letras nítidas
        blur = cv2.GaussianBlur(res, (0, 0), 1.5)
        enhanced = cv2.addWeighted(res, 1.3, blur, -0.3, 0)
        return enhanced

    elif modo == 'escala_grises':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        dil = cv2.dilate(gray, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dil, 21)
        diff = cv2.absdiff(gray, bg)
        norm = 255 - diff
        low = np.percentile(norm, 1)
        high = np.percentile(norm, 99)
        if high > low:
            stretched = np.clip((norm - low) * (255.0 / (high - low)), 0, 255).astype(np.uint8)
        else:
            stretched = norm
        blur = cv2.GaussianBlur(stretched, (0, 0), 1.5)
        sharp = cv2.addWeighted(stretched, 1.3, blur, -0.3, 0)
        return cv2.cvtColor(sharp, cv2.COLOR_GRAY2BGR)

    elif modo == 'blanco_negro':
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        dil = cv2.dilate(gray, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dil, 21)
        diff = cv2.absdiff(gray, bg)
        norm = 255 - diff
        low = np.percentile(norm, 1)
        high = np.percentile(norm, 99)
        if high > low:
            stretched = np.clip((norm - low) * (255.0 / (high - low)), 0, 255).astype(np.uint8)
        else:
            stretched = norm
        thresh_val, _ = cv2.threshold(stretched, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, thresh = cv2.threshold(stretched, max(thresh_val - 12, 115), 255, cv2.THRESH_BINARY)
        return cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

    return img


def normalizar_imagen_a4(imagen_origen, filtro='magic_color', autocrop=True, max_w=A4_WIDTH, max_h=A4_HEIGHT):
    """
    Toma un archivo de imagen o un objeto PIL.Image:
    1. Corrige la orientación EXIF de la cámara móvil.
    2. Aplica detección y recorte de bordes de la página (autocrop) con OpenCV si está activo.
    3. Aplica realce de contraste tipo CamScanner ('magic_color', 'escala_grises', etc.).
    4. Lo encuadra en una hoja A4 limpia con fondo blanco.
    """
    if hasattr(imagen_origen, 'read'):
        imagen_origen.seek(0)
        img_pil = Image.open(imagen_origen)
    elif isinstance(imagen_origen, Image.Image):
        img_pil = imagen_origen
    else:
        img_pil = Image.open(imagen_origen)

    # Corregir orientación EXIF (típico de fotos de celular)
    try:
        img_pil = ImageOps.exif_transpose(img_pil)
    except Exception:
        pass

    # Convertir a RGB
    if img_pil.mode != 'RGB':
        img_pil = img_pil.convert('RGB')

    # Convertir PIL -> OpenCV BGR para procesamiento avanzado
    cv_img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    # 1. Detección de bordes y recorte de perspectiva (Deskew)
    if autocrop:
        try:
            cv_img = detectar_y_recortar_documento(cv_img)
        except Exception as e:
            print(f"Aviso en recorte automático: {e}")

    # 2. Realce de contraste tipo CamScanner
    if filtro and filtro != 'original':
        try:
            cv_img = mejorar_contraste_camscanner(cv_img, modo=filtro)
        except Exception as e:
            print(f"Aviso en realce de contraste: {e}")

    # Convertir OpenCV BGR -> PIL RGB
    cv_rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    img_final = Image.fromarray(cv_rgb)

    # Determinar orientación vertical u horizontal
    es_apaisada = img_final.width > img_final.height
    w_lienzo = max_h if es_apaisada else max_w
    h_lienzo = max_w if es_apaisada else max_h

    # Margen sutil de seguridad (15px)
    margen = 15
    max_contenido_w = w_lienzo - (margen * 2)
    max_contenido_h = h_lienzo - (margen * 2)

    # Redimensionar conservando proporción
    ratio = min(max_contenido_w / img_final.width, max_contenido_h / img_final.height)
    nuevo_w = max(1, int(img_final.width * ratio))
    nuevo_h = max(1, int(img_final.height * ratio))

    img_redim = img_final.resize((nuevo_w, nuevo_h), Image.Resampling.LANCZOS)

    # Crear lienzo A4 blanco
    pagina_a4 = Image.new('RGB', (w_lienzo, h_lienzo), (255, 255, 255))
    pos_x = (w_lienzo - nuevo_w) // 2
    pos_y = (h_lienzo - nuevo_h) // 2
    pagina_a4.paste(img_redim, (pos_x, pos_y))

    return pagina_a4


def compilar_imagenes_a_pdf(lista_imagenes, nombre_archivo='documento_escaneado.pdf', filtro='magic_color', autocrop=True):
    """
    Recibe una lista de imágenes (UploadedFile, BytesIO, o rutas de archivo),
    las procesa con detección de página y realce de contraste,
    y las compila en un único archivo PDF normalizado A4.
    """
    if not lista_imagenes:
        return None

    paginas_procesadas = []
    for item in lista_imagenes:
        try:
            pag = normalizar_imagen_a4(item, filtro=filtro, autocrop=autocrop)
            paginas_procesadas.append(pag)
        except Exception as e:
            print(f"Error procesando imagen para PDF: {e}")

    if not paginas_procesadas:
        return None

    pdf_buffer = io.BytesIO()
    primera_pagina = paginas_procesadas[0]
    otras_paginas = paginas_procesadas[1:] if len(paginas_procesadas) > 1 else []

    primera_pagina.save(
        pdf_buffer,
        format='PDF',
        save_all=True,
        append_images=otras_paginas,
        resolution=150.0,
        quality=90
    )
    pdf_buffer.seek(0)

    return ContentFile(pdf_buffer.getvalue(), name=nombre_archivo)
