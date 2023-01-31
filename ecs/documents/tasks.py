from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models import Count
from django.contrib.auth.models import User

from celery.schedules import crontab

from ecs.documents.models import DownloadHistory
from ecs.communication.utils import send_message_template
from ecs.users.utils import get_user, get_office_user
from ecs.celery import app as celery_app

WEEKLY_DOWNLOAD_THRESHOLD = 150


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # run once per week on sunday at 23:59
    sender.add_periodic_task(crontab(day_of_week=0, hour=23, minute=59), send_download_warnings.s())
    # run once per month on the first day of the month at 0:15
    sender.add_periodic_task(crontab(day_of_month=1, hour=0, minute=15), expire_download_history.s())


@celery_app.task
def send_download_warnings():
    now = timezone.now()

    hist = (
        DownloadHistory.objects
        .filter(user__profile__is_internal=False,
                downloaded_at__range=(now - timedelta(days=7), now))
        .order_by('user_id')
        .values_list('user_id')
        .annotate(Count('id'))
        .filter(id__count__gt=WEEKLY_DOWNLOAD_THRESHOLD)
    )

    sender = get_user('root@system.local')
    receiver = get_office_user()

    for user_id, count in hist:
        user = User.objects.get(id=user_id)
        subject = _('Large number of downloads by {user}').format(user=user)
        send_message_template(sender, receiver, subject,
                              'documents/messages/download_warning.txt',
                              {'user': user, 'count': count})


@celery_app.task
def expire_download_history():
    DownloadHistory.objects.filter(
        downloaded_at__lt=timezone.now() - timedelta(days=365 * 3),
    ).delete()
