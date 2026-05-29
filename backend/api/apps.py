import sys

from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        # After runserver autoreload, the local bot thread is gone but the DB
        # session may still say "running". Clean that up on dev startup only.
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        from django.conf import settings
        if not settings.DEBUG:
            return
        try:
            from django.utils import timezone
            from api.models import BotSession

            stale = BotSession.objects.filter(status='running', task_id='local-thread')
            if stale.exists():
                stale.update(
                    status='stopped',
                    stopped_at=timezone.now(),
                    log='Dev server restarted while bot was running.',
                )
        except Exception:
            pass
