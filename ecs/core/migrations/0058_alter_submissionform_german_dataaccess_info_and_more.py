# Generated by Django 4.1.3 on 2023-02-02 13:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0057_add_subject_noncompetents_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submissionform',
            name='german_dataaccess_info',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='submissionform',
            name='german_dataprotection_info',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='submissionform',
            name='german_financing_info',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='submissionform',
            name='project_type_education_context',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Dissertation'), (2, 'Diplomarbeit'), (3, 'Bachelorarbeit'), (4, 'Masterarbeit'), (5, 'PhD-Arbeit')], null=True),
        ),
    ]