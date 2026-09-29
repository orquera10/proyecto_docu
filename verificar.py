import os, sys, django
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from documentos.models import Documento, ItemActa

print('=== RESUMEN FINAL ===')
print(f'TOTAL: {Documento.objects.count()} documentos')
print(f'  NOTAS:    {Documento.objects.filter(tipo="NOTA").count()}')
print(f'  INFORMES: {Documento.objects.filter(tipo="INFORME").count()}')
print(f'  ACTAS:    {Documento.objects.filter(tipo="ACTA").count()}')
print(f'  EMITIDOS: {Documento.objects.filter(estado="EMITIDO").count()}')
print(f'Items acta: {ItemActa.objects.count()}')
print()
print('Muestra de registros:')
for d in Documento.objects.order_by('tipo', 'numero')[:8]:
    print(f'  [{d.numero}] {d.tipo} | {d.fecha} | {d.asunto[:55]}')
