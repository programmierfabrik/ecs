import datetime
import tempfile

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db.models import Count
from django.utils.text import slugify
from django.utils.translation import gettext as _

from ecs.communication.mailutils import deliver
from ecs.core.models import AdvancedSettings
from ecs.users.utils import user_flag_required

from ecs.pki.forms import CertForm
from ecs.pki.models import Certificate


@user_flag_required('is_internal')
def cert_list(request):
    return render(request, 'pki/cert_list.html', {
        'certs': (
            Certificate.objects
            .select_related('user')
            .annotate(is_revoked=Count('revoked_at'))
            .order_by('-created_at')
        ),
    })


@user_flag_required('is_internal')
def list_soon_to_be_expired_certs(request):
    weeks_for_warning_window = AdvancedSettings.objects.get(pk=1).warning_window_certificate
    today = datetime.date.today()
    warning_window = today + datetime.timedelta(weeks=weeks_for_warning_window)
    return render(request, 'pki/cert_soon_expired_list.html', {
        'warning_window': weeks_for_warning_window,
        'certs': (
            Certificate.objects
            .select_related('user')
            .filter(revoked_at__isnull=True)
            .filter(expires_at__gte=today)
            .filter(expires_at__lte=warning_window)
            .order_by('expires_at')
        ),
    })


@user_flag_required('is_internal')
def create_cert(request):
    form = CertForm(request.POST or None)

    if form.is_valid():
        cn = form.cleaned_data.get('cn').strip()
        user = form.cleaned_data['user']

        with tempfile.NamedTemporaryFile() as tmp:
            cert, passphrase = Certificate.create_for_user(tmp.name, user, cn=cn)
            pkcs12 = tmp.read()

        filename = '{}.p12'.format(slugify(cert.cn))

        subject = _('Your Client Certificate')
        message = _('See Attachment.')
        attachments = (
            (filename, pkcs12, 'application/x-pkcs12'),
        )

        deliver(user.email, subject=subject, message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachments, nofilter=True)

        return render(request, 'pki/cert_created.html', {
            'passphrase': passphrase,
            'target_user': user,
        })

    return render(request, 'pki/create_cert.html', {
        'form': form,
    })


@require_POST
@user_flag_required('is_internal')
def revoke_cert(request, cert_pk=None):
    cert = get_object_or_404(Certificate, pk=cert_pk)
    cert.revoke()
    return redirect('pki.cert_list')
