# Generated by Django 4.1.3 on 2023-07-03 12:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0009_auto_20220624_0834'),
    ]

    operations = [
        migrations.CreateModel(
            name='CTISTransitionNotification',
            fields=[
                ('notification_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='notifications.notification')),
                ('eu_ct_number', models.TextField()),
            ],
            bases=('notifications.notification',),
        ),
    ]
