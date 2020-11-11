from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from buses.utils import varnish_ban
from .models import ServiceLink


@receiver(post_save, sender=ServiceLink)
def post_save_service_link(sender, instance, **kwargs):
    cache.delete(instance.from_service.get_linked_services_cache_key())
    cache.delete(instance.from_service.get_similar_services_cache_key())
    cache.delete(instance.to_service.get_linked_services_cache_key())
    cache.delete(instance.to_service.get_similar_services_cache_key())

    varnish_ban(instance.from_service.get_absolute_url())
    varnish_ban(instance.to_service.get_absolute_url())
