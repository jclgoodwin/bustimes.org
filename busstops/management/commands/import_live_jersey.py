import datetime
from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, Service


class Command(ImportLiveVehiclesCommand):
    source_name = 'jersey'
    operator = 'libertybus'
    url = 'https://sojbuslivetimespublic.azurewebsites.net/api/Values/GetMin?secondsAgo=360'

    def get_items(self):
        return super().get_items()['minimumInfoUpdates']

    def get_vehicle_and_service(self, item):
        code = item['bus'].split('-')[-1]
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None
        vehicle, created = Vehicle.objects.get_or_create(
            {'operator_id': self.operator, 'fleet_number': fleet_number},
            source=self.source,
            code=code
        )

        try:
            service = Service.objects.get(line_name=item['line'].lower(), current=True, operator=self.operator)
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, item['line'])
            service = None

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        now_datetime = datetime.datetime.now(datetime.timezone.utc)
        then_time = datetime.datetime.strptime(item['time'], '%H:%M:%S').time()

        now_time = now_datetime.time().replace(tzinfo=now_datetime.tzinfo)
        then_time = then_time.replace(tzinfo=now_datetime.tzinfo)

        if now_time < then_time:
            # yesterday
            now_datetime -= datetime.timedelta(days=1)
        then_datetime = datetime.datetime.combine(now_datetime, then_time)

        return VehicleLocation(
            datetime=then_datetime,
            latlong=Point(item['lon'], item['lat']),
            heading=item['bearing']
        )
