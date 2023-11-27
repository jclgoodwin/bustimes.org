from django.core.cache import cache
from django.db.models import Max
from django.utils.functional import lazy

from .models import Livery


def _liveries_css_version():
    version = cache.get("liveries_css_version")
    if not version:
        version = Livery.objects.aggregate(Max("updated_at"))["updated_at__max"]
        if version:
            version = int(version.timestamp())
            cache.set("liveries_css_version", version, None)
    return version


def liveries_css_version(request):
    return {"liveries_css_version": lazy(_liveries_css_version)}
