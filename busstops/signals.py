from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import ServiceLink


@receiver(post_save, sender=ServiceLink)
def post_save_service_link(sender, instance, **kwargs):
    cache.delete(instance.from_service.get_linked_services_cache_key())
    cache.delete(instance.from_service.get_similar_services_cache_key())
    cache.delete(instance.to_service.get_linked_services_cache_key())
    cache.delete(instance.to_service.get_similar_services_cache_key())
