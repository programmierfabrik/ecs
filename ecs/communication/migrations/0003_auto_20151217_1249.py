from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tasks', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('communication', '0002_thread_submission'),
    ]

    operations = [
        migrations.AddField(
            model_name='thread',
            name='task',
            field=models.ForeignKey(to='tasks.Task', null=True, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='receiver',
            field=models.ForeignKey(related_name='incoming_messages', to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='reply_receiver',
            field=models.ForeignKey(related_name='reply_receiver_for_messages', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='reply_to',
            field=models.ForeignKey(related_name='replies', to='communication.Message', null=True, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='sender',
            field=models.ForeignKey(related_name='outgoing_messages', to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='message',
            name='thread',
            field=models.ForeignKey(related_name='messages', to='communication.Thread', on_delete=models.PROTECT),
            preserve_default=True,
        ),
    ]
