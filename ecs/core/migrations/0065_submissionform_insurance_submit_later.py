# Generated by Django 4.1.3 on 2023-02-09 23:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_submissionform_non_applicant_submitter_contact_first_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionform',
            name='insurance_submit_later',
            field=models.BooleanField(default=False),
        ),
    ]
