from django.db import migrations, models
from django.db.models import Count


def merge_duplicate_pnl_records(apps, schema_editor):
    PnLRecord = apps.get_model('api', 'PnLRecord')
    seen = (
        PnLRecord.objects
        .values('date', 'symbol')
        .annotate(cnt=Count('id'))
        .filter(cnt__gt=1)
    )
    for entry in seen:
        dupes = list(
            PnLRecord.objects
            .filter(date=entry['date'], symbol=entry['symbol'])
            .order_by('id')
        )
        if len(dupes) < 2:
            continue
        keep = dupes[0]
        total_pnl = sum(d.pnl for d in dupes)
        max_qty = max(d.quantity for d in dupes)
        keep.pnl = total_pnl
        keep.quantity = max_qty
        keep.save(update_fields=['pnl', 'quantity'])
        PnLRecord.objects.filter(
            date=entry['date'],
            symbol=entry['symbol'],
        ).exclude(pk=keep.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_botsettings_max_capital_usage'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_pnl_records, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='pnlrecord',
            constraint=models.UniqueConstraint(
                fields=('date', 'symbol'),
                name='uniq_pnl_date_symbol',
            ),
        ),
    ]
