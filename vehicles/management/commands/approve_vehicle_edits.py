from django.core.management.base import BaseCommand
from ...models import VehicleEdit


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        for ve in VehicleEdit.objects.filter(approved=None):
            if not ve.get_changes():
                print(ve)
                ve.approved = True
                ve.save(update_fields=['approved'])
