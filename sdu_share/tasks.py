# tasks.py
from celery import shared_task

@shared_task
def clean_blacklist():
    from .models import BlacklistedAccessToken
    BlacklistedAccessToken.clean_expired()