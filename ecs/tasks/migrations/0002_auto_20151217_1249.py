from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0003_auto_20151217_1249'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workflow', '0001_initial'),
        ('tasks', '0001_initial'),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tasktype',
            name='workflow_node',
            field=models.OneToOneField(null=True, to='workflow.Node', on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='assigned_to',
            field=models.ForeignKey(related_name='tasks', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='content_type',
            field=models.ForeignKey(to='contenttypes.ContentType', null=True, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='created_by',
            field=models.ForeignKey(related_name='created_tasks', to=settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='expedited_review_categories',
            field=models.ManyToManyField(to='core.ExpeditedReviewCategory'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='task_type',
            field=models.ForeignKey(related_name='tasks', to='tasks.TaskType', on_delete=models.PROTECT),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='task',
            name='workflow_token',
            field=models.OneToOneField(related_name='task', null=True, to='workflow.Token', on_delete=models.PROTECT),
            preserve_default=True,
        ),
    ]
