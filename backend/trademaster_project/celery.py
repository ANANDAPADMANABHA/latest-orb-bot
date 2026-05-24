import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trademaster_project.settings')

app = Celery('trademaster_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'run-orb-bot-weekdays-0920': {
        'task': 'api.tasks.run_trade_task',
        'schedule': crontab(hour=9, minute=20, day_of_week='mon-fri'),
    },
}
