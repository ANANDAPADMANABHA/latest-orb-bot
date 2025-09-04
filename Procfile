worker: PYTHONPATH=. python -m celery -A cronjobs.celery worker --loglevel=info --pool=solo
beat: PYTHONPATH=. python -m celery -A cronjobs.celery beat --loglevel=info