# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_remove_submissionform_medtech_is_new_law'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submissionform',
            name='is_old_medtech',
        ),
        migrations.AddField(
            model_name='submissionform',
            name='is_new_medtech_law',
            field=models.NullBooleanField(),
        ),
        migrations.RunSQL('''
            UPDATE core_submissionform SET is_new_medtech_law = false WHERE project_type_medical_device = true;
            UPDATE core_submissionform SET submission_type = 1 WHERE project_type_medical_device = true AND submission_type IS NULL;
        '''),
    ]
