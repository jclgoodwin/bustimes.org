from time import sleep
from datetime import timedelta
from ciso8601 import parse_datetime
from django.contrib.gis.geos import Point
from django.utils import timezone
from requests.exceptions import RequestException
from django.contrib.gis.db.models import Extent
from ..import_live_vehicles import ImportLiveVehiclesCommand
from busstops.models import Operator, Service, StopPoint
from ...models import VehicleLocation, VehicleJourney


def get_latlong(item):
    position = item['position']
    return Point(position['longitude'], position['latitude'])


class Command(ImportLiveVehiclesCommand):
    operator_ids = {
        'BOWE': 'HIPK',
        'LAS': ('GAHL', 'LGEN'),
        '767STEP': ('SESX', 'GECL', 'NIBS'),
        'UNIB': 'UNOE',
        'UNO': 'UNOE',
        'RENW': 'ECWY',
        'CB': ('CBUS', 'CACB'),
        'CUBU': ('CUBU', 'RSTY'),
        'SOG': 'guernsey',
        'IOM': ('bus-vannin', 'IMHR'),
        'Rtl': ('RBUS', 'GLRB', 'KENN', 'NADS', 'THVB'),
    }
    operators = {}
    source_name = 'ZipTrip'
    url = 'https://ziptrip1.ticketer.org.uk/v1/vehiclepositions'
    ignorable_route_names = {'rr', 'rail', 'transdev', '7777', 'shop', 'pos', 'kiosk', 'rolls-royce'}

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['reported'])

    def get_extents(self):
        for operator in (
            'SBAY',
            'CBUS',
            'CUBU',
            'ECWY',
            'FALC',
            'GECL',
            'GAHL',
            'guernsey',
            'HIPK',
            'IPSW',
            'LYNX',
            'MDCL',
            'NDTR',
            'DPCE',
            'RBUS',
            'NADS',
            'SFGC',
            'SESX',
            'NIBS',
            'UNOE',
            'WHTL',
            'TRDU',
            # 'ROST',
        ):
            stops = StopPoint.objects.filter(service__operator=operator, service__current=True)
            extent = stops.aggregate(Extent('latlong'))['latlong__extent']
            if not extent:
                print(operator)
                continue
            yield {
                'maxLat': extent[3] + 0.1,
                'maxLng': extent[2] + 0.1,
                'minLat': extent[1] - 0.1,
                'minLng': extent[0] - 0.1,
            }

        # Mann
        yield {
            'maxLat': 54.5,
            'maxLng': -3.8,
            'minLat': 53.9,
            'minLng': -5.1
        }

    def get_items(self):
        fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
        for params in self.get_extents():
            try:
                response = self.session.get(self.url, params=params, timeout=5)
                items = response.json()['items']
                any_items = False
                if items:
                    for item in items:
                        if parse_datetime(item['reported']) > fifteen_minutes_ago:
                            any_items = True
                            yield item
                if not any_items:
                    print(response.url)
            except (RequestException, KeyError):
                continue
            sleep(1)

    def get_vehicle(self, item):
        operator_id, vehicle = item['vehicleCode'].split('_', 1)
        vehicle = vehicle.replace(' ', '_')

        if operator_id in self.operator_ids:
            operator_id = self.operator_ids[operator_id]

        defaults = {}
        if vehicle.isdigit():
            defaults['fleet_number'] = vehicle
        defaults['source'] = self.source
        if type(operator_id) is tuple:
            defaults['operator_id'] = operator_id[0]
            return self.vehicles.get_or_create(defaults, operator_id__in=operator_id, code=vehicle)
        else:
            try:
                if operator_id not in self.operators:
                    self.operators['operator_id'] = Operator.objects.get(id=operator_id)
                return self.vehicles.get_or_create(defaults, operator_id=operator_id, code=vehicle)
            except Operator.DoesNotExist as e:
                print(e, operator_id)
                return None, None

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        operator_id = item['vehicleCode'].split('_', 1)[0]

        route_name = item.get('routeName', '')
        if route_name:
            journey.route_name = route_name

        if operator_id == 'BOWE':
            if route_name == '199':
                route_name = 'Skyline 199'
            if route_name == 'TP':
                route_name = 'Transpeak'
        elif operator_id == '767STEP':
            if route_name == '2':
                route_name = 'Breeze 2'
            elif route_name.endswith(' Essex'):
                route_name = route_name[:-6]
        elif operator_id == 'UNIB' or operator_id == 'UNO':
            if route_name == '690':
                route_name = 'Inter-campus Shuttle'
        elif operator_id == 'LYNX' and route_name == '48b':
            route_name = '48'
        elif operator_id == 'CUBU':
            if route_name == '157A':
                route_name = route_name[:-1]
        elif operator_id == 'IOM':
            if route_name == 'IMR':
                route_name = 'Isle of Man Steam Railway'
            elif route_name == 'HT':
                route_name = 'Douglas Bay Horse Tram'
            elif route_name == 'MER':
                route_name = 'Manx Electric Railway'
            elif route_name == 'SMR':
                route_name = 'Snaefell Mountain Railway'
        elif operator_id == 'Rtl':
            if route_name.startswith('K'):
                route_name = route_name[1:]

        if operator_id in self.operator_ids:
            operator_id = self.operator_ids[operator_id]

        latest = vehicle.latest_location
        if latest and latest.journey.route_name == journey.route_name and latest.journey.service:
            journey.service = latest.journey.service
        elif route_name:
            services = Service.objects.filter(current=True)
            if operator_id[0] == 'SESX' and route_name == '1':
                services = services.filter(line_name__in=('1', 'Breeze 1'))
            else:
                services = services.filter(line_name__iexact=route_name)

            if type(operator_id) is tuple:
                services = services.filter(operator__in=operator_id)
            else:
                services = services.filter(operator=operator_id)
            try:
                journey.service = self.get_service(services, get_latlong(item))
                if operator_id[0] == 'SESX' or operator_id[0] == 'CUBU':
                    try:
                        operator = journey.service.operator.get()
                        if vehicle.operator_id != operator.id:
                            vehicle.operator = operator
                            vehicle.save()
                    except Operator.MultipleObjectsReturned:
                        pass
            except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
                if route_name.lower() not in self.ignorable_route_names:
                    if operator_id[0] != 'bus-vannin' and not (operator_id[0] == 'RBUS' and route_name[0] == 'V'):
                        print(e, operator_id, route_name)

        return journey

    def create_vehicle_location(self, item):
        bearing = item.get('bearing')
        while bearing and bearing < 0:
            bearing += 360
        return VehicleLocation(
            latlong=get_latlong(item),
            heading=bearing
        )
