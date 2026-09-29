import os
import io
import base64
import docx
from xhtml2pdf import pisa

doc = docx.Document('para_analizar/pedido adultos mayores.docx')
b = doc.part.rels['rId4'].target_part.blob
uri = 'data:image/jpeg;base64,' + base64.b64encode(b).decode('ascii')
buf = io.BytesIO()
html = f'<html><body><img src="{uri}" style="width:350pt;" /></body></html>'
status = pisa.CreatePDF(html, dest=buf)
print('xhtml2pdf data URI success:', status.err == 0, 'size:', len(buf.getvalue()))

