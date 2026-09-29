"""
Script para crear los dos usuarios del área de Informática.
Ejecutar con: python crear_usuarios.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

usuarios = [
    {
        'username': 'usuario1',
        'password': 'Informatica2026!',
        'first_name': 'Usuario',
        'last_name': 'Uno',
        'email': '',
        'is_staff': True,
    },
    {
        'username': 'usuario2',
        'password': 'Informatica2026!',
        'first_name': 'Usuario',
        'last_name': 'Dos',
        'email': '',
        'is_staff': True,
    },
]

for u in usuarios:
    if not User.objects.filter(username=u['username']).exists():
        user = User.objects.create_user(
            username=u['username'],
            password=u['password'],
            first_name=u['first_name'],
            last_name=u['last_name'],
            email=u['email'],
            is_staff=u['is_staff'],
        )
        print(f"OK: Usuario '{u['username']}' creado. Contrasena: {u['password']}")
    else:
        print(f"OMITIDO: Usuario '{u['username']}' ya existe.")

print("\nRecorda cambiar las contrasenas desde el panel de administracion.")
print("   Panel de admin: http://localhost:8000/admin/")
