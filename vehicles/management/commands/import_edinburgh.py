from datetime import datetime, timedelta

from django.utils import timezone
from django.contrib.gis.geos import Point
from django.db.models import Exists, OuterRef

from busstops.models import Service
from bustimes.models import Trip, StopTime, get_calendars
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    url = 'http://tfe-opendata.com/api/v1/vehicle_locations'
    source_name = 'TfE'
    services = Service.objects.filter(
        operator__in=('LOTH', 'EDTR', 'ECBU', 'NELB'),
        current=True
    ).defer('geometry', 'search_vector')

    @staticmethod
    def get_datetime(item):
        if item['ineo_gps_fix'] - item['last_gps_fix'] == 3600:
            return datetime.fromtimestamp(item['ineo_gps_fix'], timezone.utc)
        return datetime.fromtimestamp(item['last_gps_fix'], timezone.utc)

    def get_items(self):
        items = super().get_items()
        return items['vehicles']

    def get_vehicle(self, item):
        if item['longitude'] == -7.557172 and item['latitude'] == 49.7668:
            return None, None

        vehicle_defaults = {
            'operator_id': 'LOTH'
        }
        vehicle_code = item['vehicle_id']
        if vehicle_code.isdigit():
            vehicle_defaults['fleet_number'] = vehicle_code

        return self.vehicles.get_or_create(
            vehicle_defaults,
            source=self.source,
            code=vehicle_code
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            code=item['journey_id'] or '',
            destination=item['destination'] or ''
        )

        journey.route_name = item['service_name'] or ''

        if not journey.route_name:
            pass
        elif vehicle.latest_journey and vehicle.latest_journey.route_name == journey.route_name:
            journey.service_id = vehicle.latest_journey.service_id
        else:
            try:
                journey.service = self.services.get(line_name__iexact=journey.route_name)
                if journey.service:
                    operator = journey.service.operator.first()
                    if not vehicle.operator_id or vehicle.operator_id != operator.id:
                        vehicle.operator = operator
                        vehicle.save(update_fields=['operator'])
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item['service_name'])

        if vehicle.latest_journey and vehicle.latest_journey.code == journey.code:
            pass
        elif item['next_stop_id'] and journey.service_id:
            now = self.get_datetime(item)
            now = timezone.localtime(now)
            calendars = get_calendars(now)
            now = timedelta(hours=now.hour, minutes=now.minute)
            trips = Trip.objects.filter(
                Exists(
                    StopTime.objects.filter(
                        trip=OuterRef('id'),
                        stop__naptan_code__iexact=item['next_stop_id'],
                        departure__lt=now + timedelta(minutes=5),
                        departure__gt=now - timedelta(minutes=10)
                    )
                ), calendar__in=calendars, route__service=journey.service_id
            )
            try:
                journey.trip = trips.get()
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['longitude'], item['latitude']),
            heading=item['heading']
        )
