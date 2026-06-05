import datetime as dt

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import WatchlistTicker, BotSession, Trade, PnLRecord, BotSettings
from .serializers import (
    WatchlistTickerSerializer,
    BotSessionSerializer,
    TradeSerializer,
    PnLRecordSerializer,
    BotSettingsSerializer,
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


# ─── Sessions ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def sessions(request):
    from trading.bot_status_service import clear_stale_running_sessions

    clear_stale_running_sessions()
    all_sessions = BotSession.objects.all()[:20]
    return Response(BotSessionSerializer(all_sessions, many=True).data)


# ─── System health ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def system_health(request):
    from trading.health_service import get_system_health

    probe = request.query_params.get('probe') == '1'
    return Response(get_system_health(probe=probe))
