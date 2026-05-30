"""
Aggregated system health checks for the Dashboard status panel.
"""
import os
import subprocess
import sys
import time
import urllib.request

import pytz
from django.utils import timezone

IST = pytz.timezone('Asia/Kolkata')

_IP_CACHE: dict = {'value': None, 'expires_at': 0.0}
_IP_CACHE_TTL_SECONDS = 300

_BROKER_ENV_KEYS = ('API_KEY', 'CLIENT_ID', 'PASSWORD', 'TOKEN')
_HEARTBEAT_STALE_SECONDS = 6 * 60


def celery_available() -> bool:
    """Return True if Redis broker is reachable for Celery."""
    if os.environ.get('USE_CELERY', 'true').lower() == 'false':
        return False
    try:
        from trademaster_project.celery import app as celery_app
        celery_app.connection().ensure_connection(max_retries=1)
        return True
    except Exception:
        return False


def _env(name: str) -> str:
    return os.environ.get(name, '').strip().strip("'\"")


def check_market() -> dict:
    now = timezone.now().astimezone(IST)
    weekday = now.weekday()

    if weekday >= 5:
        return {
            'status': 'weekend',
            'label': 'Weekend — market closed',
            'session': '09:15–15:30 IST (Mon–Fri)',
        }

    open_time = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_time = now.replace(hour=15, minute=30, second=0, microsecond=0)

    if now < open_time:
        return {
            'status': 'pre_open',
            'label': 'Pre-market',
            'session': '09:15–15:30 IST',
        }
    if now >= close_time:
        return {
            'status': 'post_close',
            'label': 'Market closed',
            'session': '09:15–15:30 IST',
        }
    return {
        'status': 'open',
        'label': 'Market open',
        'session': '09:15–15:30 IST',
    }


def check_broker(*, probe: bool = False) -> dict:
    configured = all(_env(key) for key in _BROKER_ENV_KEYS)
    result = {
        'configured': configured,
        'connected': None,
        'error': None,
        'probed': probe,
    }

    if not configured:
        missing = [key for key in _BROKER_ENV_KEYS if not _env(key)]
        result['error'] = f'Missing env: {", ".join(missing)}'
        return result

    if not probe:
        return result

    try:
        from trading.broker_cache import format_broker_error, get_angel_client

        get_angel_client()
        result['connected'] = True
    except Exception as exc:
        result['connected'] = False
        result['error'] = format_broker_error(exc)

    return result


def check_celery() -> dict:
    redis_ok = celery_available()
    worker_ok = False
    worker_count = 0

    if redis_ok:
        try:
            from trademaster_project.celery import app as celery_app
            ping = celery_app.control.inspect(timeout=2).ping() or {}
            worker_count = len(ping)
            worker_ok = worker_count > 0
        except Exception:
            worker_ok = False

    mode = 'celery' if redis_ok and worker_ok else 'local-thread'
    if not redis_ok:
        mode = 'local-thread'

    return {
        'redis_ok': redis_ok,
        'worker_ok': worker_ok,
        'worker_count': worker_count,
        'mode': mode,
    }


def check_celery_beat() -> dict:
    if sys.platform == 'win32':
        return {'ok': None, 'detail': 'N/A (local dev)'}

    try:
        proc = subprocess.run(
            ['systemctl', 'is-active', 'trademaster-celery-beat'],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        active = proc.stdout.strip() == 'active'
        return {
            'ok': active,
            'detail': proc.stdout.strip() or proc.stderr.strip() or 'unknown',
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return {'ok': None, 'detail': 'N/A (systemctl unavailable)'}


def _fetch_outbound_ip() -> str | None:
    now = time.time()
    if _IP_CACHE['value'] and now < _IP_CACHE['expires_at']:
        return _IP_CACHE['value']

    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=5) as resp:
            ip = resp.read().decode('utf-8').strip()
        _IP_CACHE['value'] = ip
        _IP_CACHE['expires_at'] = now + _IP_CACHE_TTL_SECONDS
        return ip
    except Exception:
        return None


def check_ip() -> dict:
    expected = _env('PRIMARY_STATIC_IP')
    if not expected:
        return {
            'ok': None,
            'status': 'not_configured',
            'expected': '',
            'actual': None,
            'error': 'PRIMARY_STATIC_IP not set in .env',
        }

    actual = _fetch_outbound_ip()
    if not actual:
        return {
            'ok': None,
            'status': 'unknown',
            'expected': expected,
            'actual': None,
            'error': 'Could not detect outbound IP',
        }

    ok = expected == actual
    return {
        'ok': ok,
        'status': 'ok' if ok else 'mismatch',
        'expected': expected,
        'actual': actual,
        'error': None if ok else f'Expected {expected}, server outbound IP is {actual}',
    }


def check_bot() -> dict:
    from api.models import BotSession

    running = BotSession.objects.filter(status='running').order_by('-started_at').first()
    if not running:
        last = BotSession.objects.order_by('-started_at').first()
        return {
            'is_running': False,
            'session_id': last.id if last else None,
            'last_heartbeat_at': (
                last.last_heartbeat_at.isoformat()
                if last and last.last_heartbeat_at
                else None
            ),
            'stale': False,
        }

    heartbeat = running.last_heartbeat_at
    stale = False
    if heartbeat:
        age = (timezone.now() - heartbeat).total_seconds()
        stale = age > _HEARTBEAT_STALE_SECONDS
    else:
        age = (timezone.now() - running.started_at).total_seconds()
        stale = age > _HEARTBEAT_STALE_SECONDS

    return {
        'is_running': True,
        'session_id': running.id,
        'last_heartbeat_at': heartbeat.isoformat() if heartbeat else None,
        'stale': stale,
    }


def _compute_overall(
    market: dict,
    broker: dict,
    celery: dict,
    celery_beat: dict,
    ip: dict,
    bot: dict,
) -> str:
    errors = []

    if celery['redis_ok'] and not celery['worker_ok']:
        errors.append('celery_worker')
    if ip.get('status') == 'mismatch':
        errors.append('ip')
    if broker.get('probed') and broker.get('connected') is False:
        errors.append('broker')
    if bot.get('is_running') and bot.get('stale'):
        errors.append('bot_heartbeat')
    if celery_beat.get('ok') is False:
        errors.append('celery_beat')

    if errors:
        return 'error'

    degraded = False
    if not celery['redis_ok']:
        degraded = True
    if not broker.get('probed') or broker.get('connected') is None:
        degraded = True
    if celery_beat.get('ok') is None:
        degraded = True
    if ip.get('status') in ('not_configured', 'unknown'):
        degraded = True

    return 'degraded' if degraded else 'ok'


def get_system_health(*, probe: bool = False) -> dict:
    market = check_market()
    broker = check_broker(probe=probe)
    celery = check_celery()
    celery_beat = check_celery_beat()
    ip = check_ip()
    bot = check_bot()

    return {
        'checked_at': timezone.now().isoformat(),
        'overall': _compute_overall(market, broker, celery, celery_beat, ip, bot),
        'market': market,
        'broker': broker,
        'celery': celery,
        'celery_beat': celery_beat,
        'ip': ip,
        'bot': bot,
    }
