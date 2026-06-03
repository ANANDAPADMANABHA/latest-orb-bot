from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0007_botsession_last_heartbeat_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='pnlrecord',
            name='invested_capital',
            field=models.FloatField(
                blank=True,
                help_text='Capital deployed for this trade (for P&L %).',
                null=True,
            ),
        ),
    ]
