import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trademaster_project.settings')

app = Celery('trademaster_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


beat_schedule = {
    'cleanup-orphan-orders-every-2-min': {
        'task': 'api.tasks.cleanup_orphan_orders_periodic',
        'schedule': 120.0,
    },
}

if _env_bool('BOT_AUTO_START_0920', False):
    beat_schedule['run-orb-bot-weekdays-0920'] = {
        'task': 'api.tasks.run_trade_task',
        'schedule': crontab(hour=9, minute=20, day_of_week='mon-fri'),
    }

app.conf.beat_schedule = beat_schedule
