from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0006_pnlrecord_unique_date_symbol'),
    ]

    operations = [
        migrations.AddField(
            model_name='botsession',
            name='last_heartbeat_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
