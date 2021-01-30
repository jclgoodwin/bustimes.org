import os
import ssl
from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'buses.settings')

app = Celery('vehicles')

app.config_from_object('django.conf:settings', namespace='CELERY')
if app.conf.CELERY_RESULT_BACKEND.startswith('rediss'):
    app.conf.redis_backend_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_NONE,
    }

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
