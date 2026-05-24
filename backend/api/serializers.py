from rest_framework import serializers
from .models import WatchlistTicker, BotSession, Trade, PnLRecord


class WatchlistTickerSerializer(serializers.ModelSerializer):
    class Meta:
        model = WatchlistTicker
        fields = ['id', 'symbol', 'added_at', 'is_active']
        read_only_fields = ['id', 'added_at']

    def validate_symbol(self, value):
        return value.strip().upper()


class TradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trade
        fields = ['id', 'symbol', 'side', 'quantity', 'entry_price', 'stop_loss', 'target', 'order_id', 'executed_at']


class BotSessionSerializer(serializers.ModelSerializer):
    trades = TradeSerializer(many=True, read_only=True)

    class Meta:
        model = BotSession
        fields = ['id', 'started_at', 'stopped_at', 'status', 'task_id', 'log', 'trades']


class PnLRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = PnLRecord
        fields = ['id', 'date', 'symbol', 'quantity', 'pnl', 'created_at']
