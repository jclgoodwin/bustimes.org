from django.core.management.base import BaseCommand
from ...models import Operator, Region


class Command(BaseCommand):
    @staticmethod
    def maybe_move_operator(operator, regions):
        if bool(regions) and operator.region not in regions:
            if len(regions) == 1:
                print 'moving', operator, 'from', operator.region, 'to', regions[0]
                operator.region = regions[0]
                operator.save()
            else:
                print 'consider moving', operator, 'from', operator.region, 'to', regions

    def handle(self, *args, **options):
        for operator in Operator.objects.all():
            # move Anglian Bus to the East Anglia
            regions = Region.objects.filter(service__operator=operator).distinct()
            self.maybe_move_operator(operator, regions)

            # move Cumbria to the North West
            regions = Region.objects.filter(adminarea__locality__stoppoint__service__operator=operator).distinct()
            self.maybe_move_operator(operator, regions)
