# Generated by Django 2.2 on 2022-07-20 11:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_auto_20220812_1750'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investigator',
            name='certified',
            field=models.BooleanField(blank=True, default=False),
        ),
        migrations.AlterField(
            model_name='investigator',
            name='jus_practicandi',
            field=models.BooleanField(blank=True, default=False),
        ),
        migrations.AlterField(
            model_name='investigator',
            name='main',
            field=models.BooleanField(blank=True, default=True),
        ),
    ]
