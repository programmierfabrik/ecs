from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404

from ecs.core.forms.clinic import AdministrationFilterForm, ClinicForm
from ecs.core.models.clinic import Clinic
from ecs.users.utils import user_group_required


@user_group_required('EC-Executive')
def administration(request):
    limit = 20

    filter_defaults = {
        'page': '1',
        'activity': 'active',
        'keyword': '',
    }

    filterdict = request.POST or filter_defaults
    filterform = AdministrationFilterForm(filterdict)
    if not filterform.is_valid():
        filterform = AdministrationFilterForm(filter_defaults)
        filterform.is_valid()

    page = filterform.cleaned_data['page']

    activity = filterform.cleaned_data['activity']
    clinics = Clinic.objects
    if activity == 'active':
        clinics = clinics.filter(deactivated=False)
    elif activity == 'inactive':
        clinics = clinics.filter(deactivated=True)

    keyword = filterform.cleaned_data['keyword']
    if keyword is not None and keyword != "":
        clinics = clinics.filter(name__icontains=keyword)

    paginator = Paginator(clinics.order_by("-is_favorite", "-pk"), limit, allow_empty_first_page=True)
    try:
        clinics = paginator.page(page)
    except:
        clinics = paginator.page(1)

    return render(request, 'clinic/administration.html', {
        'clinics': clinics,
        'filterform': filterform
    })


@user_group_required('EC-Executive')
def upsert_clinic(request, clinic_id=None):
    if clinic_id:
        instance = get_object_or_404(Clinic, pk=clinic_id)
        updating = True
    else:
        instance = None
        updating = False

    form = ClinicForm(instance=instance)

    if request.method == 'POST':
        form = ClinicForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            return redirect('core.clinic.administration')

    return render(request, 'clinic/upsert.html', {
        'form': form,
        'updating': updating
    })
