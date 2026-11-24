from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_uuidfield'),
    ]

    operations = [
        migrations.RunSQL('''
            drop table if exists
                djcelery_crontabschedule,
                djcelery_intervalschedule,
                djcelery_periodictask,
                djcelery_periodictasks,
                djcelery_taskstate,
                djcelery_workerstate;
        ''')
    ]
