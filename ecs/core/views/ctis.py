from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ecs.core.ctis import import_or_sync_ctis_study
from ecs.core.forms import CTISNumberForm
from ecs.core.models import Submission
from ecs.users.utils import user_group_required


@user_group_required('CTIS Importer')
def import_ctis_study(request):
    form = CTISNumberForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        submission = import_or_sync_ctis_study(form.cleaned_data['ctis_number'])
        messages.success(request, 'CTIS-Studie mit EK-Nr. {ec_number} verknüpft.'.format(
            ec_number=submission.get_ec_number_display()))
        return redirect('view_submission', submission_pk=submission.pk)
    return render(request, 'submissions/ctis_import.html', {'form': form})


@user_group_required('CTIS Importer')
def sync_ctis_study(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    target = submission
    if request.method == 'POST':
        form = CTISNumberForm(request.POST)
        if form.is_valid():
            target = import_or_sync_ctis_study(form.cleaned_data['ctis_number'])
            if target.pk == submission.pk:
                messages.success(request, 'Synchronisiert auf CTIS-Nummer {ctis_number}.'.format(
                    ctis_number=form.cleaned_data['ctis_number']))
            else:
                messages.warning(request, (
                    'Diese CTIS-Nummer gehört zu einer anderen Studie (EK-Nr. {ec_number}) - dorthin weitergeleitet.'
                ).format(ec_number=target.get_ec_number_display()))
        else:
            messages.error(request, 'Ungültige CTIS-Nummer.')
    return redirect('view_submission', submission_pk=target.pk)
