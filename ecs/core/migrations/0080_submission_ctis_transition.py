# Generated by Django 4.1.3 on 2023-07-03 15:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0079_alter_submissionform_subject_divers'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='ctis_transition',
            field=models.BooleanField(default=False),
        ),
    ]
