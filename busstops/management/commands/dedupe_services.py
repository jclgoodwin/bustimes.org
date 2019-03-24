from django.core.management.base import BaseCommand
from ...models import Service


class Command(BaseCommand):
    def handle(self, *args, **options):
        # services = Service.objects.annotate(operators=Count('operator')).filter(current=True, operators=1)
        # for service in services:
        #     doppelgangers = services.filter(line_name=service.line_name, operator=service.operator.first(),
        #                                     description=service.description).exclude(pk=service.pk)
        #     if doppelgangers.exists():
        #         print(doppelgangers)

        services = Service.objects.filter(current=True, operator__in=['SCCO', 'SCHM'])
        for service in services:
            doppelgangers = services.filter(line_name=service.line_name,
                                            description=service.description).exclude(pk=service.pk)
            if doppelgangers.exists():
                for doppelganger in doppelgangers:
                    print(doppelganger.get_absolute_url())
                    print(doppelganger.journey_set.count())
                    if service.slug == service.pk.lower() or doppelganger.slug != doppelganger.pk.lower():
                        service.current = False
                        service.save()
                print(service.get_absolute_url())
                print(service.journey_set.count())
                print('')
