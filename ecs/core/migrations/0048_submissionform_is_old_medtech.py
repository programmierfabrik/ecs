# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_auto_20220712_1540'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionform',
            name='is_old_medtech',
            field=models.NullBooleanField(),
        ),
        migrations.RunSQL('''
            UPDATE core_submissionform SET is_old_medtech = true WHERE project_type_medical_device = true and medtech_is_new_law is false;
            UPDATE core_submissionform SET submission_type = 1 WHERE project_type_medical_device = true and submission_type IS NULL;
        '''),
    ]
