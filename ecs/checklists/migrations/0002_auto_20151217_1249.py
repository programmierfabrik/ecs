from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('documents', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0002_auto_20151217_1249'),
        ('checklists', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='checklist',
            name='pdf_document',
            field=models.OneToOneField(related_name='checklist', null=True, to='documents.Document', on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='checklist',
            name='submission',
            field=models.ForeignKey(related_name='checklists', to='core.Submission', null=True, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='checklist',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='checklist',
            unique_together={('blueprint', 'submission', 'user')},
        ),
    ]
