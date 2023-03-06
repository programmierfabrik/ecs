import datetime

from celery.schedules import crontab
from django.contrib.auth.models import User

from ecs.celery import app as celery_app
from ecs.communication.utils import send_system_message_template
from ecs.core.models import AdvancedSettings
from ecs.pki.models import Certificate


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # run once every monday at 08:47
    sender.add_periodic_task(crontab(hour=8, minute=47, day_of_week=1), check_certificates_to_be_expired.s())


@celery_app.task()
def check_certificates_to_be_expired():
    weeks_for_warning_window = AdvancedSettings.objects.get(pk=1).warning_window_certificate
    today = datetime.date.today()
    warning_window = today + datetime.timedelta(weeks=weeks_for_warning_window)
    certs = (
        Certificate.objects.select_related('user')
        .filter(revoked_at__isnull=True)
        .filter(expires_at__gte=today)
        .filter(expires_at__lte=warning_window)
        .order_by('expires_at')
    )

    certificate_warning_reciever = User.objects.filter(groups__name='Certificate-Warning Reciever')
    for user in certificate_warning_reciever:
        send_system_message_template(
            user.email,
            'Zertifikate, die bald ablaufen werden',
            'pki/warn_soon_to_be_expired_certs.txt', {
                'user': user,
                'certs': certs,
            }
        )
