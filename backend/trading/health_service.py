"""
Celery availability checks used by bot start/stop and status repair.
"""
import os


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


def celery_worker_available() -> bool:
    """True if at least one Celery worker is connected (not just Redis)."""
    if not celery_available():
        return False
    try:
        from trademaster_project.celery import app as celery_app
        inspect = celery_app.control.inspect(timeout=3)
        if not inspect:
            return False
        ping = inspect.ping() or {}
        if ping:
            return True
        # solo pool workers sometimes miss ping; stats() is more reliable
        stats = inspect.stats() or {}
        return len(stats) > 0
    except Exception:
        return False
