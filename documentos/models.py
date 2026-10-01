import os
from datetime import date
from django.db import models
from django.contrib.auth.models import User


class Documento(models.Model):
    TIPO_CHOICES = [
        ('NOTA', 'Nota'),
        ('INFORME', 'Informe'),
        ('ACTA', 'Acta de Entrega'),
    ]
    ESTADO_CHOICES = [
        ('EMITIDO', 'Emitido'),
        ('ENTREGADO', 'Entregado'),
    ]
    FIRMA_CHOICES = [
        ('AMBOS', 'Darío y Alex (Ambas firmas)'),
        ('DARIO', 'Solo Darío'),
        ('ALEX', 'Solo Alex'),
    ]

    tipo = models.CharField('Tipo', max_length=10, choices=TIPO_CHOICES)
    numero = models.CharField('Número', max_length=20, unique=True, blank=True)
    fecha = models.DateField('Fecha')
    asunto = models.CharField('Asunto', max_length=255)
    remitente = models.CharField('Remitente', max_length=150)
    destinatario = models.TextField('Destinatario', blank=True)
    destinatario_cargo = models.CharField('Cargo del Destinatario', max_length=255, blank=True, default='')
    destinatario_nombre = models.CharField('Nombre del Destinatario', max_length=150, blank=True, default='')
    receptor_nombre = models.CharField('Nombre y Apellido de quien recibe', max_length=150, blank=True, default='')
    receptor_dni = models.CharField('DNI de quien recibe', max_length=30, blank=True, default='')
    cuerpo = models.TextField('Contenido', blank=True, default='')
    estado = models.CharField('Estado', max_length=10, choices=ESTADO_CHOICES, default='EMITIDO')
    firma = models.CharField('Firmas', max_length=10, choices=FIRMA_CHOICES, default='AMBOS')
    detalle_entrega = models.TextField('Detalle o Constancia de Entrega', blank=True, default='')
    creado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='documentos', verbose_name='Creado por')
    creado_en = models.DateTimeField('Creado el', auto_now_add=True)
    modificado_en = models.DateTimeField('Modificado el', auto_now=True)

    class Meta:
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.numero} – {self.asunto}'

    def save(self, *args, **kwargs):
        if not self.numero:
            from .utils import generar_numero
            self.numero = generar_numero(self.tipo, self.fecha.year)
        if self.tipo == 'ACTA' and not (self.cuerpo or '').strip():
            self.cuerpo = 'Recibí del Área de Informática los bienes que se detallan a continuación.-'
        if self.tipo in ['NOTA', 'INFORME']:
            partes = []
            if (self.destinatario_cargo or '').strip():
                partes.append(self.destinatario_cargo.strip().upper())
            if (self.destinatario_nombre or '').strip():
                partes.append(self.destinatario_nombre.strip().upper())
            if partes:
                self.destinatario = "\n".join(partes)
        super().save(*args, **kwargs)

    @property
    def tipo_display(self):
        return dict(self.TIPO_CHOICES).get(self.tipo, self.tipo)

    @property
    def firma_display(self):
        return dict(self.FIRMA_CHOICES).get(self.firma, 'Darío y Alex (Ambas firmas)')

    @property
    def prefijo_numero(self):
        prefijos = {'NOTA': 'NOTA', 'INFORME': 'INF', 'ACTA': 'ACTA'}
        return prefijos.get(self.tipo, self.tipo)

    @property
    def cargo_display(self):
        if (self.destinatario_cargo or '').strip():
            return self.destinatario_cargo.strip().upper()
        if self.destinatario:
            lines = [l.strip() for l in self.destinatario.splitlines() if l.strip() and 'despacho' not in l.lower()]
            if len(lines) > 1:
                return "\n".join(lines[:-1]).upper()
            elif len(lines) == 1:
                return lines[0].upper()
        return ''

    @property
    def nombre_display(self):
        if (self.destinatario_nombre or '').strip():
            return self.destinatario_nombre.strip().upper()
        if self.destinatario:
            lines = [l.strip() for l in self.destinatario.splitlines() if l.strip() and 'despacho' not in l.lower()]
            if len(lines) > 1:
                return lines[-1].upper()
        return ''


class ItemActa(models.Model):
    CONDICION_CHOICES = [
        ('NUEVO', 'Nuevo'),
        ('USADO', 'Usado'),
        ('REPARADO', 'Reparado'),
    ]

    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name='items',
        limit_choices_to={'tipo': 'ACTA'},
    )
    cantidad = models.PositiveIntegerField('Cantidad', default=1)
    descripcion = models.CharField('Descripción', max_length=255)
    numero_serie = models.CharField('N° de Serie', max_length=100, blank=True)
    codigo_inventario = models.CharField('Código Inventario', max_length=100, blank=True)
    condicion = models.CharField('Condición', max_length=10, choices=CONDICION_CHOICES, default='USADO')
    observaciones = models.CharField('Observaciones', max_length=255, blank=True)

    class Meta:
        verbose_name = 'Ítem del Acta'
        verbose_name_plural = 'Ítems del Acta'

    def __str__(self):
        return f'{self.cantidad}x {self.descripcion}'


