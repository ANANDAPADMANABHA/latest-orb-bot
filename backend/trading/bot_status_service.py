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


def _canonical_running_session_id(now=None) -> int | None:
    """The one running row that matches a live worker, if any."""
    from api.models import BotSession

    now = now or timezone.now()
    celery_sid = _celery_active_session_id()
    if celery_sid:
        return celery_sid
    for session in BotSession.objects.filter(status='running').order_by('-started_at'):
        if session_is_alive(session, now):
            return session.id
    return None


def get_active_bot_session():
    """
  Return the BotSession that should be treated as running, or None.
  Repairs DB when Celery/heartbeat show activity but status was cleared.
    """
    from api.models import BotSession

    now = timezone.now()
    clear_stale_running_sessions(now=now)

    celery_sid = _celery_active_session_id()
    if celery_sid:
        session = BotSession.objects.filter(pk=celery_sid).first()
        if session:
            _repair_session_running(session)
            _stop_duplicate_running_sessions(now=now, keep_id=celery_sid)
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
        _stop_duplicate_running_sessions(now=now, keep_id=alive_running.id)
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


def _stop_duplicate_running_sessions(now, keep_id: int) -> int:
    """Only one session may be running in the DB."""
    from api.models import BotSession

    extras = BotSession.objects.filter(status='running').exclude(pk=keep_id)
    count = extras.count()
    if count:
        extras.update(
            status='stopped',
            stopped_at=now,
            log='Stopped: superseded by another bot session.',
        )
    return count


def clear_stale_running_sessions(now=None) -> int:
    """Mark abandoned running rows stopped; dedupe to a single running row."""
    from api.models import BotSession
    from django.db.models import Q

    now = now or timezone.now()
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

    running = BotSession.objects.filter(status='running').order_by('-started_at')
    if running.count() <= 1:
        return count

    keep_id = _canonical_running_session_id(now)
    if keep_id is None:
        keep_id = running.first().id
    count += _stop_duplicate_running_sessions(now, keep_id)
    return count
