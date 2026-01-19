from django.core.cache import cache
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from django.db.models.functions import Length

from .views import operator_names
from . import popular_pages


@db_periodic_task(crontab(minute=9))
def update_popular_services():
    popular_services = (
        popular_pages.get_popular_services()
        .order_by(Length("description").desc())
        .annotate(operators=operator_names)
    )
    cache.set("popular_services", popular_services, None)
