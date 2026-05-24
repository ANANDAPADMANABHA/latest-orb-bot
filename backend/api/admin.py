from django.contrib import admin
from .models import WatchlistTicker, BotSession, Trade, PnLRecord


@admin.register(WatchlistTicker)
class WatchlistTickerAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'is_active', 'added_at']
    list_filter = ['is_active']
    search_fields = ['symbol']


@admin.register(BotSession)
class BotSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'started_at', 'stopped_at', 'task_id']
    list_filter = ['status']


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'side', 'quantity', 'entry_price', 'stop_loss', 'target', 'executed_at']
    list_filter = ['side', 'symbol']


@admin.register(PnLRecord)
class PnLRecordAdmin(admin.ModelAdmin):
    list_display = ['date', 'symbol', 'quantity', 'pnl']
    list_filter = ['date']
    ordering = ['-date']
