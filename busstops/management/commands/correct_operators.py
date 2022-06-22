import yaml
from django.db.models import Count, OuterRef, Exists
from django.core.management.base import BaseCommand
from django.conf import settings
from ...models import Operator, Region, Service


def maybe_move_operator(operator, regions):
    if operator.region != regions[0]:
        if len(regions) == 1 or regions[0].services >= regions[1].services * 2:
            operator.region = regions[0]
            operator.save()
            print(f"moved {operator} to {operator.region}")
        elif operator.region_id != "GB" and operator.region_id != "NI":
            regions = [(region.id, region.services) for region in regions]
            print(f"consider moving {operator} from {operator.region} to {regions}")


class Command(BaseCommand):
    def handle(self, *args, **options):
        operator_services = Service.objects.filter(
            current=True, operator=OuterRef("pk")
        )
        operators = Operator.objects.filter(Exists(operator_services))

        for operator in operators:
            # move Cumbria to the North West
            regions = (
                Region.objects.filter(
                    adminarea__locality__stoppoint__service__current=True,
                    adminarea__locality__stoppoint__service__operator=operator,
                )
                .annotate(services=Count("adminarea__locality__stoppoint__service"))
                .order_by("-services")
                .distinct()
            )

            if not regions:
                regions = Region.objects.filter(
                    service__current=True, service__operator=operator
                )
                regions = (
                    regions.annotate(services=Count("service"))
                    .order_by("-services")
                    .distinct()
                )

            if regions:
                maybe_move_operator(operator, regions)

        with open(settings.BASE_DIR / "fixtures" / "operators.yaml") as open_file:
            records = yaml.load(open_file, Loader=yaml.BaseLoader)
            for code in records:
                Operator.objects.filter(noc=code).update(**records[code])
