import logging

from celery.schedules import crontab
from celery.signals import task_failure
from django.core.management import call_command

from ecs.celery import app as celery_app

logger = logging.getLogger('task')


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # run once per day at 04:05
    sender.add_periodic_task(crontab(hour=4, minute=5), clearsessions.s())


def process_failure_signal(exception, traceback, sender, task_id, signal, args, kwargs, einfo, **kw):
    exc_info = (type(exception), exception, traceback)
    logger.error(
        str(exception),
        exc_info=exc_info,
        extra={
            'data': {
                'task_id': task_id,
                'sender': sender,
                'args': args,
                'kwargs': kwargs,
            }
        }
    )


task_failure.connect(process_failure_signal)


@celery_app.task
def clearsessions():
    call_command('clearsessions')
