"""
Script para corregir caracteres de codificación CP1252/Latin-1 en PostgreSQL.
Corrige viñetas (\\x95 -> •), comillas (\\x93/\\x94 -> “/”), guiones (\\x96 -> –), etc.
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Cargar .env para conectar a PostgreSQL
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ[k.strip()] = v.strip()

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.apps import apps
from django.db import models, connection

CP1252_MAP = {
    '\x80': '€',
    '\x82': '‚',
    '\x83': 'ƒ',
    '\x84': '„',
    '\x85': '…',
    '\x86': '†',
    '\x87': '‡',
    '\x88': 'ˆ',
    '\x89': '‰',
    '\x8a': 'Š',
    '\x8b': '‹',
    '\x8c': 'Œ',
    '\x8e': 'Ž',
    '\x91': '‘',
    '\x92': '’',
    '\x93': '“',
    '\x94': '”',
    '\x95': '•',
    '\x96': '–',
    '\x97': '—',
    '\x98': '˜',
    '\x99': '™',
    '\x9a': 'š',
    '\x9b': '›',
    '\x9c': 'œ',
    '\x9e': 'ž',
    '\x9f': 'Ÿ',
}

def clean_text(s):
    if not isinstance(s, str):
        return s
    for bad_char, good_char in CP1252_MAP.items():
        if bad_char in s:
            s = s.replace(bad_char, good_char)
    return s

def main():
    print(f"Conectado a: {connection.settings_dict['ENGINE']} en {connection.settings_dict['HOST']}")
    total_fixed = 0
    
    for model in apps.get_models():
        app_label = model._meta.app_label
        if app_label in ('contenttypes', 'auth', 'sessions', 'admin', 'messages'):
            continue
        
        text_fields = [f.name for f in model._meta.fields if isinstance(f, (models.CharField, models.TextField))]
        if not text_fields:
            continue
        
        model_count = 0
        for obj in model.objects.all():
            updated = False
            for field_name in text_fields:
                val = getattr(obj, field_name)
                if val and any(c in val for c in CP1252_MAP):
                    new_val = clean_text(val)
                    setattr(obj, field_name, new_val)
                    updated = True
            if updated:
                obj.save()
                model_count += 1
                total_fixed += 1
        
        if model_count > 0:
            print(f"  • {model.__name__}: {model_count} registros corregidos")

    print(f"\nTotal de registros corregidos en la base de datos: {total_fixed}")

    # Verificar documento 82 específicamente
    from documentos.models import Documento
    doc = Documento.objects.filter(id=82).first()
    if doc:
        for line in doc.cuerpo.split('\n'):
            if 'Recuperar equipos' in line:
                print(f"\nVerificación Doc 82:")
                print(f"  Línea: {line}")
                print(f"  Primer carácter: {repr(line[0])} (codepoint: {ord(line[0])})")

if __name__ == '__main__':
    main()
