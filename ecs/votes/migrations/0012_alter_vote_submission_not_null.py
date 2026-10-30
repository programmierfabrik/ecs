import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0086_ctrsubmissionform_submission_current_ctr_form'),
        ('votes', '0011_backfill_vote_submission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vote',
            name='submission',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='votes', to='core.submission'),
        ),
    ]
