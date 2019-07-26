from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import Vehicle


@receiver(pre_save, sender=Vehicle)
def correct_vehicle_reg(sender, instance, **kwargs):
    instance.reg = instance.reg.upper().replace(' ', '')
