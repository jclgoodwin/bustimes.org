from time import sleep
from datetime import datetime
from requests.exceptions import RequestException
from django.db.models import Exists, OuterRef
from django.contrib.gis.geos import Point
from django.utils import timezone
from busstops.models import Operator, Service, StopPoint
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand, logger


# "fn" "fleetNumber": "10452",
# "ut" "updateTime": "1599550016135",
# "oc" "operatingCompany": "SDVN",
# "sn" "serviceNumber": "RED",
# "dn" "direction": "INBOUND",
# "sd" "serviceId": "XDARED0.I",
# "so" "shortOpco": "SCD",
# "sr" "serviceDescription": "Honiton Road Park & Ride - Exeter, Paris Street",
# "cd" "cancelled": "False",
# "vc" "vehicleActivityCancellation": "False",
# "la" "latitude": "50.7314606",
# "lo" "longitude": "-3.7003877",
# "hg" "heading": "66",
# "cg" "calculatedHeading": "",
# "dd" "destinationDisplay": "City Centre Paris S",
# "or" "originStopReference": "1100DEC10843",
# "on" "originStopName": "Honiton Road P&R",
# "nr" "nextStopReference": "1100DEC10085",
# "nn" "nextStopName": "Sidwell Street",
# "fr" "finalStopReference": "1100DEC10468",
# "fs" "finalStopName": "Paris Street",
# "ao" "aimedOriginStopDepartureTime": "",
# "eo" "expectedOriginStopDepartureTime": "1599414000000",
# "an" "aimedNextStopArrivalTime": "1599414720000",
# "en" "expectedNextStopArrivalTime": "1599414756000",
# "ax" "aimedNextStopDepartureTime": "1599414720000",
# "ex" "expectedNextStopDepartureTime": "1599414522000",
# "af" "aimedFinalStopArrivalTime": "1599414780000",
# "ef" "expectedFinalStopArrivalTime": "1599414728000",
# "ku" "kmlUrl": "https://tis-kml-stagecoach.s3.amazonaws.com/kml/0017f465-8178-4bfb-bfaa-43a81386120e.kml",
# "td" "tripId": "7127",
# "pr" "previousStopOnRoute": "1100DEC10843",
# "cs" "currentStopOnRoute": "",
# "ns" "nextStopOnRoute": "",
# "jc" "isJourneyCompletedHeuristic": "False",
# "rg" "rag": "A"


def get_latlong(item):
    return Point(float(item['lo']), float(item['la']))


def get_datetime(timestamp):
    if timestamp:
        return datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc)


def has_stop(stop):
    return Exists(StopPoint.objects.filter(service=OuterRef('pk'), locality__stoppoint=stop))


