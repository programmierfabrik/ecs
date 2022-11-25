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
import tempfile

import pikepdf
from PyPDF2 import PdfFileWriter, PdfFileReader
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

    new_pdf_data = io.BytesIO()
    can = canvas.Canvas(new_pdf_data, pagesize=pagesizes.A4)
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
    new_pdf_data.seek(0)

    new_pdf = PdfFileReader(new_pdf_data, strict=False)
    existing_pdf = PdfFileReader(source, strict=False)
    output = PdfFileWriter()

    for i in range(len(existing_pdf.pages)):
        page = existing_pdf.getPage(i)
        page.mergePage(new_pdf.getPage(0))
        output.addPage(page)

    pdf_data = io.BytesIO()
    output.write(pdf_data)
    pdf_data.seek(0)

    return pdf_data


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
