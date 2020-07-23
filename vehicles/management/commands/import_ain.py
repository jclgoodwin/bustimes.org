import logging
from time import sleep
from datetime import datetime
from django.utils import timezone
from django.contrib.gis.geos import Point
from busstops.models import Operator, Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


logger = logging.getLogger(__name__)


class Command(ImportLiveVehiclesCommand):
    source_name = 'ain'
    services = []
    operators = {}

    def get_services(self):
        self.session.headers.update(self.source.settings['headers'])
        i = 1
        results = True
        while results:
            response = self.session.get(
                self.source.url + 'operators',
                params={'iteration': i},
                timeout=5,
                verify=False
            )
            sleep(2)
            results = response.json()['results']
            for operator in results:
                name = operator['name']
                try:
                    self.operators[name] = Operator.objects.get(operatorcode__source=self.source,
                                                                operatorcode__code=name)
                    for service in operator['services']:
                        self.services.append(service['code'])
                except Operator.DoesNotExist as e:
                    print(e, name)
            i += 1

    def get_items(self):
        if not self.services:
            self.get_services()
        response = self.session.get(
            self.source.url + 'buses',
            params={'service[]': [self.services]},
            timeout=5
        )
        return response.json()['results']

    @staticmethod
    def get_timestamp(item):
        return timezone.make_aware(datetime.fromtimestamp(item['now'])),

    def get_vehicle(self, item):
        code = item['vehicle']['registration']
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        return self.vehicles.get_or_create(
            {'fleet_number': fleet_number, 'source': self.source},
            code=code,
            operator=self.operators[item['operator']]
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        journey.route_name = item['service']['line'] or ''
        journey.destination = item['service']['destination'] or ''

        latest_location = vehicle.latest_location
        if latest_location and latest_location.journey.route_name == journey.route_name:
            if latest_location.journey.destination == journey.destination:
                return latest_location.journey

        try:
            try:
                service_code = item['service']['code']
                if '-' in service_code:
                    service_code = '-'.join(service_code.split('-')[:-1])
                    journey.service = Service.objects.get(service_code__endswith='_' + service_code)
                else:
                    journey.service = Service.objects.get(service_code=service_code)
            except Service.DoesNotExist:
                journey.service = Service.objects.get(operator=self.operators[item['operator']],
                                                      line_name=journey.route_name)
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            logger.error(e, exc_info=True)

        return journey

    def create_vehicle_location(self, item):
        bearing = item['vehicle']['bearing']
        if bearing == -1:
            bearing = None
        pos = item['vehicle']['pos']
        delay = item['service']['delay']
        if delay is not None:
            delay = int(delay)
            early = -delay
        else:
            early = None
        return VehicleLocation(
            latlong=Point(float(pos['lon']), float(pos['lat'])),
            heading=bearing,
            delay=delay,
            early=early
        )
