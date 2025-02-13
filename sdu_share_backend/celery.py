import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sdu_share_backend.settings')
app = Celery('sdu_share_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()