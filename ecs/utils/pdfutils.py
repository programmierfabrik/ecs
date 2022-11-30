'''
========
pdfutils
========

- identification (is valid pdf, number of pages),
- manipulation (barcode stamp)
- conversion (to PDF/A, to text)
- creation (from html)

'''
import io
import logging
import mimetypes
import os
import subprocess
import tempfile

import pikepdf
from django.conf import settings
from qrcode import QRCode
from reportlab.lib import pagesizes
from reportlab.pdfgen import canvas
from weasyprint import default_url_fetcher, HTML

logger = logging.getLogger(__name__)


def decrypt_pdf(src):
    pdf = pikepdf.Pdf.open(src)
    pdf_stream = io.BytesIO()
    pdf.save(pdf_stream)
    return pdf_stream


def pdf_barcodestamp(source, barcode, text=None):
    qr = QRCode()
    qr.add_data(barcode)
    qrcode_image = qr.make_image()

    with tempfile.NamedTemporaryFile() as pdf:
        can = canvas.Canvas(pdf, pagesize=pagesizes.A4)
        width = 40
        font_size = 8
        text_offset = (width - font_size) / 2
        with tempfile.NamedTemporaryFile() as tmp:
            qrcode_image.save(tmp)
            can.drawImage(tmp.name, x=0, y=0, width=width, height=width)
        can.rotate(90)
        pdf_text = can.beginText(x=width, y=-text_offset - font_size)
        pdf_text.setFont("Helvetica", 8)
        pdf_text.textLine(text=text)
        can.drawText(pdf_text)

        can.save()
        pdf.seek(0)

        stamped = tempfile.TemporaryFile()
        p = subprocess.check_call(
            ['pdftk', '-', 'stamp', pdf.name, 'output', '-', 'dont_ask'],
            stdin=source, stdout=stamped
        )

    stamped.seek(0)
    return stamped


def _url_fetcher(url):
    if url.startswith('static:'):
        path = os.path.abspath(os.path.join(settings.STATIC_ROOT, url[len('static:'):]))
        if not path.startswith(settings.STATIC_ROOT):
            raise ValueError('static: URI points outside of static directory!')
        with open(path, 'rb') as f:
            data = f.read()
        return {'string': data, 'mime_type': mimetypes.guess_type(path)[0]}

    return default_url_fetcher(url)


def html2pdf(html):
    return HTML(string=html, url_fetcher=_url_fetcher).write_pdf()
