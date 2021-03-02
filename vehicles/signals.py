from django.db.models.signals import pre_save
from django.dispatch import receiver
from buses.utils import varnish_ban
from .models import Vehicle, Livery


@receiver(pre_save, sender=Vehicle)
def correct_vehicle_reg(sender, instance, **kwargs):
    instance.reg = instance.reg.upper().replace(' ', '')


@receiver(pre_save, sender=Vehicle)
def vehicle_varnish_ban(sender, instance, **kwargs):
    varnish_ban(f'/vehicles/{instance.id}')


@receiver(pre_save, sender=Livery)
def liveries_varnish_ban(sender, instance, **kwargs):
    varnish_ban('/liveries.css')
