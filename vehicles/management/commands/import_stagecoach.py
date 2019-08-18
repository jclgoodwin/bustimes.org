import json
from datetime import datetime
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point, Polygon
from django.contrib.gis.db.models import Extent, Q
from django.utils import timezone
from busstops.models import Operator, Service
from ...models import VehicleLocation, VehicleJourney
from ..import_live_vehicles import ImportLiveVehiclesCommand


def get_latlong(item):
    return Point(float(item['lo']), float(item['la']))


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
        geojson = {"type": "FeatureCollection", "features": []}
        i = 0
        operators = Operator.objects.filter(name__startswith='Stagecoach', service__current=True, vehicle_mode='bus')
        operators = operators.exclude(service__servicecode__scheme__endswith=' SIRI', service__tracking=True)
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
                    geojson['features'].append({
                        "type": "Feature",
                        "geometry": json.loads(polygon.json),
                        "properties": {
                            "name": str(i)
                        }
                    })

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
        print(json.dumps(geojson))

    def get_items(self):
        for params in self.get_boxes():
            try:
                response = self.session.get(self.url, params=params, timeout=50)
                print(response.url)
                for item in response.json()['services']:
                    yield item
            except (RequestException, KeyError) as e:
                print(e)
                continue

    @staticmethod
    def get_datetime(item):
        return datetime.fromtimestamp(int(item['ut']) / 1000, timezone.utc)

    def get_vehicle(self, item):
        vehicle = item['fn']
        if len(vehicle) > 5:
            return None, None
        if vehicle in self.vehicles_ids:
            vehicle = self.vehicles.objects.get(id=self.vehicles_ids[vehicle])
            created = False
        else:
            operator_id = self.operator_ids.get(item['oc'], item['oc'])
            operator = self.operators.get(operator_id)
            if not operator:
                try:
                    operator = Operator.objects.get(id=operator_id)
                except Operator.DoesNotExist as e:
                    print(operator_id, e)
                defaults = {
                    'source': self.source
                }
            if operator:
                defaults['operator'] = operator
            if vehicle.isdigit():
                defaults['fleet_number'] = vehicle
            if not operator or operator.name.startswith('Stagecoach '):
                vehicle, created = self.vehicles.get_or_create(defaults, operator__name__startswith='Stagecoach ',
                                                               code=vehicle)
            else:  # Scottish Citylink
                vehicle, created = self.vehicles.get_or_create(defaults, operator=operator, code=vehicle)

        self.vehicles_ids[item['fn']] = vehicle.id

        latest_location = vehicle.latest_location
        if latest_location and latest_location.journey.source_id != self.source.id:
            return None, None

        return vehicle, created

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        journey.code = item.get('td', '')
        journey.destination = item.get('dd', '')
        journey.route_name = item.get('sn', '')

        if item['ao']:
            journey.datetime = datetime.fromtimestamp(int(item['ao']) / 1000, timezone.utc)

        latest_location = vehicle.latest_location
        if (
            latest_location and latest_location.journey.code == journey.code and
            latest_location.journey.route_name == journey.route_name and latest_location.journey.service
        ):
            journey.service = latest_location.journey.service
        elif journey.route_name:
            service = journey.route_name
            alternatives = {
                'PULS': 'Pulse',
                'FLCN': 'Falcon',
                'TUBE': 'Oxford Tube',
                'SPRI': 'spring',
                'PRO': 'pronto',
                'SA': 'The Sherwood Arrow',
                'Yo-Y': 'YOYO',
                'TRIA': 'Triangle',
            }
            if service in alternatives:
                service = alternatives[service]
            services = Service.objects.filter(current=True, operator__name__startswith='Stagecoach ')
            services = services.filter(Q(line_name__iexact=service) | Q(service_code__icontains=f'-{service}-'))
            services = services.filter(stops__locality__stoppoint=item['or']).distinct()
            try:
                journey.service = services.get()

                for operator in journey.service.operator.all():
                    if operator.name.startswith('Stagecoach '):
                        if vehicle.operator_id != operator.id:
                            vehicle.operator_id = operator.id
                            vehicle.save(update_fields=['operator'])
                        break
            except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
                print(e, item['or'], service)

        return journey

    def create_vehicle_location(self, item):
        bearing = item['hg']
        return VehicleLocation(
            latlong=get_latlong(item),
            heading=bearing
        )
