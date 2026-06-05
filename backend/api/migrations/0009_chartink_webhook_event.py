from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0008_pnlrecord_invested_capital'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChartinkWebhookEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('received_at', models.DateTimeField(auto_now_add=True)),
                ('scan_name', models.CharField(blank=True, max_length=120)),
                ('alert_name', models.CharField(blank=True, max_length=120)),
                ('triggered_at', models.CharField(blank=True, max_length=40)),
                ('symbol_count', models.PositiveIntegerField(default=0)),
                ('symbols_added', models.PositiveIntegerField(default=0)),
                ('symbols_skipped', models.PositiveIntegerField(default=0)),
                ('bot_session_id', models.PositiveIntegerField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('ok', 'OK'), ('error', 'Error')],
                    default='ok',
                    max_length=20,
                )),
                ('error', models.TextField(blank=True)),
                ('raw_payload', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-received_at'],
            },
        ),
    ]
