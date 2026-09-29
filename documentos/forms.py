from datetime import date, datetime
from django import forms
from .models import Documento, ItemActa, NotaRecibida


class DocumentoForm(forms.ModelForm):
    estado = forms.ChoiceField(choices=Documento.ESTADO_CHOICES, required=False, initial='BORRADOR')

    class Meta:
        model = Documento
        fields = ['tipo', 'fecha', 'asunto', 'remitente', 'destinatario', 'destinatario_cargo', 'destinatario_nombre', 'receptor_nombre', 'receptor_dni', 'cuerpo', 'estado']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-control', 'id': 'id_tipo'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'asunto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asunto del documento'}),
            'remitente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del remitente'}),
            'destinatario': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Ej: Sector o dependencia de destino'}),
            'destinatario_cargo': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Ej: A LA SECRETARIA DE NIÑEZ, ADOLESCENCIA Y FAMILIA'}),
            'destinatario_nombre': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Ej: Dra. Marta Iriarte'}),
            'receptor_nombre': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Nombre y Apellido de quien recibe (o dejar en blanco)'}),
            'receptor_dni': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'DNI de quien recibe (o dejar en blanco)'}),
            'cuerpo': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'placeholder': 'Redacte aquí el contenido del documento...'}),
            'estado': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'tipo': 'Tipo de Documento',
            'fecha': 'Fecha',
            'asunto': 'Asunto',
            'remitente': 'Remitente',
            'destinatario': 'Sector o Dependencia de Destino',
            'destinatario_cargo': 'Cargo / Organismo al que va dirigido',
            'destinatario_nombre': 'Nombre y Apellido de la Persona',
            'receptor_nombre': 'Persona que Recibe (Aclaración)',
            'receptor_dni': 'DNI de quien Recibe',
            'cuerpo': 'Contenido',
            'estado': 'Estado',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuerpo'].required = False
        tipo = self.initial.get('tipo') or (self.instance.pk and self.instance.tipo)
        if tipo == 'ACTA' and not self.initial.get('cuerpo') and not getattr(self.instance, 'cuerpo', None):
            self.initial['cuerpo'] = 'Recibí del Área de Informática los bienes que se detallan a continuación.-'
        if tipo in ['NOTA', 'INFORME'] and not self.initial.get('remitente') and not getattr(self.instance, 'remitente', None):
            self.initial['remitente'] = 'Área de Informática'
        if self.instance.pk and self.instance.tipo in ['NOTA', 'INFORME']:
            if not self.initial.get('destinatario_cargo') and not self.instance.destinatario_cargo:
                self.initial['destinatario_cargo'] = self.instance.cargo_display
            if not self.initial.get('destinatario_nombre') and not self.instance.destinatario_nombre:
                self.initial['destinatario_nombre'] = self.instance.nombre_display

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo')
        cuerpo = (cleaned_data.get('cuerpo') or '').strip()
        if tipo == 'ACTA':
            if not cuerpo:
                cleaned_data['cuerpo'] = 'Recibí del Área de Informática los bienes que se detallan a continuación.-'
        else:
            if not cuerpo:
                self.add_error('cuerpo', 'Este campo es obligatorio.')
            cargo = (cleaned_data.get('destinatario_cargo') or '').strip().upper()
            nombre = (cleaned_data.get('destinatario_nombre') or '').strip().upper()
            partes = [p for p in [cargo, nombre] if p]
            if partes:
                cleaned_data['destinatario'] = "\n".join(partes)
        return cleaned_data


class ItemActaForm(forms.ModelForm):
    class Meta:
        model = ItemActa
        fields = ['cantidad', 'descripcion', 'numero_serie', 'codigo_inventario', 'condicion', 'observaciones']
        widgets = {
            'cantidad': forms.NumberInput(attrs={'class': 'acta-item-input acta-item-cant', 'min': 1, 'placeholder': '1'}),
            'descripcion': forms.TextInput(attrs={'class': 'acta-item-input', 'placeholder': 'Descripción del bien o equipo (ej: Monitor 24", Notebook...)'}),
            'numero_serie': forms.TextInput(attrs={'class': 'acta-item-input', 'placeholder': 'N° de serie (opcional)'}),
            'codigo_inventario': forms.TextInput(attrs={'class': 'acta-item-input', 'placeholder': 'Cód. inventario (opcional)'}),
            'condicion': forms.Select(attrs={'class': 'acta-item-select'}),
            'observaciones': forms.TextInput(attrs={'class': 'acta-item-input', 'placeholder': 'Observaciones adicionales (opcional)'}),
        }


# Formset para ítems del Acta (inline)
ItemActaFormSet = forms.inlineformset_factory(
    Documento,
    ItemActa,
    form=ItemActaForm,
    extra=1,
    can_delete=True,
    min_num=0,
)


class NotaRecibidaForm(forms.ModelForm):
    class Meta:
        model = NotaRecibida
        fields = [
            'fecha_recepcion',
            'hora_recepcion',
            'remitente_origen',
            'numero_origen',
            'asunto',
            'descripcion',
            'recibido_por',
            'estado',
            'documento_respuesta',
            'observaciones',
            'archivo_pdf',
        ]
        widgets = {
            'fecha_recepcion': forms.DateInput(attrs={'class': 'form-input-styled', 'type': 'date'}),
            'hora_recepcion': forms.TimeInput(attrs={'class': 'form-input-styled', 'type': 'time'}),
            'remitente_origen': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Ej: Defensoría de los Derechos de Niñas, Niños y Adolescentes'}),
            'numero_origen': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Ej: Nota N° 45/2026 o Ref. 102/SNAF'}),
            'asunto': forms.TextInput(attrs={'class': 'form-input-styled', 'placeholder': 'Motivo o asunto de la nota recibida'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Resumen o detalle del contenido de la nota recibida...'}),
            'recibido_por': forms.Select(attrs={'class': 'form-input-styled'}),
            'estado': forms.Select(attrs={'class': 'form-input-styled'}),
            'documento_respuesta': forms.Select(attrs={'class': 'form-input-styled'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notas internas u observaciones sobre el trámite...'}),
            'archivo_pdf': forms.FileInput(attrs={'class': 'form-input-styled', 'accept': '.pdf,application/pdf'}),
        }
        labels = {
            'fecha_recepcion': 'Fecha de Recepción',
            'hora_recepcion': 'Hora de Recepción',
            'remitente_origen': 'Remitente / Organismo de Origen',
            'numero_origen': 'N° de Nota Externa o Referencia',
            'asunto': 'Asunto / Motivo',
            'descripcion': 'Detalle o Contenido',
            'recibido_por': 'Recibido por (Personal de Informática)',
            'estado': 'Estado de Gestión',
            'documento_respuesta': 'Documento de Salida que Responde (Opcional)',
            'observaciones': 'Observaciones Internas',
            'archivo_pdf': 'Archivo PDF de la Nota (Opcional si sube fotos/escaneo)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            if not self.initial.get('fecha_recepcion'):
                self.initial['fecha_recepcion'] = date.today()
            if not self.initial.get('hora_recepcion'):
                self.initial['hora_recepcion'] = datetime.now().strftime('%H:%M')
        self.fields['documento_respuesta'].queryset = Documento.objects.filter(
            tipo__in=['NOTA', 'INFORME']
        ).order_by('-fecha', '-id')
        self.fields['documento_respuesta'].required = False
        self.fields['archivo_pdf'].required = False
        self.fields['hora_recepcion'].required = False
        self.fields['numero_origen'].required = False
        self.fields['descripcion'].required = False
        self.fields['observaciones'].required = False
