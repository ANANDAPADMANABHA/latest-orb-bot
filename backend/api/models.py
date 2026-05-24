from django.db import models


class WatchlistTicker(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    added_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.symbol

    class Meta:
        ordering = ['symbol']


class BotSession(models.Model):
    STATUS_CHOICES = [
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    ]
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    task_id = models.CharField(max_length=100, blank=True)
    log = models.TextField(blank=True)

    def __str__(self):
        return f"Session {self.id} — {self.status} @ {self.started_at:%Y-%m-%d %H:%M}"

    class Meta:
        ordering = ['-started_at']


class Trade(models.Model):
    SIDE_CHOICES = [('BUY', 'Buy'), ('SELL', 'Sell')]

    session = models.ForeignKey(BotSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='trades')
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.IntegerField()
    entry_price = models.FloatField()
    stop_loss = models.FloatField()
    target = models.FloatField()
    order_id = models.CharField(max_length=50, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.quantity} x {self.symbol} @ {self.entry_price}"

    class Meta:
        ordering = ['-executed_at']


class PnLRecord(models.Model):
    date = models.DateField()
    symbol = models.CharField(max_length=20)
    quantity = models.IntegerField(default=0)
    pnl = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} | {self.symbol} | PnL: {self.pnl}"

    class Meta:
        ordering = ['-date', 'symbol']
