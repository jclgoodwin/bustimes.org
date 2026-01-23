from django.core.cache import cache
from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from django.db.models.functions import Coalesce, Length
from django.contrib.postgres.aggregates import StringAgg

from .views import operator_names
from . import popular_pages


@db_periodic_task(crontab(minute=9))
def update_popular_services():
    popular_services = (
        popular_pages.get_popular_services()
        .annotate(
            line_names_str=StringAgg(Coalesce("route__line_name", "line_name"), " "),
            operators=operator_names,
        )
        .order_by(
            (
                Length("line_names_str") + Length("line_brand") + Length("description")
            ).desc()
        )
    )
    cache.set("popular_services", popular_services, None)
