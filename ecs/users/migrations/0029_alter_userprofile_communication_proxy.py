# Generated by Django 4.1.3 on 2024-05-24 12:29

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('users', '0028_alter_userprofile_organisation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='communication_proxy',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='communication_proxy_profiles', to=settings.AUTH_USER_MODEL),
        ),
    ]
