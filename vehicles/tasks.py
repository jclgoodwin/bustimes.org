from celery import shared_task
from .siri_et import siri_et


@shared_task
def handle_siri_et(request_body):
    siri_et(request_body)
