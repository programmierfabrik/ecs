from django.core.paginator import Paginator
from django.shortcuts import render, redirect

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
