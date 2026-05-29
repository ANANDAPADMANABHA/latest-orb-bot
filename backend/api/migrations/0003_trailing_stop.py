from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0002_botsettings'),
    ]

    operations = [
        migrations.AlterField(
            model_name='botsettings',
            name='stop_loss_strategy',
            field=models.CharField(
                choices=[
                    ('fixed_percent', 'Fixed percent'),
                    ('prev_candle', 'Previous 5m candle'),
                    ('trailing_candle', 'Trailing stop'),
                ],
                default='fixed_percent',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='ManagedPosition',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=20)),
                ('side', models.CharField(max_length=4)),
                ('quantity', models.IntegerField()),
                ('entry_price', models.FloatField()),
                ('initial_sl', models.FloatField()),
                ('current_sl', models.FloatField()),
                ('sl_order_id', models.CharField(max_length=50)),
                ('target_order_id', models.CharField(blank=True, max_length=50)),
                ('trail_stage', models.CharField(
                    choices=[
                        ('initial', 'Initial'),
                        ('breakeven', 'Breakeven'),
                        ('trailing', 'Trailing'),
                    ],
                    default='initial',
                    max_length=20,
                )),
                ('is_active', models.BooleanField(default=True)),
                ('opened_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='managed_positions',
                    to='api.botsession',
                )),
            ],
            options={
                'ordering': ['-opened_at'],
            },
        ),
    ]
