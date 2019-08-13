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

        if fleet_number.isdigit():
            return self.vehicles.get_or_create(
                defaults,
                fleet_number=fleet_number,
                operator__in=self.operators.values()
            )
        return self.vehicles.get_or_create(
            defaults,
            code=fleet_number,
            operator__in=self.operators.values()
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()
        journey.route_name = item['properties']['line']

        fleet_number = item['properties']['vehicle']
        if '-' in fleet_number:
            operator, fleet_number = item['properties']['vehicle'].split('-', 1)
        else:
            operator = item['_embedded']['transmodel:line']['id'].split(':')[0]

        operator = self.operators[operator]

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
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(operator, line_name, e)

        return journey

    def create_vehicle_location(self, item):
        return VehicleLocation(
            latlong=Point(item['geometry']['coordinates']),
            heading=item['properties'].get('bearing')
        )
