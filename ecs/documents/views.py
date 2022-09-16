from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import render

from ecs.documents.forms import DocumentForm
from ecs.documents.models import Document


def upload_document(request, template='documents/upload_form.html'):
    form = DocumentForm(request.POST or None, request.FILES or None, prefix='document')
    documents = Document.objects.filter(pk__in=request.docstash.get('document_pks', []))
    if request.method == 'POST' and form.is_valid():
        new_document = form.save()
        documents |= Document.objects.filter(pk=new_document.pk)
        documents = documents.exclude(
            pk__in=documents.exclude(replaces_document=None).values('replaces_document').query)
        request.docstash['document_pks'] = [d.pk for d in documents]
        request.docstash.save()
        form = DocumentForm(prefix='document')
    return render(request, template, {
        'form': form,
        'documents': documents.order_by('doctype__identifier', 'date', 'name'),
    })


def delete_document(request, document_pk):
    document_pks = set(request.docstash.get('document_pks', []))
    if document_pk in document_pks:
        document_pks.remove(document_pk)
    request.docstash['document_pks'] = list(document_pks)
    request.docstash.save()


def handle_download(request, doc, view=False):
    if not doc.doctype.is_downloadable and not request.user.profile.is_internal:
        raise PermissionDenied()

    response = FileResponse(doc.retrieve(request.user, 'download'), content_type=doc.mimetype)
    response['Content-Disposition'] = '{};filename={}'.format('inline' if view else 'attachment', doc.get_filename())
    return response
