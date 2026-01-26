from django.core.cache import cache
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from django.db.models import Value
from django.db.models.aggregates import StringAgg

from .views import operator_names
from . import popular_pages


@db_periodic_task(crontab(minute=9))
def update_popular_services():
    popular_services = (
        popular_pages.get_popular_services()
        .annotate(
            line_names_str=StringAgg(
                "route__line_name", Value("  "), default="line_name", distinct=True
            ),
            operators=operator_names,
        )
        .order_by("?")
    )[:10]

    # sort by string length for aesthetics
    popular_services = list(popular_services)
    popular_services.sort(key=popular_pages.Service.__str__)

    cache.set("popular_services", popular_services, None)
