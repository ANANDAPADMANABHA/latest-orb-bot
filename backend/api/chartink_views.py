import json
import os

from django.http import Http404
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.models import ChartinkWebhookEvent
from trading.chartink_service import parse_chartink_stocks, process_chartink_payload


def _configured_secret() -> str:
    return os.environ.get('CHARTINK_WEBHOOK_SECRET', '').strip()


def _chartink_enabled() -> bool:
    raw = os.environ.get('CHARTINK_WEBHOOK_ENABLED', 'true').strip().lower()
    return raw in ('1', 'true', 'yes', 'on') and bool(_configured_secret())


def _verify_secret(secret: str) -> None:
    expected = _configured_secret()
    if not expected or secret != expected:
        raise Http404()


def _parse_payload(request) -> dict:
    if hasattr(request, 'data') and request.data:
        if isinstance(request.data, dict):
            return request.data
        if isinstance(request.data, str):
            try:
                return json.loads(request.data)
            except json.JSONDecodeError:
                return {}
    body = request.body
    if not body:
        return {}
    try:
        return json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _log_event(payload: dict, result: dict) -> ChartinkWebhookEvent:
    raw = json.dumps(payload, default=str)
    if len(raw) > 8000:
        raw = raw[:8000] + '...'
    return ChartinkWebhookEvent.objects.create(
        scan_name=result.get('scan_name') or str(payload.get('scan_name') or ''),
        alert_name=result.get('alert_name') or str(payload.get('alert_name') or ''),
        triggered_at=result.get('triggered_at') or str(payload.get('triggered_at') or ''),
        symbol_count=result.get('symbols_received', len(parse_chartink_stocks(payload.get('stocks') or ''))),
        symbols_added=result.get('symbols_added', 0),
        symbols_skipped=result.get('symbols_skipped', 0),
        bot_session_id=result.get('session_id'),
        status=ChartinkWebhookEvent.STATUS_OK if result.get('ok') else ChartinkWebhookEvent.STATUS_ERROR,
        error=result.get('error') or '',
        raw_payload=raw,
    )


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def chartink_webhook(request, secret: str):
    """Chartink alert webhook — replace watchlist and start bot."""
    if not _chartink_enabled():
        raise Http404()
    _verify_secret(secret)

    payload = _parse_payload(request)
    if not payload.get('stocks'):
        result = {
            'ok': False,
            'error': 'Missing stocks field in payload',
            'symbols_received': 0,
            'symbols_added': 0,
            'symbols_skipped': 0,
            'bot_started': False,
            'session_id': None,
        }
        _log_event(payload, result)
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = process_chartink_payload(payload)
    except Exception as exc:
        result = {
            'ok': False,
            'error': str(exc),
            'symbols_received': len(parse_chartink_stocks(payload.get('stocks') or '')),
            'symbols_added': 0,
            'symbols_skipped': 0,
            'bot_started': False,
            'session_id': None,
            'scan_name': payload.get('scan_name'),
            'alert_name': payload.get('alert_name'),
        }
        _log_event(payload, result)
        return Response(result, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    _log_event(payload, result)
    code = status.HTTP_200_OK if result.get('ok') else status.HTTP_422_UNPROCESSABLE_ENTITY
    return Response(result, status=code)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chartink_webhook_config(request):
    """Return webhook URL for Chartink alert setup (authenticated)."""
    secret = _configured_secret()
    enabled = _chartink_enabled()
    webhook_url = None
    if enabled:
        webhook_url = request.build_absolute_uri(f'/api/webhooks/chartink/{secret}/')

    auto_start_0920 = os.environ.get('BOT_AUTO_START_0920', 'false').strip().lower() in (
        '1', 'true', 'yes', 'on',
    )

    return Response({
        'enabled': enabled,
        'webhook_url': webhook_url,
        'auto_start_0920': auto_start_0920,
        'instructions': (
            'In Chartink: Create/Modify Alert on your scanner → set schedule to '
            'weekdays 11:00 AM IST → paste the webhook URL above.'
        ),
    })
