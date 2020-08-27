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
        self.source = DataSource.objects.get(url=self.url)
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

        if operator == 'NCTR' and len(code) == 6:
            # Trent Barton vehicles
            return None, None
        elif operator == 'MCGL' and (len(code) >= 7 or len(code) >= 5 and code.isdigit()):
            # Borders Buses or First vehicles
            print(code)
            return None, None

        fleet_number = code

        if '_-_' in code:
            parts = code.split('_-_')
            if parts[0].isdigit():
                fleet_number = parts[0]

        if operator == 'CTNY':
            code = code.replace('_', '')

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

        if self.source.name in {'salisburyreds', 'morebus', 'swindonbus', 'bluestar'}:
            vehicles = self.vehicles.filter(operator__parent='Go South Coast')
        else:
            vehicles = self.vehicles.filter(operator__in=self.operators.values())

        if fleet_number.isdigit():
            vehicle = vehicles.get_or_create(
                defaults,
                fleet_number=fleet_number,
            )
        elif fleet_number.isupper() and operator == 'GNEL':
            vehicle = vehicles.get_or_create(
                defaults,
                reg=code.replace('_', ''),
            )
        else:
            vehicle = vehicles.get_or_create(
                defaults,
                code=code,
            )

        if vehicle[0].operator_id == 'METR':  # ignore Metrobus vehicles in Brighton & Hove feed
            return None, None

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

        line_name = journey.route_name
        if operator == 'BLAC' and line_name == 'PRM':
            line_name = '1'
        elif vehicle.operator_id == 'WDBC' and line_name == '1':
            line_name = 'ONE'

        latest_location = vehicle.latest_location
        if latest_location and latest_location.current and latest_location.journey.route_name == journey.route_name:
            journey.service = latest_location.journey.service
        else:
            services = Service.objects.filter(current=True, line_name=line_name)
            if self.source.name in {'salisburyreds', 'morebus', 'swindonbus', 'bluestar'}:
                services = services.filter(operator=vehicle.operator_id)
            else:
                if operator == 'BORD':
                    services = services.filter(operator__in=('BORD', 'PERY'))
                elif operator == 'CTNY':
                    services = services.filter(operator__in=('CTNY', 'THVB'))
                else:
                    services = services.filter(operator=operator)

                if vehicle.operator_id != operator:
                    vehicle.operator_id = operator
                    vehicle.save()

            try:
                journey.service = self.get_service(services, Point(item['geometry']['coordinates']))
            except Service.DoesNotExist:
                pass
            if not journey.service:
                print(operator, vehicle.operator_id, line_name)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['geometry']['coordinates']),
            heading=item['properties'].get('bearing')
        )
