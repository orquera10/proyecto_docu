from django.contrib import admin
from .models import Documento, ItemActa, NotaRecibida


class ItemActaInline(admin.TabularInline):
    model = ItemActa
    extra = 1


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('numero', 'tipo', 'fecha', 'asunto', 'destinatario', 'estado', 'creado_por')
    list_filter = ('tipo', 'estado', 'fecha')
    search_fields = ('numero', 'asunto', 'remitente', 'destinatario')
    readonly_fields = ('numero', 'creado_en', 'modificado_en')
    inlines = [ItemActaInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(ItemActa)
class ItemActaAdmin(admin.ModelAdmin):
    list_display = ('documento', 'cantidad', 'descripcion', 'condicion', 'numero_serie')
    list_filter = ('condicion',)
    search_fields = ('descripcion', 'numero_serie', 'codigo_inventario')


@admin.register(NotaRecibida)
class NotaRecibidaAdmin(admin.ModelAdmin):
    list_display = ('numero_registro', 'fecha_recepcion', 'remitente_origen', 'numero_origen', 'asunto', 'recibido_por', 'estado')
    list_filter = ('estado', 'fecha_recepcion', 'recibido_por')
    search_fields = ('numero_registro', 'remitente_origen', 'numero_origen', 'asunto', 'descripcion')
    readonly_fields = ('numero_registro', 'creado_en', 'modificado_en')

