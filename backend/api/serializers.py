from rest_framework import serializers
from .models import WatchlistTicker, BotSession, Trade, PnLRecord, BotSettings


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
        fields = ['id', 'started_at', 'stopped_at', 'status', 'task_id', 'log', 'last_heartbeat_at', 'trades']


class PnLRecordSerializer(serializers.ModelSerializer):
    pnl_percent = serializers.SerializerMethodField()

    class Meta:
        model = PnLRecord
        fields = [
            'id', 'date', 'symbol', 'quantity', 'pnl',
            'invested_capital', 'pnl_percent', 'created_at',
        ]

    def get_pnl_percent(self, obj):
        from trading.pnl_service import invested_capital_for_pnl_record, pnl_percent

        invested = invested_capital_for_pnl_record(obj)
        pct = pnl_percent(obj.pnl, invested)
        return round(pct, 2) if pct is not None else None


class BotSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BotSettings
        fields = [
            'stop_loss_strategy',
            'risk_percent',
            'max_capital_usage_percent',
            'updated_at',
        ]
        read_only_fields = ['updated_at']

    def validate_risk_percent(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError('Risk percent must be between 1 and 10.')
        return value

    def validate_max_capital_usage_percent(self, value):
        if value not in (50, 100):
            raise serializers.ValidationError('Max capital usage must be 50 or 100.')
        return value
