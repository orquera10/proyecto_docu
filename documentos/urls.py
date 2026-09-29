from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('documentos/', views.lista_documentos, name='lista_documentos'),
    path('documentos/nuevo/', views.crear_documento, name='crear_documento'),
    path('documentos/<int:pk>/', views.detalle_documento, name='detalle_documento'),
    path('documentos/<int:pk>/editar/', views.editar_documento, name='editar_documento'),
    path('documentos/<int:pk>/eliminar/', views.eliminar_documento, name='eliminar_documento'),
    path('documentos/<int:pk>/pdf/', views.generar_pdf, name='generar_pdf'),
    path('api/subir-imagen/', views.subir_imagen_editor, name='subir_imagen_editor'),
    path('adjuntos/<int:pk>/eliminar/', views.eliminar_adjunto, name='eliminar_adjunto'),
    # Mesa de Entrada / Notas Recibidas
    path('recibidos/', views.lista_notas_recibidas, name='lista_notas_recibidas'),
    path('recibidos/nuevo/', views.crear_nota_recibida, name='crear_nota_recibida'),
    path('recibidos/<int:pk>/', views.detalle_nota_recibida, name='detalle_nota_recibida'),
    path('recibidos/<int:pk>/editar/', views.editar_nota_recibida, name='editar_nota_recibida'),
    path('recibidos/<int:pk>/eliminar/', views.eliminar_nota_recibida, name='eliminar_nota_recibida'),
    path('recibidos/<int:pk>/pdf/', views.descargar_pdf_nota_recibida, name='descargar_pdf_nota_recibida'),
]