class Command(ImportLiveVehiclesCommand):
    url = 'https://api.stagecoach-technology.net/vehicle-tracking/v1/vehicles'
    source_name = 'Stagecoach'
    operator_codes = [
        'SDVN', 'SCMN', 'SCCU', 'SCGL', 'SSWL', 'SCNH', 'STWS', 'SCEM', 'SCCM', 'SCOX', 'SCHI', 'SCNE',
        'SCFI', 'SBLB', 'SYRK', 'SCEK', 'SCMY', 'SCLK', 'SCSO'
    ]
    operator_ids = {
        'SCEM': 'SCGH',
        'SCSO': 'SCCO'
    }
    vehicles_ids = {}
    services = {}

    def get_items(self):
        for operator in self.operator_codes:
            params = {
                # 'clip': 1,
                # 'descriptive_fields': 1,
                'services': f':{operator}:::'
            }
            try:
                response = self.session.get(self.url, params=params, timeout=5)
                # print(response.url)
                for item in response.json()['services']:
                    yield item
                sleep(1)
            except (RequestException, KeyError) as e:
                print(e)
                continue

    @staticmethod
    def get_datetime(item):
        return get_datetime(item['ut'])

    def get_vehicle(self, item):
        vehicle_code = item['fn']
        if len(vehicle_code) > 5:
            return None, None
        if vehicle_code in self.vehicles_ids:
            vehicle = self.vehicles.get(id=self.vehicles_ids[vehicle_code])
            created = False
        else:
            operator_id = self.operator_ids.get(item['oc'], item['oc'])
            operator = self.operators.get(operator_id)
            if not operator:
                try:
                    operator = Operator.objects.get(id=operator_id)
                except Operator.DoesNotExist as e:
                    logger.error(e, exc_info=True, extra={
                        'operator': operator_id
                    })
            defaults = {
                'source': self.source
            }
            if vehicle_code.isdigit():
                defaults['fleet_number'] = vehicle_code
            if operator:
                defaults['operator'] = operator
                if operator_id == 'SCLK':  # Scottish Citylink
                    vehicles = self.vehicles.filter(operator=operator_id)
                else:
                    vehicles = self.vehicles.filter(operator__in=self.operators)
                vehicle, created = vehicles.get_or_create(defaults, code=vehicle_code)
                self.vehicles_ids[vehicle_code] = vehicle.id
            else:
                return None, None

        # if vehicle.latest_location:
        #    if vehicle.latest_location.journey.source_id != self.source.id:
        #        if (self.source.datetime - vehicle.latest_location.datetime).total_seconds() < 300:
        #            print(vehicle)
        #            return None, None

        return vehicle, created

    def get_journey(self, item, vehicle):
        if item['ao']:  # aimed origin departure time
            departure_time = get_datetime(item['ao'])
            code = item.get('td', '')  # trip id
        else:
            departure_time = None
            code = ''

        latest_location = vehicle.latest_location

        if departure_time:
            if latest_location and latest_location.journey.datetime == departure_time:
                return latest_location.journey
            else:
                try:
                    return vehicle.vehiclejourney_set.select_related('service').get(datetime=departure_time)
                except VehicleJourney.DoesNotExist:
                    pass

        journey = VehicleJourney(datetime=departure_time, data=item)

        if code:
            journey.code = code
            journey.destination = item.get('dd', '')

        journey.route_name = item.get('sn', '')

        if not journey.service and journey.route_name:
            service = journey.route_name
            alternatives = {
                'PULS': 'Pulse',
                # 'TUBE': 'Oxford Tube',
                'SPRI': 'SPRING',
                'YO-Y': 'Yo-Yo',
                'TRIA': 'Triangle',
            }
            if service in alternatives:
                service = alternatives[service]

            services = Service.objects.filter(current=True, operator__in=self.operators)

            stop = item.get('or') or item.get('pr') or item.get('nr')

            if stop:
                key = f'{stop}-{service}'
                if key in self.services:
                    journey.service = self.services[key]
                    return journey

                services = services.filter(has_stop(stop))

            if item.get('fr'):
                services = services.filter(has_stop(item['fr']))

            journey.service = services.filter(line_name__iexact=service).first()
            if not journey.service:
                try:
                    journey.service = services.get(service_code__icontains=f'-{service}-')
                except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                    pass

            if stop:
                self.services[key] = journey.service

            if not journey.service:
                print(service, item.get('or'), vehicle.get_absolute_url())

        return journey

    def create_vehicle_location(self, item):
        bearing = item['hg']

        aimed = item.get('an') or item.get('ax')
        expected = item.get('en') or item.get('ex')
        if aimed and expected:
            aimed = get_datetime(aimed)
            expected = get_datetime(expected)
            early = (aimed - expected).total_seconds() / 60
            early = round(early)
            delay = -early
        else:
            delay = None
            early = None

        return VehicleLocation(
            latlong=get_latlong(item),
            heading=bearing,
            delay=delay,
            early=early
        )

    def handle(self, *args, **options):
        self.operators = Operator.objects.filter(parent='Stagecoach').in_bulk()

        return super().handle(*args, **options)
