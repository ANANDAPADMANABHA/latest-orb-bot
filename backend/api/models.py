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
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)

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


class BotSettings(models.Model):
    STRATEGY_FIXED = 'fixed_percent'
    STRATEGY_PREV_CANDLE = 'prev_candle'
    STRATEGY_TRAILING = 'trailing_candle'
    STRATEGY_CHOICES = [
        (STRATEGY_FIXED, 'Fixed percent'),
        (STRATEGY_PREV_CANDLE, 'Previous 5m candle'),
        (STRATEGY_TRAILING, 'Trailing stop'),
    ]

    stop_loss_strategy = models.CharField(
        max_length=20,
        choices=STRATEGY_CHOICES,
        default=STRATEGY_FIXED,
    )
    risk_percent = models.PositiveSmallIntegerField(default=1)
    CAPITAL_USAGE_50 = 50
    CAPITAL_USAGE_100 = 100
    CAPITAL_USAGE_CHOICES = [
        (CAPITAL_USAGE_50, '50%'),
        (CAPITAL_USAGE_100, '100%'),
    ]
    max_capital_usage_percent = models.PositiveSmallIntegerField(
        choices=CAPITAL_USAGE_CHOICES,
        default=CAPITAL_USAGE_100,
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Bot settings — {self.stop_loss_strategy}"

    class Meta:
        verbose_name_plural = 'Bot settings'


class ManagedPosition(models.Model):
    STAGE_INITIAL = 'initial'
    STAGE_BREAKEVEN = 'breakeven'
    STAGE_TRAILING = 'trailing'
    STAGE_CHOICES = [
        (STAGE_INITIAL, 'Initial'),
        (STAGE_BREAKEVEN, 'Breakeven'),
        (STAGE_TRAILING, 'Trailing'),
    ]

    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=4)
    quantity = models.IntegerField()
    entry_price = models.FloatField()
    initial_sl = models.FloatField()
    current_sl = models.FloatField()
    sl_order_id = models.CharField(max_length=50)
    target_order_id = models.CharField(max_length=50, blank=True)
    trail_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_INITIAL)
    is_active = models.BooleanField(default=True)
    session = models.ForeignKey(
        BotSession, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_positions'
    )
    opened_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.symbol} SL={self.current_sl} ({self.trail_stage})"

    class Meta:
        ordering = ['-opened_at']


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
        constraints = [
            models.UniqueConstraint(fields=['date', 'symbol'], name='uniq_pnl_date_symbol'),
        ]
