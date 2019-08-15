from time import sleep
from datetime import datetime
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import Extent
from django.utils import timezone
from busstops.models import Operator, Service, StopPoint
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


def get_latlong(item):
    return Point(float(item['lo']), float(item['la']))


class Command(ImportLiveVehiclesCommand):
    url = 'https://api.stagecoach-technology.net/vehicle-tracking/v1/vehicles'
    source_name = 'Stagecoach'
    operator_ids = {
        'SCEM': 'SCLI'
    }
    operators = {}

    @staticmethod
    def get_datetime(item):
        return datetime.fromtimestamp(int(item['ut']) / 1000, timezone.utc)

    def get_vehicle(self, item):
        vehicle = item['fn']
        if len(vehicle) > 5:
            return None, None
        operator_id = item['oc']
        operator_id = self.operator_ids.get(operator_id, operator_id)
        operator = self.operators.get(operator_id)
        if not operator:
            try:
                operator = Operator.objects.get(id=operator_id)
            except Operator.DoesNotExist as e:
                print(operator_id, e)
                return None, None
            self.operators[item['oc']] = operator
        defaults = {
            'operator_id': operator_id,
            'source': self.source
        }
        if vehicle.isdigit():
            defaults['fleet_number'] = vehicle
        if operator.name.startswith('Stagecoach '):
            return self.vehicles.get_or_create(defaults, operator__name__startswith='Stagecoach ', code=vehicle)
        else:  # Scottish Citylink
            return self.vehicles.get_or_create(defaults, operator=operator, code=vehicle)

    @staticmethod
    def get_extents():
        # for operator in ['SCCU', 'STGS', 'SCGR', 'CLTL', 'STCR', 'YSYC', 'SCEB', 'SCGL', 'SCHA', 'SCHT',
        #                  'SCLI', 'SCMY', 'SSWL', 'SCST', 'SCTE', 'SSWN']:
        for operator in ['SCEK', 'SSTY', 'SCGL', 'SCNE']:
            stops = StopPoint.objects.filter(service__operator=operator, service__current=True)
            extent = stops.aggregate(Extent('latlong'))['latlong__extent']
            if not extent:
                print(operator)
                continue
            yield {
                'latne': extent[3] + 0,
                'lngne': extent[2] + 0,
                'latsw': extent[1] - 0,
                'lngsw': extent[0] - 0,
                'clip': 1,
                # 'descriptive_fields': 1
            }

    def get_items(self):
        for params in self.get_extents():
            try:
                response = self.session.get(self.url, params=params, timeout=50)
                print(response.url)
                for item in response.json()['services']:
                    yield item
            except (RequestException, KeyError) as e:
                print(e)
                continue
            sleep(1)

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        journey.code = item.get('td', '')
        journey.destination = item.get('dd', '')
        journey.route_name = item.get('sn', '')

        if item['ao']:
            journey.datetime = datetime.fromtimestamp(int(item['ao']) / 1000, timezone.utc)

        latest_location = vehicle.latest_location
        if (
            latest_location and latest_location.journey.code == journey.code and
            latest_location.journey.route_name == journey.route_name and latest_location.journey.service
        ):
            journey.service = latest_location.journey.service
        elif journey.route_name:
            service = journey.route_name
            if service == 'TRIA':
                service = 'Triangle'
            elif service == 'TUBE':
                service = 'Oxford Tube'
            services = Service.objects.filter(current=True, line_name__iexact=service)
            operator = item['oc']
            services = services.filter(operator__name__startswith='Stagecoach ')
            try:
                journey.service = self.get_service(services, get_latlong(item))
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, operator, service)

        return journey

    def create_vehicle_location(self, item):
        bearing = item['hg']
        return VehicleLocation(
            latlong=get_latlong(item),
            heading=bearing
        )
