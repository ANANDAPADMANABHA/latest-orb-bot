import datetime as dt

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import WatchlistTicker, BotSession, Trade, PnLRecord, BotSettings, SimulatedTrade
from .serializers import (
    WatchlistTickerSerializer,
    BotSessionSerializer,
    TradeSerializer,
    PnLRecordSerializer,
    BotSettingsSerializer,
    SimulatedTradeSerializer,
)


# ─── Watchlist ────────────────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
def watchlist(request):
    if request.method == 'GET':
        tickers = WatchlistTicker.objects.filter(is_active=True)
        return Response(WatchlistTickerSerializer(tickers, many=True).data)

    serializer = WatchlistTickerSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
def watchlist_detail(request, pk):
    try:
        ticker = WatchlistTicker.objects.get(pk=pk)
    except WatchlistTicker.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    ticker.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Bot Control ──────────────────────────────────────────────────────────────

@api_view(['GET'])
def bot_status(request):
    from trading.bot_status_service import (
        clear_stale_running_sessions,
        get_active_bot_session,
        session_is_alive,
    )

    clear_stale_running_sessions()
    active = get_active_bot_session()
    last = BotSession.objects.order_by('-started_at').first()
    settings = BotSettings.get_singleton()
    session_data = None
    display = active or last
    if display:
        session_data = BotSessionSerializer(display).data
    heartbeat_stale = False
    if active:
        heartbeat_stale = not session_is_alive(active)
    return Response({
        'is_running': active is not None,
        'heartbeat_stale': heartbeat_stale,
        'session': session_data,
        'settings': BotSettingsSerializer(settings).data,
    })


@api_view(['GET', 'PATCH'])
def bot_settings(request):
    settings = BotSettings.get_singleton()
    if request.method == 'GET':
        return Response(BotSettingsSerializer(settings).data)

    serializer = BotSettingsSerializer(settings, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def bot_start(request):
    from trading.bot_control_service import BotAlreadyRunningError, BotStartError, start_bot

    try:
        payload = start_bot()
    except BotAlreadyRunningError:
        return Response({'error': 'Bot is already running'}, status=status.HTTP_400_BAD_REQUEST)
    except BotStartError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(payload, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
def bot_stop(request):
    from trading.bot_control_service import stop_running_bot

    running = stop_running_bot()
    if not running:
        return Response({'error': 'Bot is not running'}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Bot stop requested', 'session_id': running.id})


# ─── Positions & Orders ───────────────────────────────────────────────────────

@api_view(['GET'])
def positions(request):
    """Live positions from Angel One API."""
    try:
        from trading.broker_cache import format_broker_error, get_angel_client
        client = get_angel_client()
        data = client.get_positions()
        return Response(data)
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_view(['GET'])
def orders(request):
    """Live order book from Angel One API."""
    try:
        from trading.broker_cache import format_broker_error, get_angel_client
        client = get_angel_client()
        data = client.get_order_book()
        return Response(data)
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@api_view(['GET'])
def capital(request):
    """Available trading capital from Angel One."""
    try:
        from trading.broker_cache import format_broker_error, get_angel_client
        client = get_angel_client()
        amount = client.get_trade_capital()
        return Response({'capital': amount})
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ─── P&L ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def pnl_history(request):
    from trading.pnl_service import cleanup_pnl_records

    cleanup_pnl_records()

    records = PnLRecord.objects.all()
    date_filter = request.query_params.get('date')
    if date_filter:
        records = records.filter(date=date_filter)
    return Response(PnLRecordSerializer(records, many=True).data)


@api_view(['GET'])
def pnl_today(request):
    from trading.pnl_service import cleanup_pnl_records

    cleanup_pnl_records()
    today = dt.date.today()
    records = PnLRecord.objects.filter(date=today)
    total = sum(r.pnl for r in records)
    return Response({
        'date': today.isoformat(),
        'total_pnl': total,
        'trades': PnLRecordSerializer(records, many=True).data,
    })


@api_view(['GET'])
def pnl_summary(request):
    """Aggregate daily P&L for chart."""
    from django.db.models import Sum
    from trading.pnl_service import cleanup_pnl_records

    cleanup_pnl_records()
    summary = (
        PnLRecord.objects
        .values('date')
        .annotate(total_pnl=Sum('pnl'))
        .order_by('date')
    )
    return Response(list(summary))


@api_view(['POST'])
def pnl_sync(request):
    """Pull today's P&L from Angel One positions into the database."""
    from trading.broker_cache import format_broker_error, get_angel_client
    from trading.pnl_service import cleanup_pnl_records, sync_pnl_records

    try:
        client = get_angel_client()
        rows, count = sync_pnl_records(client, replace_today=True)
        cleaned = cleanup_pnl_records()
        return Response({
            'synced': count,
            'trades': rows,
            'cleaned': cleaned,
            'message': 'No P&L rows from broker' if count == 0 else f'Synced {count} record(s)',
        })
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


# ─── Simulated Trades ────────────────────────────────────────────────────────

@api_view(['GET'])
def sim_trades(request):
    """Return simulated trades, optionally filtered by date."""
    qs = SimulatedTrade.objects.all()
    date_filter = request.query_params.get('date')
    if date_filter:
        qs = qs.filter(executed_at__date=date_filter)
    return Response(SimulatedTradeSerializer(qs, many=True).data)


@api_view(['POST'])
def sim_settle(request):
    """Settle open simulated trades using current LTP from Angel One."""
    from django.utils import timezone
    from trading.broker_cache import format_broker_error, get_angel_client

    open_trades = SimulatedTrade.objects.filter(status='open')
    if not open_trades.exists():
        return Response({'settled': 0, 'message': 'No open simulated trades to settle'})

    try:
        client = get_angel_client()
        client._load_instrument_list()
    except Exception as e:
        return Response(
            {'error': format_broker_error(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    settled = 0
    for trade in open_trades:
        try:
            ltp = client.get_ltp(client.instrument_list, trade.symbol)
            if not ltp:
                continue
            if trade.side == 'BUY':
                pnl = (ltp - trade.entry_price) * trade.quantity
            else:
                pnl = (trade.entry_price - ltp) * trade.quantity
            trade.exit_price = ltp
            trade.pnl = round(pnl, 2)
            trade.status = 'settled'
            trade.settled_at = timezone.now()
            trade.save(update_fields=['exit_price', 'pnl', 'status', 'settled_at'])
            settled += 1
        except Exception as exc:
            print(f'Failed to settle sim trade {trade.id} ({trade.symbol}): {exc}')

    return Response({'settled': settled, 'message': f'Settled {settled} simulated trade(s)'})


@api_view(['GET'])
def sim_summary(request):
    """Aggregate daily sim P&L for the chart."""
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    rows = (
        SimulatedTrade.objects
        .filter(status='settled')
        .annotate(date=TruncDate('executed_at'))
        .values('date')
        .annotate(total_pnl=Sum('pnl'), trades=Count('id'))
        .order_by('date')
    )
    return Response([
        {
            'date': r['date'].isoformat() if r['date'] else None,
            'total_pnl': round(r['total_pnl'] or 0, 2),
            'trades': r['trades'],
        }
        for r in rows
    ])


# ─── Sessions ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def sessions(request):
    from trading.bot_status_service import clear_stale_running_sessions

    clear_stale_running_sessions()
    all_sessions = BotSession.objects.all()[:20]
    return Response(BotSessionSerializer(all_sessions, many=True).data)

