# Generated by Django 2.0 on 2022-06-24 08:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0008_auto_20161122_0946'),
    ]

    operations = [
        migrations.AlterField(
            model_name='amendmentnotification',
            name='notification_ptr',
            field=models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='notifications.Notification'),
        ),
        migrations.AlterField(
            model_name='centerclosenotification',
            name='notification_ptr',
            field=models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='notifications.Notification'),
        ),
        migrations.AlterField(
            model_name='completionreportnotification',
            name='notification_ptr',
            field=models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='notifications.Notification'),
        ),
        migrations.AlterField(
            model_name='progressreportnotification',
            name='notification_ptr',
            field=models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='notifications.Notification'),
        ),
        migrations.AlterField(
            model_name='safetynotification',
            name='notification_ptr',
            field=models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='notifications.Notification'),
        ),
    ]