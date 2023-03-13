from django.core.paginator import Paginator
from django.shortcuts import render

from ecs.core.models.clinic import Clinic
from ecs.users.utils import user_group_required


@user_group_required('EC-Executive')
def administration(request):
    limit = 20
    page = request.GET.get('page', 1)

    paginator = Paginator(Clinic.objects.order_by("-is_favorite", "-pk"), limit, allow_empty_first_page=True)
    try:
        clinics = paginator.page(page)
    except:
        clinics = paginator.page(1)

    return render(request, 'clinic/administration.html', {
        'clinics': clinics
    })
