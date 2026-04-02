from django.core.cache import cache
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from .views import operator_names
from . import popular_pages


@db_periodic_task(crontab(minute=9))
def update_popular_services():
    popular_services = (
        popular_pages.get_popular_services()
        .annotate(
            operators=operator_names,
        )
        .order_by("?")
    )[:10]

    # sort by string length for aesthetics
    popular_services = list(popular_services)
    popular_services.sort(key=lambda service: len(str(service)))

    cache.set("popular_services", popular_services, None)
