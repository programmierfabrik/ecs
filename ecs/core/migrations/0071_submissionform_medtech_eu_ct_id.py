# Generated by Django 4.1.3 on 2023-02-21 16:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_investigatoremployee_suffix_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='submissionform',
            name='medtech_eu_ct_id',
            field=models.TextField(blank=True),
        ),
    ]