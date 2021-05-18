from datetime import datetime
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from buses.utils import varnish_ban
from .models import Vehicle, Livery


@receiver(post_save, sender=Vehicle)
def vehicle_varnish_ban(sender, instance, created, **kwargs):
    if not created:
        varnish_ban(f'/vehicles/{instance.id}')


@receiver(post_save, sender=Livery)
def liveries_varnish_ban(sender, instance, **kwargs):
    cache.set('liveries_css_version', int(datetime.utcnow().timestamp()))
