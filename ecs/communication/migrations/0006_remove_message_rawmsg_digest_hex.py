from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('communication', '0005_uuidfield'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='message',
            name='rawmsg_digest_hex',
        ),
    ]
