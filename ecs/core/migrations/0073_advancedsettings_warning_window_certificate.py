# Generated by Django 4.1.3 on 2023-03-06 08:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0072_alter_investigator_contact_gender_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='advancedsettings',
            name='warning_window_certificate',
            field=models.SmallIntegerField(choices=[(1, '1 Woche'), (2, '2 Wochen'), (3, '3 Wochen'), (4, '4 Wochen'), (5, '5 Wochen'), (6, '6 Wochen'), (7, '7 Wochen'), (8, '8 Wochen')], default=5),
        ),
    ]
