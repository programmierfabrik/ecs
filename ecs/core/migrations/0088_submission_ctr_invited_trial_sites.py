import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0087_ctis_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='ctr_invited_trial_sites',
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.TextField(), blank=True, default=list,
                size=None),
        ),
    ]
