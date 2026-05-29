from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='BotSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stop_loss_strategy', models.CharField(
                    choices=[
                        ('fixed_percent', 'Fixed percent'),
                        ('prev_candle', 'Previous 5m candle'),
                    ],
                    default='fixed_percent',
                    max_length=20,
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Bot settings',
            },
        ),
    ]
