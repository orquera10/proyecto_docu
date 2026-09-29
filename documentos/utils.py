from .models import Documento


def generar_numero(tipo: str, anio: int) -> str:
    """
    Genera el próximo número correlativo para un tipo de documento y año dados.
    Ejemplo: NOTA-001/2026, INF-001/2026, ACTA-001/2026
    """
    prefijos = {
        'NOTA': 'NOTA',
        'INFORME': 'INF',
        'ACTA': 'ACTA',
    }
    prefijo = prefijos.get(tipo, tipo)
    patron = f'{prefijo}-'

    # Filtrar documentos del mismo tipo y año
    docs = Documento.objects.filter(
        tipo=tipo,
        fecha__year=anio,
    ).exclude(numero='').order_by('numero')

    max_seq = 0
    for doc in docs:
        try:
            # Formato esperado: PREFIJO-NNN/AAAA
            partes = doc.numero.split('-')
            if len(partes) == 2:
                seq_str = partes[1].split('/')[0]
                seq = int(seq_str)
                if seq > max_seq:
                    max_seq = seq
        except (ValueError, IndexError):
            pass

    siguiente = max_seq + 1
    return f'{prefijo}-{siguiente:03d}/{anio}'


def generar_numero_recepcion(anio: int) -> str:
    """
    Genera el próximo número correlativo para una nota recibida en el año dado.
    Ejemplo: REC-001/2026
    """
    from .models import NotaRecibida
    prefijo = 'REC'
    notas = NotaRecibida.objects.filter(
        fecha_recepcion__year=anio,
    ).exclude(numero_registro='').order_by('numero_registro')

    max_seq = 0
    for n in notas:
        try:
            partes = n.numero_registro.split('-')
            if len(partes) == 2:
                seq_str = partes[1].split('/')[0]
                seq = int(seq_str)
                if seq > max_seq:
                    max_seq = seq
        except (ValueError, IndexError):
            pass

    siguiente = max_seq + 1
    return f'{prefijo}-{siguiente:03d}/{anio}'

