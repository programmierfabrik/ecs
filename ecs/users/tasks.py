from datetime import timedelta

from django.utils import timezone

from celery.schedules import crontab

from ecs.users.models import LoginHistory, Invitation
from ecs.celery import app as celery_app


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # run once per month on the first day of the month at 0:20
    sender.add_periodic_task(crontab(day_of_month=1, hour=0, minute=20), expire_login_history.s())
    # run once per day at 04:09
    sender.add_periodic_task(crontab(hour=4, minute=9), expire_invitations.s())


@celery_app.task
def expire_login_history():
    LoginHistory.objects.filter(
        timestamp__lt=timezone.now() - timedelta(days=365 * 5),
    ).delete()


@celery_app.task
def expire_invitations():
    Invitation.objects.filter(
        created_at__lt=timezone.now() - timedelta(days=14),
        is_used=False
    ).update(is_used=True)
