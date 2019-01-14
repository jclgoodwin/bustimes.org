import ciso8601
from django.contrib.gis.geos import Point
from django.db.utils import IntegrityError
from ..import_live_vehicles import ImportLiveVehiclesCommand
from busstops.models import Operator, Service
from ...models import Vehicle, VehicleLocation, VehicleJourney


def get_latlong(item):
    position = item['position']
    return Point(position['longitude'], position['latitude'])


class Command(ImportLiveVehiclesCommand):
    operators = {}
    source_name = 'ZipTrip'
    url = 'http://ziptrip-vps.api.urbanthings.cloud/api/0.2/vehiclepositions?maxLat=60&maxLng=10&minLng=-50&minLat=40'

    def get_items(self):
        return super().get_items()['items']

    def get_journey(self, item):
        journey = VehicleJourney()

        operator_id, vehicle = item['vehicleCode'].split('_', 1)

        route_name = item['routeName']

        if operator_id == 'BOWE':
            operator_id = 'HIPK'
            if route_name == '199':
                route_name = 'Skyline 199'
            if route_name == 'TP':
                route_name = 'Transpeak'
        elif operator_id == 'LAS':
            operator_id = ('GAHL', 'LGEN')
        elif operator_id == '767STEP':
            if '(' in vehicle:
                operator_id = 'GECL'
            else:
                operator_id = 'SESX'
                if route_name == '2':
                    route_name = 'Breeze 2'
        elif operator_id == 'UNIB' or operator_id == 'UNO':
            operator_id = 'UNOE'
            if route_name == '690':
                route_name = 'Inter-campus Shuttle'
        elif operator_id == 'RENW':
            operator_id = 'ECWY'
        elif operator_id == 'CB':
            operator_id = ('CBUS', 'CACB')
        elif operator_id == 'SOG':
            operator_id = 'guernsey'
        elif operator_id == 'IOM':
            operator_id = 'IMHR'
            if route_name == 'IMR':
                route_name = 'Isle of Man Steam Railway'
            elif route_name == 'HT':
                route_name = 'Douglas Bay Horse Tram'
            elif route_name == 'MER':
                route_name = 'Manx Electric Railway'
            elif route_name == 'SMR':
                route_name = 'Snaefell Mountain Railway'
            else:
                operator_id = 'bus-vannin'
        elif operator_id == 'Rtl':
            if route_name.startswith('K'):
                route_name = route_name[1:]
                operator_id = 'KENN'
            operator_id = ('RBUS', 'GLRB')

        if operator_id in self.operators:
            operator = self.operators[operator_id]
        elif type(operator_id) is str:
            try:
                operator = Operator.objects.get(id=operator_id)
            except Operator.DoesNotExist:
                operator = None
            self.operators[operator_id] = operator
        else:
            operator = Operator.objects.get(id=operator_id[0])

        if vehicle.isdigit():
            fleet_number = vehicle
        else:
            fleet_number = None
        defaults = {
             'fleet_number': fleet_number
        }
        if operator:
            defaults['source'] = self.source
            try:
                journey.vehicle, created = Vehicle.objects.get_or_create(defaults, operator=operator, code=vehicle)
            except IntegrityError:
                defaults['operator'] = operator
                journey.vehicle, created = Vehicle.objects.get_or_create(defaults, source=self.source, code=vehicle)
        else:
            created = False

        if route_name.endswith('_Essex'):
            route_name = route_name[:-6]
        elif operator_id == 'CUBU' and route_name == '157A':
            route_name = route_name[:-1]

        services = Service.objects.filter(current=True)
        if operator_id == 'SESX' and item['route_name'] == '1':
            services = services.filter(line_name__in=['1', 'Breeze 1'])
        else:
            services = services.filter(line_name__iexact=route_name)

        if type(operator_id) is tuple:
            services = services.filter(operator__in=operator_id)
        elif operator:
            services = services.filter(operator=operator)

        try:
            if operator:
                journey.service = self.get_service(services, get_latlong(item))
            else:
                print(item)
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            if route_name.lower() not in {'rr', 'rail', 'transdev', '7777', 'shop', 'pos'}:
                print(e, operator_id, route_name)

        return journey, created

    def create_vehicle_location(self, item):
        bearing = item.get('bearing')
        while bearing and bearing < 0:
            bearing += 360
        return VehicleLocation(
            datetime=ciso8601.parse_datetime(item['reported']),
            latlong=get_latlong(item),
            heading=bearing
        )
