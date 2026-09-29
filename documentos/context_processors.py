from .models import Documento, NotaRecibida


def sidebar_context(request):
    """
    Context processor para proveer datos dinámicos globales al sidebar y topbar
    en todas las vistas del sistema SysDoc IT.
    """
    if not request.user.is_authenticated:
        return {}

    notas_count = Documento.objects.filter(tipo='NOTA').count()
    informes_count = Documento.objects.filter(tipo='INFORME').count()
    actas_count = Documento.objects.filter(tipo='ACTA').count()
    total_count = Documento.objects.count()
    emitidos_count = Documento.objects.filter(estado='EMITIDO').count()
    entregados_count = Documento.objects.filter(estado='ENTREGADO').count()

    recibidos_total = NotaRecibida.objects.count()
    recibidos_pendientes = NotaRecibida.objects.filter(estado='PENDIENTE').count()

    nombre_completo = request.user.get_full_name().strip()
    nombre_usuario = nombre_completo if nombre_completo else request.user.username

    return {
        'conteo_notas': notas_count,
        'conteo_informes': informes_count,
        'conteo_actas': actas_count,
        'conteo_total': total_count,
        'conteo_emitidos': emitidos_count,
        'conteo_entregados': entregados_count,
        'conteo_recibidos_total': recibidos_total,
        'conteo_recibidos_pendientes': recibidos_pendientes,
        'nombre_usuario': nombre_usuario,
        'cargo_usuario': 'Departamento Informática',
    }

