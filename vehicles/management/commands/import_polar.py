from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'transdevblazefield'
    url = 'https://transdevblazefield.arcticapi.com/network/vehicles'
    operators = {
        'YCD': 'YCST',
        'LUI': 'LNUD',
        'BPT': 'BPTR',
        'HDT': 'HRGT',
        'KDT': 'KDTR',
        'ROS': 'ROST'
    }

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
            operator = self.operators[operator]

        if operator == 'NCTR' and len(code) == 6:
            # Trent Barton vehicles
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

        if fleet_number.isdigit():
            vehicle = self.vehicles.get_or_create(
                defaults,
                fleet_number=fleet_number,
                operator__in=self.operators.values()
            )
        else:
            vehicle = self.vehicles.get_or_create(
                defaults,
                code=code,
                operator__in=self.operators.values()
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

        if len(self.operators) == 1:
            operator = list(self.operators.values())[0]
        else:
            operator = item['_embedded']['transmodel:line']['id'].split(':')[0]
            try:
                operator = self.operators[operator]
            except KeyError as e:
                print(e, item)
                return journey

        line_name = item['properties']['line']
        if operator == 'BLAC' and line_name == 'PRM':
            line_name = '1'
        if vehicle.latest_location and vehicle.latest_location.journey.route_name == journey.route_name:
            journey.service = vehicle.latest_location.journey.service
        else:
            services = Service.objects.filter(current=True, line_name=line_name)
            if operator == 'BORD':
                services = services.filter(operator__in=('BORD', 'PERY'))
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
                print(operator, line_name)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['geometry']['coordinates']),
            heading=item['properties'].get('bearing')
        )
