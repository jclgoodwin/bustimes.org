# import json
from time import sleep
from datetime import datetime
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models import Extent
from django.utils import timezone
from busstops.models import Operator, Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand, logger


def get_latlong(item):
    return Point(float(item['lo']), float(item['la']))


def get_datetime(timestamp):
    if timestamp:
        return datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc)


class Command(ImportLiveVehiclesCommand):
    url = 'https://api.stagecoach-technology.net/vehicle-tracking/v1/vehicles'
    source_name = 'Stagecoach'
    operator_ids = {
        'SCEM': 'SCLI',
        'SCSO': 'SCCO'
    }
    operators = {}
    vehicles_ids = {}

    def get_boxes(self):
        # geojson = {"type": "FeatureCollection", "features": []}
        i = 0
        operators = Operator.objects.filter(parent='Stagecoach', service__current=True, vehicle_mode='bus')
        services = Service.objects.filter(operator__in=operators)
        extent = services.aggregate(Extent('geometry'))['geometry__extent']

        lng = extent[0]
        while lng <= extent[2]:
            lat = extent[1]
            while lat <= extent[3]:
                bbox = (
                    lng,
                    lat,
                    lng + 1.5,
                    lat + 1,
                )
                polygon = Polygon.from_bbox(bbox)
                i += 1
                if services.filter(geometry__bboverlaps=polygon).exists():
                    # geojson['features'].append({
                    #     "type": "Feature",
                    #     "geometry": json.loads(polygon.json),
                    #     "properties": {
                    #         "name": str(i)
                    #     }
                    # })

                    yield {
                        'latne': bbox[3],
                        'lngne': bbox[2],
                        'latsw': bbox[1],
                        'lngsw': bbox[0],
                        # 'clip': 1,
                        # 'descriptive_fields': 1
                    }

                lat += 1
            lng += 1.5
        # print(json.dumps(geojson))

    def get_items(self):
        for params in self.get_boxes():
            try:
                response = self.session.get(self.url, params=params, timeout=50)
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
                vehicles = self.vehicles.filter(operator__parent='Stagecoach')
                vehicle, created = vehicles.get_or_create(defaults, code=vehicle_code)
                self.vehicles_ids[vehicle_code] = vehicle.id
            else:
                return None, None

        return vehicle, created

    def get_journey(self, item, vehicle):
        if item['ao']:  # aimed origin departure time
            departure_time = get_datetime(item['ao'])
            code = item.get('td', '')  # trip id
        else:
            departure_time = None
            code = ''

        if code and departure_time:
            journey = vehicle.vehiclejourney_set.filter(code=code, datetime=departure_time).first()
        else:
            journey = None
        if not journey:
            journey = VehicleJourney(
                code=code,
                datetime=departure_time
            )

        if code:
            journey.destination = item.get('dd', '')

        journey.route_name = item.get('sn', '')

        journey.text = item

        latest_location = vehicle.latest_location
        if journey.service:
            pass
        elif (
            latest_location and latest_location.journey.code == journey.code and
            latest_location.journey.route_name == journey.route_name and latest_location.journey.service
        ):
            journey.service = latest_location.journey.service
        elif journey.route_name:
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
            services = Service.objects.filter(current=True, operator__parent='Stagecoach')
            services = services.filter(stops__locality__stoppoint=item['or']).distinct()
            latlong = get_latlong(item)
            try:
                journey.service = self.get_service(services.filter(line_name__iexact=service), latlong)
                if journey.service:
                    return journey
            except Service.DoesNotExist:
                pass
            try:
                journey.service = self.get_service(services.filter(service_code__icontains=f'-{service}-'), latlong)
                if journey.service:
                    return journey
            except Service.DoesNotExist:
                pass

            if not journey.service:
                print(service, item['or'], vehicle.get_absolute_url())

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
