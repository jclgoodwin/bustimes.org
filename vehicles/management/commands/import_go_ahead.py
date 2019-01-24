from time import sleep
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point
from busstops.models import Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney


class Command(ImportLiveVehiclesCommand):
    url = 'http://api.otrl-bus.io/api/bus/nearby'
    source_name = 'Go-Ahead'
    operators = {
        'GOEA': ('KCTB',),
        'CSLB': ('OXBC', 'THTR'),
        'GNE': ('GNEL',),
        'BH': ('BHBC',),
        'SQ': ('SVCT',),
    }

    def get_items(self):
        for opco, lat, lng in (
            ('eastangliabuses', 52.6, 1.3),
            ('eastangliabuses', 52.6458, 1.1162),
            ('eastangliabuses', 52.6816, 0.9378),
            # ('eastangliabuses', 52.4593, 1.5661),
            # ('eastangliabuses', 52.8313, 0.8393),
            ('eastangliabuses', 52.7043, 1.4073),
            # ('brightonhove', 51, -0.1372),
            # ('brightonhove', 50.6, -0.1372),
            # ('brightonhove', 50.8225, -0.1372),
            # ('brightonhove', 50.8225, -0.2),
            # ('brightonhove', 50.8225, 0),
            # ('oxford', 51.752, -1.2577),
            # ('oxford', 51.752, -1.3),
            # ('oxford', 51.752, -1.4),
            # ('oxford', 51.6, -1.3),
            # ('oxford', 51.8, -1.4),
            # ('oxford', 51.752, -1.0577),
            # ('oxford', 51.752, -0.9),
            # ('gonortheast', 54.9783, -1.6178),
            ('southernvectis', 50.6332, -1.2547),
        ):
            params = {'lat': lat, 'lng': lng}
            headers = {'opco': opco}
            try:
                response = self.session.get(self.url, params=params, timeout=30, headers=headers)
                for item in response.json()['data']:
                    yield item
            except (RequestException, KeyError):
                continue
            sleep(5)

    def get_journey(self, item):
        journey = VehicleJourney()

        journey.code = item['datedVehicleJourney']
        journey.destination = item['destination']['name']

        vehicle = item['vehicleRef']
        operator, fleet_number = item['vehicleRef'].split('-', 1)
        operators = self.operators.get(operator)
        defaults = {
            'source': self.source
        }
        if fleet_number.isdigit():
            defaults['fleet_number'] = fleet_number
        if operators:
            defaults['operator_id'] = operators[0]
            try:
                journey.service = Service.objects.get(operator__in=operators, line_name=item['lineRef'], current=True)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, operators, item['lineRef'])

        journey.vehicle, created = Vehicle.objects.get_or_create(defaults, code=vehicle)

        return journey, created

    def create_vehicle_location(self, item):
        return VehicleLocation(
            datetime=item['recordedTime'],
            latlong=Point(item['geo']['longitude'], item['geo']['latitude']),
            heading=item['geo']['bearing']
        )
