# Generated by Django 4.1.3 on 2023-02-09 05:47

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_submissionform_submitter_phone_number'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submissionform',
            name='submitter_is_authorized_by_sponsor',
        ),
        migrations.RemoveField(
            model_name='submissionform',
            name='submitter_is_coordinator',
        ),
        migrations.RemoveField(
            model_name='submissionform',
            name='submitter_is_main_investigator',
        ),
        migrations.RemoveField(
            model_name='submissionform',
            name='submitter_is_sponsor',
        ),
    ]
