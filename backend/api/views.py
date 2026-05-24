import datetime as dt
import os

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import WatchlistTicker, BotSession, Trade, PnLRecord
from .serializers import (
    WatchlistTickerSerializer,
    BotSessionSerializer,
    TradeSerializer,
    PnLRecordSerializer,
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
    return Response({
        'is_running': running is not None,
        'session': BotSessionSerializer(running or last).data if (running or last) else None,
    })


@api_view(['POST'])
def bot_start(request):
    if BotSession.objects.filter(status='running').exists():
        return Response({'error': 'Bot is already running'}, status=status.HTTP_400_BAD_REQUEST)

    from .tasks import run_trade_task
    result = run_trade_task.delay()
    return Response({'message': 'Bot started', 'task_id': result.id}, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
def bot_stop(request):
    running = BotSession.objects.filter(status='running').first()
    if not running:
        return Response({'error': 'Bot is not running'}, status=status.HTTP_400_BAD_REQUEST)

    from celery.app.control import Control
    from trademaster_project.celery import app as celery_app
    if running.task_id:
        celery_app.control.revoke(running.task_id, terminate=True)

    running.status = 'stopped'
    running.stopped_at = timezone.now()
    running.save()
    return Response({'message': 'Bot stopped'})


# ─── Positions & Orders ───────────────────────────────────────────────────────

@api_view(['GET'])
def positions(request):
    """Live positions from Angel One API."""
    try:
        from trading.broker import AngelOneClient
        client = AngelOneClient()
        client._initialize_smart_api()
        client._load_instrument_list()
        data = client.get_positions()
        return Response(data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def orders(request):
    """Live order book from Angel One API."""
    try:
        from trading.broker import AngelOneClient
        client = AngelOneClient()
        client._initialize_smart_api()
        client._load_instrument_list()
        data = client.get_order_book()
        return Response(data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def capital(request):
    """Available trading capital from Angel One."""
    try:
        from trading.broker import AngelOneClient
        client = AngelOneClient()
        client._initialize_smart_api()
        amount = client.get_trade_capital()
        return Response({'capital': amount})
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
