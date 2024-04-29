import os

from django.conf import settings
from django.core.management import call_command

from ecs import bootstrap
from ecs import workflow

@bootstrap.register()
def workflow_sync():
    workflow.autodiscover()
    call_command('workflow_sync', quiet=True)

@bootstrap.register()
def create_settings_dirs():
    os.makedirs(os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, 'submission-preview'), exist_ok=True)
    os.makedirs(os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, 'xls-export'), exist_ok=True)
    os.makedirs(os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, 'english-vote'), exist_ok=True)

@bootstrap.register()
def compilemessages():
    call_command('compilemessages')
