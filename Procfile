web: cd backend && gunicorn --bind 0.0.0.0:$PORT --workers 2 trademaster_project.wsgi:application
worker: cd backend && celery -A trademaster_project worker --loglevel=info --pool=solo
beat: cd backend && celery -A trademaster_project beat --loglevel=info
