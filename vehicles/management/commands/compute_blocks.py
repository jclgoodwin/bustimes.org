from django.core.management.base import BaseCommand
from django.db.models import Q
from sql_util.utils import Exists

from bustimes.models import Trip

from ...models import Vehicle


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("operator_code", type=str)
        parser.add_argument("yesterday", type=str)
        parser.add_argument("before_yesterday", type=str)

    def handle(self, operator_code, yesterday, before_yesterday, **options):
        vehicles = Vehicle.objects.filter(operator=operator_code)

        block_number = 1

        Trip.objects.filter(operator=operator_code).update(block="")

        for v in vehicles.filter(
            Exists("vehiclejourney", filter=Q(datetime__date=yesterday))
        ):
            journeys = v.vehiclejourney_set.filter(date=yesterday)
            trip_ids = [j.trip_id for j in journeys]
            if trip_ids[0]:
                for previous_vehicle in vehicles.filter(
                    Exists(
                        "vehiclejourney",
                        filter=Q(date=before_yesterday, trip=trip_ids[0]),
                    )
                ):
                    previous_journeys = previous_vehicle.vehiclejourney_set.filter(
                        date=yesterday
                    )
                    previous_trip_ids = [j.trip_id for j in previous_journeys]

                    print(trip_ids)
                    print(previous_trip_ids)
                    if trip_ids == previous_trip_ids:
                        Trip.objects.filter(id__in=trip_ids).update(block=block_number)
                        block_number += 1
