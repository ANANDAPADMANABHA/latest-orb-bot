"""Start/stop bot — shared by API views and Chartink webhook."""
from __future__ import annotations

import threading

from django.utils import timezone

from trading.health_service import celery_available


class BotAlreadyRunningError(Exception):
    pass


class BotStartError(Exception):
    pass


def stop_running_bot():
    """Stop the active bot session if any. Returns the stopped session or None."""
    from api.models import BotSession

    running = BotSession.objects.filter(status='running').order_by('-started_at').first()
    if not running:
        return None

    running.status = 'stopped'
    running.stopped_at = timezone.now()
    running.save(update_fields=['status', 'stopped_at'])

    if running.task_id and running.task_id != 'local-thread':
        try:
            from trademaster_project.celery import app as celery_app

            celery_app.control.revoke(running.task_id, terminate=True)
        except Exception:
            pass
    else:
        from api.tasks import request_bot_stop

        request_bot_stop()

    return running


def start_bot(*, allow_if_running: bool = False) -> dict:
    """
    Start a new bot session. Raises BotAlreadyRunningError or BotStartError.
    """
    from api.models import BotSession
    from trading.bot_status_service import bot_is_running, clear_stale_running_sessions

    clear_stale_running_sessions()
    if bot_is_running() and not allow_if_running:
        raise BotAlreadyRunningError('Bot is already running')

    if celery_available():
        from trading.health_service import celery_worker_available

        worker_ok = celery_worker_available()
        session = BotSession.objects.create(status='running', task_id='')
        try:
            from api.tasks import run_trade_task

            result = run_trade_task.delay(session_id=session.id)
            session.task_id = result.id or ''
            session.save(update_fields=['task_id'])
        except Exception as exc:
            session.status = 'error'
            session.log = str(exc)
            session.stopped_at = timezone.now()
            session.save()
            raise BotStartError(str(exc)) from exc

        payload = {
            'message': 'Bot started',
            'task_id': session.task_id,
            'session_id': session.id,
            'mode': 'celery',
            'is_running': True,
        }
        if not worker_ok:
            payload['warning'] = (
                'Task was queued but no Celery worker responded. '
                'On the server run: sudo systemctl start trademaster-celery '
                'and check: sudo journalctl -u trademaster-celery -f'
            )
        return payload

    from api.tasks import run_trade_bot_in_thread

    session = BotSession.objects.create(status='running', task_id='local-thread')
    thread = threading.Thread(
        target=run_trade_bot_in_thread,
        args=(session.id,),
        daemon=True,
        name='trademaster-bot',
    )
    thread.start()
    return {
        'message': 'Bot started in local mode (no Redis). Install Redis + Celery worker for production.',
        'session_id': session.id,
        'mode': 'local-thread',
        'is_running': True,
    }
