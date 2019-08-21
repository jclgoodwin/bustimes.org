from time import sleep
from random import shuffle
from datetime import timedelta
from ciso8601 import parse_datetime_as_naive
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models import Extent
from django.db.models import Q
from django.utils import timezone
from busstops.models import Service, StopPoint
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


def get_latlong(item):
    return Point(item['geo']['longitude'], item['geo']['latitude'])


class Command(ImportLiveVehiclesCommand):
    url = 'http://api.otrl-bus.io/api/bus/nearby'
    source_name = 'Go-Ahead'
    operators = {
        'GOEA': ('KCTB', 'CHAM', 'HEDO'),
        'CSLB': ('OXBC', 'CSLB', 'THTR'),
        'GNE': ('GNEL',),
        'BH': ('BHBC',),
        'SQ': ('BLUS', 'SVCT', 'UNIL', 'SWWD', 'DAMY', 'TOUR', 'WDBC'),
        'TT': ('TDTR',),
        'PC': ('PLYC',),
        'GONW': ('GONW',),
    }

    opcos = {
        'eastangliabuses': ('KCTB', 'CHAM', 'HEDO'),
        'oxford': ('OXBC', 'CSLB', 'THTR'),
        'gonortheast': ('GNEL',),
        'brightonhove': ('BHBC',),
        'swindon': ('TDTR',),
        'more': ('WDBC',),
        'bluestar': ('BLUS', 'UNIL'),
        'salisburyreds': ('SWWD',),
        'plymouth': ('PLYC',),
        'gonorthwest': ('GONW',),
    }

    @staticmethod
    def get_datetime(item):
        return timezone.make_aware(parse_datetime_as_naive(item['recordedTime']))

    def get_vehicle(self, item):
        vehicle = item['vehicleRef']
        operator, fleet_number = item['vehicleRef'].split('-', 1)
        operators = self.operators.get(operator)
        if not operators:
            print(operator)
        defaults = {
            'source': self.source
        }
        if fleet_number.isdigit():
            defaults['fleet_number'] = fleet_number

        if operator == 'PC':
            return self.vehicles.get_or_create(defaults, code=fleet_number, operator_id='PLYC')

        return self.vehicles.get_or_create(defaults, code=vehicle)

    def get_points(self):
        boxes = []
        for opco in self.opcos:
            for operator in self.opcos[opco]:
                stops = StopPoint.objects.filter(service__operator=operator, service__current=True).using('read-only')
                extent = stops.aggregate(Extent('latlong'))['latlong__extent']
                lng = extent[0]
                # exclude services with current locations from another source
                services = Service.objects.filter(current=True, operator=operator).exclude(
                    ~Q(vehiclejourney__source=self.source),
                    vehiclejourney__vehiclelocation__current=True,
                    vehiclejourney__vehiclelocation__datetime__gt=self.source.datetime + timedelta(minutes=5),
                ).using('read-only')
                stops = stops.filter(stopusageusage__journey__service__in=services)

                while lng <= extent[2]:
                    lat = extent[1]
                    while lat <= extent[3]:
                        boxes.append((opco, stops, lng, lat))
                        lat += 0.2
                    lng += 0.2
        shuffle(boxes)
        return boxes

    def get_items(self):
        for opco, stops, lng, lat in self.get_points():
            bbox = Polygon.from_bbox(
                (lng - 0.1, lat - 0.1, lng + 0.1, lat + 0.1)
            )
            if stops.filter(latlong__within=bbox).exists():
                params = {'lat': lat, 'lng': lng}
                headers = {'opco': opco}
                try:
                    response = self.session.get(self.url, params=params, timeout=30, headers=headers)
                    for item in response.json()['data']:
                        yield item
                except (RequestException, KeyError):
                    continue
                sleep(1)

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        journey.code = str(item['datedVehicleJourney'])
        journey.destination = item['destination']['name']
        journey.route_name = item['lineRef']

        operator, fleet_number = item['vehicleRef'].split('-', 1)
        operators = self.operators.get(operator)
        if not operators:
            print(operator)

        if operators:
            latest_location = vehicle.latest_location
            if (
                latest_location and latest_location.journey.code == journey.code and
                latest_location.journey.route_name == journey.route_name and latest_location.journey.service
            ):
                journey.service = latest_location.journey.service
            else:
                if item['lineRef'] == 'CSR' and operators[0] == 'BHBC':
                    item['lineRef'] = 'CSS'
                if operators[0] == 'BLUS' and item['lineRef'] == 'QC':
                    item['lineRef'] = 'QuayConnect'
                services = Service.objects.filter(operator__in=operators, line_name__iexact=item['lineRef'],
                                                  current=True)
                try:
                    try:
                        journey.service = self.get_service(services, get_latlong(item))
                    except Service.MultipleObjectsReturned:
                        destination = item['destination']['ref']
                        journey.service = services.filter(stops__locality__stoppoint=destination).distinct().get()
                except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                    print(e, operators, item['lineRef'])

                if journey.service:
                    try:
                        operator = journey.service.operator.get()
                        if vehicle.operator_id != operator.id:
                            vehicle.operator_id = operator.id
                            vehicle.save()
                    except journey.service.operator.model.MultipleObjectsReturned:
                        pass

        return journey

    def create_vehicle_location(self, item):
        bearing = item['geo']['bearing']
        if bearing == 0 and item['vehicleRef'].startswith('BH-'):
            bearing = None
        return VehicleLocation(
            latlong=get_latlong(item),
            heading=bearing
        )
