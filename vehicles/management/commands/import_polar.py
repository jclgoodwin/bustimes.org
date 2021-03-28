from django.contrib.gis.geos import Point
from django.db.models import Q
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('source_name', type=str)

    def handle(self, source_name, **options):
        self.source_name = source_name
        super().handle(**options)

    def do_source(self):
        super().do_source()
        self.operators = self.source.settings['operators']

    def get_items(self):
        return super().get_items()['features']

    def get_operator(self, item):
        if len(self.operators) == 1:
            return list(self.operators.values())[0]
        operator = item['_embedded']['transmodel:line']['href'].split('/')[3]
        try:
            operator = self.operators[operator]
        except KeyError:
            if len(operator) != 4:
                return None
        return operator

    def get_vehicle(self, item):
        code = item['properties']['vehicle']

        operator = self.get_operator(item)
        if not operator:
            return None, None

        if operator == 'MCGL' and (len(code) >= 7 or len(code) >= 5 and code.isdigit()):
            # Borders Buses or First vehicles
            print(code)
            return None, None

        fleet_number = code

        if '_-_' in code:
            parts = code.split('_-_')
            if parts[0].isdigit():
                fleet_number = parts[0]

        defaults = {
            'source': self.source,
            'operator_id': operator,
            'code': code
        }

        if 'meta' in item['properties']:
            if 'name' in item['properties']['meta']:
                defaults['name'] = item['properties']['meta']['name']
            if 'number_plate' in item['properties']['meta']:
                defaults['reg'] = item['properties']['meta']['number_plate']

        if len(code) > 4 and code[0].isalpha() and code[1] == '_':  # McGill
            fleet_number = code[2:]
            defaults['fleet_code'] = code.replace('_', ' ')

        condition = Q(operator__in=self.operators.values()) | Q(operator=operator)
        vehicles = self.vehicles.filter(condition)

        vehicle = None
        created = False

        if 'reg' in defaults:
            vehicle = vehicles.filter(reg=defaults['reg']).first()

        if not vehicle and fleet_number.isdigit():
            vehicle = vehicles.filter(fleet_number=fleet_number).first()

        if not vehicle:
            vehicle, created = vehicles.get_or_create(defaults, code=code)

        if vehicle.code != code:
            vehicle.code = code
            if 'fleet_code' in defaults:
                vehicle.fleet_code = defaults['fleet_code']
            elif 'fleet_number' in defaults:
                vehicle.fleet_number = defaults['fleet_number']
                vehicle.fleet_code = vehicle.fleet_number
            vehicle.save(update_fields=['code', 'fleet_code', 'fleet_number'])

        return vehicle, created

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            route_name=item['properties']['line'],
            direction=item['properties']['direction'][:8]
        )
        journey.data = item

        operator = self.get_operator(item)
        if not operator:
            return journey

        latest_journey = vehicle.latest_journey

        if latest_journey and latest_journey.route_name == journey.route_name:
            journey.service_id = latest_journey.service_id
        else:
            services = Service.objects.filter(current=True, line_name__iexact=journey.route_name)
            services = services.filter(operator=operator)

            try:
                journey.service = self.get_service(services, Point(item['geometry']['coordinates']))
            except Service.DoesNotExist:
                pass
            if not journey.service:
                print(operator, vehicle.operator_id, journey.route_name)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['geometry']['coordinates']),
            heading=item['properties'].get('bearing')
        )
