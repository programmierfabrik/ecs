from django.utils import timezone
from django.utils.translation import gettext as _
from django.db.models.expressions import RawSQL

from celery.schedules import crontab

from ecs.communication.utils import send_message_template
from ecs.tasks.models import Task
from ecs.users.utils import get_user
from ecs.celery import app as celery_app


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # run once per hour at minute 0 of hour
    sender.add_periodic_task(crontab(minute=0), send_reminder_messages.s())


def send_task_message(task, subject, template, extra_ctx={}):
    if task.content_type.natural_key() == ('core', 'submission'):
        submission = task.data
    elif task.content_type.natural_key() == ('checklists', 'checklist'):
        submission = task.data.submission
    else:
        assert False

    subject = subject.format(task=task.task_type)
    template = 'tasks/messages/{}'.format(template)
    ctx = {'task': task}
    ctx.update(extra_ctx)

    send_message_template(get_user('root@system.local'), task.created_by,
                          subject, template, ctx, submission=submission)


def send_close_message(task):
    send_task_message(task, _('{task} completed'), 'completed.txt')


def send_delete_message(task, user):
    send_task_message(task, _('{task} deleted'), 'deleted.txt', {'user': user})


@celery_app.task
def send_reminder_messages():
    now = timezone.now()
    tasks = (Task.objects.open()
             .filter(reminder_message_sent_at=None,
                     reminder_message_timeout__isnull=False)
             .annotate(deadline=RawSQL('created_at + reminder_message_timeout', ()))
             .filter(deadline__lt=now))

    for task in tasks:
        send_task_message(task, _('{task} still open'), 'still_open.txt')

        task.reminder_message_sent_at = now
        task.save(update_fields=('reminder_message_sent_at',))
