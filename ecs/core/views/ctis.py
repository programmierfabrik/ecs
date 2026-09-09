from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ecs.core.ctis import (
    CTISError, CTISNotConfigured, ctis_configured, import_or_sync_ctis_study,
)
from ecs.core.forms import CTISNumberForm
from ecs.core.models import Submission
from ecs.users.utils import user_group_required

NOT_CONFIGURED_MESSAGE = (
    'Die CTIS-Schnittstelle ist für diese Installation nicht konfiguriert.'
)
FAILED_MESSAGE = (
    'Die CTIS-Studie konnte nicht abgerufen werden. Bitte versuchen Sie es '
    'später erneut.'
)


@user_group_required('CTIS Importer')
def import_ctis_study(request):
    configured = ctis_configured()
    form = CTISNumberForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Checked before the form is even looked at further, so an instance
        # without credentials says so instead of failing on the first call.
        if not configured:
            messages.error(request, NOT_CONFIGURED_MESSAGE)
        else:
            try:
                submission = import_or_sync_ctis_study(
                    form.cleaned_data['ctis_number'])
            except CTISNotConfigured:
                messages.error(request, NOT_CONFIGURED_MESSAGE)
            except CTISError:
                messages.error(request, FAILED_MESSAGE)
            else:
                return redirect('view_submission', submission_pk=submission.pk)
    return render(request, 'submissions/ctis_import.html', {
        'form': form,
        'ctis_configured': configured,
    })


@user_group_required('CTIS Importer')
def sync_ctis_study(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    target = submission
    if request.method == 'POST':
        form = CTISNumberForm(request.POST)
        if not ctis_configured():
            messages.error(request, NOT_CONFIGURED_MESSAGE)
        elif form.is_valid():
            try:
                target = import_or_sync_ctis_study(
                    form.cleaned_data['ctis_number'])
            except CTISNotConfigured:
                messages.error(request, NOT_CONFIGURED_MESSAGE)
            except CTISError:
                messages.error(request, FAILED_MESSAGE)
            else:
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
