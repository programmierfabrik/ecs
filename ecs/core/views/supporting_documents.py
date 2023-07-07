from django.core.paginator import Paginator
from django.http import HttpResponse, FileResponse
from django.shortcuts import render, redirect, get_object_or_404

from ecs.core.forms.supporting_documents import SupportingDocumentsForm, SupportingDocumentsAdministrationFilterForm
from ecs.core.models import SupportingDocument
from ecs.tasks.models import TaskType
from ecs.users.utils import user_group_required


@user_group_required('Supporting Documents')
def administration(request):
    limit = 20
    filter_defaults = {
        'tasks': TaskType.objects.none(),
        'page': '1',
        'filename': '',
    }

    filterdict = request.POST or filter_defaults
    filterform = SupportingDocumentsAdministrationFilterForm(filterdict)
    if not filterform.is_valid():
        filterform = SupportingDocumentsAdministrationFilterForm(filter_defaults)
        filterform.is_valid()

    supporting_documents = SupportingDocument.objects.all()

    # Apply filter for tasks
    tasks = filterform.cleaned_data.get('tasks')
    if tasks:
        supporting_documents = supporting_documents.filter(tasks__in=tasks)
    # Apply filter for filename
    filename = filterform.cleaned_data['filename']
    if filename is not None and filename != "":
        supporting_documents = supporting_documents.filter(document__name__icontains=filename)

    # Paginate here
    paginator = Paginator(supporting_documents.order_by("-pk"), limit, allow_empty_first_page=True)
    page = filterform.cleaned_data['page']
    try:
        supporting_documents = paginator.page(page)
    except:
        supporting_documents = paginator.page(1)
 
    return render(request, 'supporting_documents/administration.html', {
        'supporting_documents': supporting_documents,
        'filterform': filterform
    })

@user_group_required('Supporting Documents')
def create(request):
    if request.method == "POST":
        form = SupportingDocumentsForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('core.supporting_documents.administration')
    else:
        form = SupportingDocumentsForm()

    return render(request, 'supporting_documents/create.html', {
        'form': form,
    })

@user_group_required('Supporting Documents')
def delete(request, pk):
    supporting_document = get_object_or_404(SupportingDocument, pk=pk)
    supporting_document.document.delete()
    supporting_document.delete()
    return HttpResponse(status=204)

@user_group_required('Supporting Documents')
def download(request, pk):
    supporting_document = get_object_or_404(SupportingDocument, pk=pk)

    document = supporting_document.document
    response = FileResponse(document.retrieve_raw(), content_type=document.mimetype)
    response['Content-Disposition'] = 'attachment;filename={}'.format(document.name)
    return response
