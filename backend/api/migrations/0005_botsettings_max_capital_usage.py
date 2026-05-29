from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_botsettings_risk_percent'),
    ]

    operations = [
        migrations.AddField(
            model_name='botsettings',
            name='max_capital_usage_percent',
            field=models.PositiveSmallIntegerField(
                choices=[(50, '50%'), (100, '100%')],
                default=100,
            ),
        ),
    ]