class Adjunto(models.Model):
    documento = models.ForeignKey(
        Documento,
        on_delete=models.CASCADE,
        related_name='adjuntos',
        verbose_name='Documento',
        null=True,
        blank=True,
    )
    archivo = models.FileField('Archivo', upload_to='adjuntos/%Y/%m/')
    nombre_original = models.CharField('Nombre Original', max_length=255, blank=True)
    tamano = models.PositiveIntegerField('Tamaño (bytes)', default=0)
    subido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='adjuntos_subidos',
        verbose_name='Subido por',
    )
    creado_en = models.DateTimeField('Subido el', auto_now_add=True)

    class Meta:
        verbose_name = 'Archivo Adjunto'
        verbose_name_plural = 'Archivos Adjuntos'
        ordering = ['creado_en']

    def __str__(self):
        return self.nombre_original or os.path.basename(self.archivo.name)

    @property
    def extension(self):
        nombre = self.nombre_original or self.archivo.name
        _, ext = os.path.splitext(nombre)
        return ext.lower().replace('.', '')

    @property
    def es_imagen(self):
        return self.extension in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp']

    @property
    def es_pdf(self):
        return self.extension == 'pdf'

    @property
    def tamano_formateado(self):
        tam = self.tamano
        if not tam and self.archivo:
            try:
                tam = self.archivo.size
            except Exception:
                tam = 0
        if tam > 1024 * 1024:
            return f'{tam / (1024 * 1024):.1f} MB'
        return f'{max(1, round(tam / 1024))} KB'

    def save(self, *args, **kwargs):
        if not self.nombre_original and self.archivo:
            self.nombre_original = os.path.basename(self.archivo.name)
        if self.archivo and not self.tamano:
            try:
                self.tamano = self.archivo.size
            except Exception:
                pass
        super().save(*args, **kwargs)


class NotaRecibida(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Revisión'),
        ('EN_TRAMITE', 'En Trámite'),
        ('RESPONDIDO', 'Respondida'),
        ('ARCHIVADO', 'Archivada'),
    ]

    numero_registro = models.CharField('N° Registro', max_length=25, unique=True, blank=True)
    numero_origen = models.CharField('N° Nota Externa / Ref.', max_length=100, blank=True)
    remitente_origen = models.CharField('Remitente / Procedencia', max_length=255)
    fecha_recepcion = models.DateField('Fecha de Recepción')
    hora_recepcion = models.TimeField('Hora de Recepción', null=True, blank=True)
    recibido_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='notas_recibidas',
        verbose_name='Recibido por'
    )
    asunto = models.CharField('Asunto / Motivo', max_length=255)
    descripcion = models.TextField('Detalle o Contenido', blank=True, default='')
    estado = models.CharField('Estado', max_length=15, choices=ESTADO_CHOICES, default='PENDIENTE')
    archivo_pdf = models.FileField('PDF Compilado', upload_to='notas_recibidas/%Y/', blank=True, null=True)
    observaciones = models.TextField('Observaciones', blank=True, default='')
    documento_respuesta = models.ForeignKey(
        'Documento',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_que_responde',
        verbose_name='Documento de Respuesta (Salida)'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    modificado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Nota Recibida'
        verbose_name_plural = 'Notas Recibidas'
        ordering = ['-fecha_recepcion', '-creado_en']

    def __str__(self):
        return f'{self.numero_registro} - {self.remitente_origen}: {self.asunto}'

    def save(self, *args, **kwargs):
        if not self.numero_registro:
            from .utils import generar_numero_recepcion
            anio = self.fecha_recepcion.year if self.fecha_recepcion else date.today().year
            self.numero_registro = generar_numero_recepcion(anio)
        super().save(*args, **kwargs)

    @property
    def badge_estado(self):
        mapa = {
            'PENDIENTE': 'bg-amber-100 text-amber-800 border-amber-300',
            'EN_TRAMITE': 'bg-blue-100 text-blue-800 border-blue-300',
            'RESPONDIDO': 'bg-emerald-100 text-emerald-800 border-emerald-300',
            'ARCHIVADO': 'bg-slate-100 text-slate-700 border-slate-300',
        }
        return mapa.get(self.estado, 'bg-slate-100 text-slate-700 border-slate-300')

