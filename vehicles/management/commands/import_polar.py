from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import Vehicle, VehicleLocation, VehicleJourney
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

    def get_journey(self, item):
        journey = VehicleJourney()
        journey.route_name = item['properties']['line']

        fleet_number = item['properties']['vehicle']
        if '-' in fleet_number:
            operator, fleet_number = item['properties']['vehicle'].split('-', 1)
        else:
            operator = item['_embedded']['transmodel:line']['id'].split(':')[0]

        operator = self.operators[operator]

        defaults = {
            'source': self.source,
            'operator_id': operator,
            'code': fleet_number
        }

        if ' - ' in fleet_number:
            fleet_number, defaults['reg'] = fleet_number.split(' - ')

        line_name = item['properties']['line']
        if operator == 'BLAC' and line_name == 'PRM':
            line_name = '1'
        services = Service.objects.filter(current=True, line_name=line_name)
        if operator == 'BORD':
            services = services.filter(operator__in=('BORD', 'PERY'))
        else:
            services = services.filter(operator=operator)

        try:
            journey.service = self.get_service(services, Point(item['geometry']['coordinates']))
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print(operator, line_name, e)

        if fleet_number.isdigit():
            journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(
                defaults,
                fleet_number=fleet_number,
                operator__in=self.operators.values()
            )
        else:
            journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(
                defaults,
                code=fleet_number,
                operator__in=self.operators.values()
            )

        return journey, vehicle_created

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['geometry']['coordinates']),
            heading=item['properties'].get('bearing')
        )
