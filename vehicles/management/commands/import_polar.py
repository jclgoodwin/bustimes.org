from django.contrib.gis.geos import Point
from busstops.models import Service, DataSource
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('source_name', type=str)

    def handle(self, source_name, **options):
        self.source_name = source_name
        super().handle(**options)

    def do_source(self):
        self.url = f'https://{self.source_name}.arcticapi.com/network/vehicles'
        self.source = DataSource.objects.get(url=self.url)  # we can't rely on the source name being unique
        self.operators = self.source.settings['operators']

    def get_items(self):
        return super().get_items()['features']

    def get_vehicle(self, item):
        code = item['properties']['vehicle']
        if '-' in code and code[0].isalpha():
            operator, code = code.split('-', 1)
        else:
            operator = item['_embedded']['transmodel:line']['id'].split(':')[0]

        if len(self.operators) == 1:
            operator = list(self.operators.values())[0]
        else:
            try:
                operator = self.operators[operator]
            except KeyError as e:
                print(e, operator)
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

        vehicles = self.vehicles.filter(operator__in=self.operators.values())

        if fleet_number.isdigit():
            vehicle = vehicles.get_or_create(
                defaults,
                fleet_number=fleet_number,
            )
        else:
            vehicle = vehicles.get_or_create(
                defaults,
                code=code,
            )

        if vehicle[0].code.isdigit() and not code.isdigit():
            vehicle[0].code = code
            vehicle[0].save()

        return vehicle

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            route_name=item['properties']['line'],
            direction=item['properties']['direction'][:8]
        )
        journey.data = item

        if len(self.operators) == 1:
            operator = list(self.operators.values())[0]
        else:
            operator = item['_embedded']['transmodel:line']['id'].split(':')[0]
            try:
                operator = self.operators[operator]
            except KeyError as e:
                print(e, operator)
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
