from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0009_chartink_webhook_event'),
    ]

    operations = [
        migrations.AddField(
            model_name='botsettings',
            name='paper_mode',
            field=models.BooleanField(
                default=False,
                help_text='When enabled the bot detects signals and logs simulated trades without placing real orders.',
            ),
        ),
        migrations.CreateModel(
            name='SimulatedTrade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=20)),
                ('side', models.CharField(choices=[('BUY', 'Buy'), ('SELL', 'Sell')], max_length=4)),
                ('quantity', models.IntegerField()),
                ('entry_price', models.FloatField()),
                ('stop_loss', models.FloatField()),
                ('target', models.FloatField()),
                ('exit_price', models.FloatField(blank=True, null=True)),
                ('pnl', models.FloatField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[('open', 'Open'), ('settled', 'Settled')],
                    default='open',
                    max_length=10,
                )),
                ('executed_at', models.DateTimeField(auto_now_add=True)),
                ('settled_at', models.DateTimeField(blank=True, null=True)),
                ('session', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='simulated_trades',
                    to='api.botsession',
                )),
            ],
            options={
                'ordering': ['-executed_at'],
            },
        ),
    ]
