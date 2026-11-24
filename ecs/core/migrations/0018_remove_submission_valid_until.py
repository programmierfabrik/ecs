# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_advancedsettings_display_notifications_in_protocol'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='submission',
            name='valid_until',
        ),
    ]
