from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Livery


@receiver(post_save, sender=Livery)
def liveries_cache_update(sender, instance, **kwargs):
    cache.set("liveries_css_version", int(instance.updated_at.timestamp()), None)
