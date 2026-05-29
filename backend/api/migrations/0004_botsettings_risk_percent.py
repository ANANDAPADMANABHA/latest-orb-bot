from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_trailing_stop'),
    ]

    operations = [
        migrations.AddField(
            model_name='botsettings',
            name='risk_percent',
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
