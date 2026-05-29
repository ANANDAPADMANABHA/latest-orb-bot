import datetime as dt
import os
import threading

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
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
    running = BotSession.objects.filter(status='running').order_by('-started_at').first()
    last = BotSession.objects.order_by('-started_at').first()
    settings = BotSettings.get_singleton()
    return Response({
        'is_running': running is not None,
        'session': BotSessionSerializer(running or last).data if (running or last) else None,
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


def _celery_available() -> bool:
    """Return True if Redis broker is reachable for Celery."""
    if os.environ.get('USE_CELERY', 'true').lower() == 'false':
        return False
    try:
        from trademaster_project.celery import app as celery_app
        celery_app.connection().ensure_connection(max_retries=1)
        return True
    except Exception:
        return False


@api_view(['POST'])
def bot_start(request):
    if BotSession.objects.filter(status='running').exists():
        return Response({'error': 'Bot is already running'}, status=status.HTTP_400_BAD_REQUEST)

    if _celery_available():
        try:
            from .tasks import run_trade_task
            result = run_trade_task.delay()
            return Response(
                {'message': 'Bot started', 'task_id': result.id, 'mode': 'celery'},
                status=status.HTTP_202_ACCEPTED,
            )
        except Exception as exc:
            if 'redis' not in str(exc).lower() and '6379' not in str(exc):
                return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Local fallback when Redis/Celery is not running (common on Windows dev)
    from .tasks import run_trade_bot_in_thread

    session = BotSession.objects.create(status='running', task_id='local-thread')
    thread = threading.Thread(
        target=run_trade_bot_in_thread,
        args=(session.id,),
        daemon=True,
        name='trademaster-bot',
    )
    thread.start()
    return Response(
        {
            'message': 'Bot started in local mode (no Redis). Install Redis + Celery worker for production.',
            'session_id': session.id,
            'mode': 'local-thread',
        },
        status=status.HTTP_202_ACCEPTED,
    )


@api_view(['POST'])
def bot_stop(request):
    running = BotSession.objects.filter(status='running').first()
    if not running:
        return Response({'error': 'Bot is not running'}, status=status.HTTP_400_BAD_REQUEST)

    if running.task_id and running.task_id != 'local-thread':
        try:
            from trademaster_project.celery import app as celery_app
            celery_app.control.revoke(running.task_id, terminate=True)
        except Exception:
            pass
    else:
        from .tasks import request_bot_stop

        request_bot_stop()

    running.status = 'stopped'
    running.stopped_at = timezone.now()
    running.save()
    return Response({'message': 'Bot stop requested'})


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
    records = PnLRecord.objects.all()
    date_filter = request.query_params.get('date')
    if date_filter:
        records = records.filter(date=date_filter)
    return Response(PnLRecordSerializer(records, many=True).data)


@api_view(['GET'])
def pnl_today(request):
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
    from django.db.models.functions import TruncDate
    summary = (
        PnLRecord.objects
        .values('date')
        .annotate(total_pnl=Sum('pnl'))
        .order_by('date')
    )
    return Response(list(summary))


# ─── Sessions ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
def sessions(request):
    all_sessions = BotSession.objects.all()[:20]
    return Response(BotSessionSerializer(all_sessions, many=True).data)
