# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0004_uuidfield'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='documenttype',
            name='helptext',
        ),
    ]
