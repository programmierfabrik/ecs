# Generated by Django 4.1.3 on 2023-02-10 11:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_submissionform_insurance_submit_later'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investigator',
            name='organisation',
            field=models.TextField(),
        ),
    ]
