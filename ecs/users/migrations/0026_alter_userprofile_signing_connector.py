# Generated by Django 4.1.3 on 2022-11-09 14:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0025_invite_add_is_used_index'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='signing_connector',
            field=models.CharField(choices=[('bku', 'localbku'), ('mobilebku', 'mobilebku')], default='mobilebku', max_length=9),
        ),
        migrations.RunSQL('''
            update users_userprofile set signing_connector = 'mobilebku' where signing_connector = 'onlinebku';
        ''')
    ]
