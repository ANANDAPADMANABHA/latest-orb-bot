"""
Resolve whether the trading bot is actually running (DB + heartbeat + Celery).
"""
from __future__ import annotations

import datetime as dt

from django.utils import timezone

# Loop runs every ~5 min; sync-to-candle can sleep up to ~5 min before first pass.
HEARTBEAT_STALE_SECONDS = 7 * 60
STARTUP_WARMUP_SECONDS = 10 * 60


def _heartbeat_age_seconds(session, now) -> float | None:
    if session.last_heartbeat_at:
        return (now - session.last_heartbeat_at).total_seconds()
    return None


def session_is_alive(session, now=None) -> bool:
    """True if this session likely has a live worker loop."""
    now = now or timezone.now()
    age = _heartbeat_age_seconds(session, now)
    if age is not None:
        return age <= HEARTBEAT_STALE_SECONDS
    uptime = (now - session.started_at).total_seconds()
    return uptime <= STARTUP_WARMUP_SECONDS


def _celery_active_session_id() -> int | None:
    try:
        from api.models import BotSession
        from trading.health_service import celery_available

        if not celery_available():
            return None
        from trademaster_project.celery import app as celery_app

        inspect = celery_app.control.inspect(timeout=2)
        if not inspect:
            return None
        active = inspect.active() or {}
        for tasks in active.values():
            for task in tasks:
                name = task.get('name') or ''
                if 'run_trade_task' not in name:
                    continue
                kwargs = task.get('kwargs') or {}
                if isinstance(kwargs, dict) and kwargs.get('session_id') is not None:
                    return int(kwargs['session_id'])
                args = task.get('args') or []
                if args:
                    return int(args[0])
                celery_id = task.get('id')
                if celery_id:
                    match = BotSession.objects.filter(task_id=celery_id).first()
                    if match:
                        return match.id
    except Exception:
        pass
    return None


def _repair_session_running(session) -> None:
    if session.status != 'running':
        session.status = 'running'
        session.stopped_at = None
        session.save(update_fields=['status', 'stopped_at'])


def get_active_bot_session():
    """
  Return the BotSession that should be treated as running, or None.
  Repairs DB when Celery/heartbeat show activity but status was cleared.
    """
    from api.models import BotSession

    now = timezone.now()

    celery_sid = _celery_active_session_id()
    if celery_sid:
        session = BotSession.objects.filter(pk=celery_sid).first()
        if session:
            _repair_session_running(session)
            return session

    running_qs = BotSession.objects.filter(status='running').order_by('-started_at')
    alive_running = None
    for running in running_qs:
        if session_is_alive(running, now):
            if alive_running is None:
                alive_running = running
            continue
        running.status = 'stopped'
        running.stopped_at = now
        running.log = (running.log or '') + '\nHeartbeat timeout.'
        running.save(update_fields=['status', 'stopped_at', 'log'])
    if alive_running:
        return alive_running

    recent = (
        BotSession.objects.filter(last_heartbeat_at__isnull=False)
        .order_by('-last_heartbeat_at')
        .first()
    )
    if recent and session_is_alive(recent, now):
        _repair_session_running(recent)
        return recent

    return None


def bot_is_running() -> bool:
    return get_active_bot_session() is not None


def clear_stale_running_sessions() -> int:
    """Mark abandoned running rows stopped (worker died)."""
    from api.models import BotSession
    from django.db.models import Q

    now = timezone.now()
    stuck = BotSession.objects.filter(status='running').filter(
        Q(last_heartbeat_at__lt=now - dt.timedelta(seconds=HEARTBEAT_STALE_SECONDS))
        | Q(
            last_heartbeat_at__isnull=True,
            started_at__lt=now - dt.timedelta(seconds=STARTUP_WARMUP_SECONDS),
        )
    )
    count = stuck.count()
    if count:
        stuck.update(
            status='stopped',
            stopped_at=now,
            log='Stale session cleared (no heartbeat).',
        )
    return count
