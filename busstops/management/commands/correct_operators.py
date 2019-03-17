import yaml
import os
from django.db.models import Count
from django.core.management.base import BaseCommand
from django.conf import settings
from ...models import Operator, Region


DIR = os.path.dirname(__file__)


class Command(BaseCommand):
    @staticmethod
    def maybe_move_operator(operator, regions):
        if len(regions) > 0 and operator.region != regions[0]:
            if len(regions) == 1 or regions[0].services >= regions[1].services * 2:
                operator.region = regions[0]
                operator.save()
                return 'moved {} to {}'.format(operator, operator.region)
            elif operator.region_id != 'GB' and operator.region_id != 'NI':
                return 'consider moving {} from {} to {}'.format(operator, operator.region,
                                                                 [(region.id, region.services) for region in regions])

    @staticmethod
    def maybe_print(output):
        if output is not None:
            print(output)

    def handle(self, *args, **options):
        for operator in Operator.objects.filter(service__current=True).distinct().iterator():
            # move Anglian Bus to East Anglia, etc
            regions = Region.objects.filter(service__current=True, service__operator=operator)
            regions = regions.annotate(services=Count('service')).order_by('-services').distinct()
            self.maybe_print(self.maybe_move_operator(operator, regions))

            # move Cumbria to the North West
            regions = Region.objects.filter(
                adminarea__locality__stoppoint__service__current=True,
                adminarea__locality__stoppoint__service__operator=operator
            ).annotate(services=Count('adminarea__locality__stoppoint__service')).order_by('-services').distinct()
            self.maybe_print(self.maybe_move_operator(operator, regions))

        with open(os.path.join(settings.DATA_DIR, 'operators.yaml')) as open_file:
            records = yaml.load(open_file, Loader=yaml.FullLoader)
            for code in records:
                Operator.objects.filter(id=code).update(**records[code])
