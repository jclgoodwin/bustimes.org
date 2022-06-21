from django.core.management.base import BaseCommand
from ...models import Service


class Command(BaseCommand):
    def handle(self, *args, **options):

        services = Service.objects.filter(current=True, operator="STWS")

        for service in services:
            doppelgangers = services.filter(
                line_name__iexact=service.line_name, description=service.description
            ).exclude(pk=service.pk)
            if doppelgangers:
                print(service, doppelgangers)
                for doppelganger in doppelgangers:
                    print(doppelganger.route_set.update(service=service))
                    print(doppelganger.vehiclejourney_set.update(service=service))
                    print(doppelganger.stopusage_set.update(service=service))
                print(doppelgangers.update(current=False))
