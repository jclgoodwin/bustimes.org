import io
import requests
import zipfile
from ciso8601 import parse_datetime
import xmltodict
from django.contrib.gis.geos import Point
from django.db.models import Q
from django.core.management.base import BaseCommand
from busstops.models import DataSource, Operator, Service
from ...models import Vehicle, VehicleJourney, VehicleLocation


class Command(BaseCommand):
    cache = set()
    operators = {
        'ASC': ['ARHE', 'AKSS', 'AMTM', 'GLAR'],
        'ANE': ['ANEA', 'ANUM', 'ARDU'],
        'ANW': ['ANWE', 'AMSY', 'ACYM'],
        'ATS': ['ASES', 'ARBB', 'GLAR'],
        'AMD': ['AMNO', 'AMID', 'AFCL'],
        'AYT': ['YTIG'],
        'AYK': ['WRAY'],
        'FAR': ['FSRV'],
        'GEA': ['KCTB', 'HEDO', 'CHAM'],
        'GP': ['GPLM'],
        'CBLE': ['CBBH', 'CBNL'],
        'WPB': ['WHIP'],
        'UNO': ['UNOE', 'UNIB'],
        'UNIB': ['UNOE', 'UNIB'],
        'GNE': ['GNEL'],
        'ENS': ['ENSB'],
        'HAMSTRA': ['HAMS'],
        'RI': ['RCHC'],
        'RG': ['RGNT'],
        'WBT': ['WBTR'],
    }
    operator_cache = {}

    def get_operator(self, operator_ref):
        if operator_ref in self.operators:
            return self.operators[operator_ref]
        if operator_ref in self.operator_cache:
            return self.operator_cache[operator_ref]
        if len(operator_ref) == 4:
            try:
                operator = Operator.objects.get(id=operator_ref)
                self.operator_cache[operator_ref] = operator
                return operator
            except Operator.DoesNotExist:
                pass
        print(operator_ref)
        self.operator_cache[operator_ref] = None

    def get_vehicle(self, operator, operator_ref, vehicle_ref):
        if operator and vehicle_ref.startswith(f'{operator_ref}-'):
            vehicle_ref = vehicle_ref[len(operator_ref) + 1:]

        defaults = {
            'code': vehicle_ref,
            'source': self.source
        }

        if type(operator) is Operator:
            defaults['operator'] = operator
            if operator.parent:
                vehicles = Vehicle.objects.filter(operator__parent=operator.parent)
            else:
                vehicles = operator.vehicle_set
        elif type(operator) is list:
            defaults['operator_id'] = operator[0]
            vehicles = Vehicle.objects.filter(operator__in=operator)
        else:
            vehicles = Vehicle.objects.filter(operator=None)

        assert vehicle_ref

        condition = Q(code=vehicle_ref)
        if operator:
            if vehicle_ref.isdigit():
                defaults['fleet_number'] = vehicle_ref
                condition |= Q(code__endswith=f'-{vehicle_ref}') | Q(code__startswith=f'{vehicle_ref}_')
            else:
                if '_-_' in vehicle_ref:
                    fleet_number, reg = vehicle_ref.split('_-_', 2)
                    if fleet_number.isdigit():
                        condition |= Q(code=vehicle_ref)
                        defaults['reg'] = reg.replace('_', '')
        vehicles = vehicles.filter(condition)

        try:
            return vehicles.get_or_create(defaults)
        except Vehicle.MultipleObjectsReturned as e:
            print(e, operator, vehicle_ref)
            return vehicles.first(), False

    def get_service(self, operator, monitored_vehicle_journey):
        line_ref = monitored_vehicle_journey.get('LineRef')
        if not line_ref:
            return

        services = Service.objects.filter(current=True, line_name__iexact=line_ref)
        if type(operator) is Operator:
            services = services.filter(operator=operator)
        elif type(operator) is list:
            services = services.filter(operator__in=operator)

        try:
            return Service.objects.get()
        except Service.DoesNotExist:
            # print(e, line_ref)
            return
        except Service.MultipleObjectsReturned:
            destination_ref = monitored_vehicle_journey.get('DestinationRef')
            if not destination_ref:
                return
            try:
                return services.filter(stops__locality__stoppoint=destination_ref).distinct().get()
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                # print(e, line_ref)
                return

    def handle_item(self, item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        operator_ref = monitored_vehicle_journey['OperatorRef']
        operator = self.get_operator(operator_ref)

        if not operator and operator_ref not in self.cache:
            print(item)
            self.cache.add(operator_ref)

        vehicle_ref = monitored_vehicle_journey['VehicleRef']
        vehicle, created = self.get_vehicle(operator, operator_ref, vehicle_ref)

        recorded_at_time = parse_datetime(item['RecordedAtTime'])
        vehicle_journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')
        if vehicle_journey_ref == 'UNKNOWN':
            vehicle_journey_ref = None

        location = monitored_vehicle_journey['VehicleLocation']
        latlong = Point(float(location['Longitude']), float(location['Latitude']))

        latest_location = vehicle.latest_location
        route_name = monitored_vehicle_journey.get('LineRef') or ''
        if created or not (latest_location and latest_location.current and
                           latest_location.journey.route_name == route_name):
            journey = VehicleJourney(
                route_name=route_name,
                datetime=recorded_at_time,
                vehicle=vehicle,
                source=self.source,
                data=item
            )
            if vehicle_journey_ref:
                journey.code = vehicle_journey_ref
            journey.save()
            vehicle.latest_location = VehicleLocation(
                journey=journey,
                latlong=latlong,
                datetime=recorded_at_time,
                current=True
            )
            vehicle.latest_location.save()
            vehicle.save(update_fields=['latest_location'])
        else:
            vehicle.latest_location.latlong = latlong
            vehicle.latest_location.current = True
            vehicle.latest_location.datetime = recorded_at_time
            vehicle.latest_location.save(update_fields=['latlong', 'datetime'])

        if not vehicle.latest_location.journey.service:
            vehicle.latest_location.journey.service = self.get_service(operator, monitored_vehicle_journey)
            if vehicle.latest_location.journey.service:
                vehicle.latest_location.journey.save(update_fields=['service'])

    def handle(self, **options):
        self.source = DataSource.objects.get(name='Bus Open Data')

        response = requests.get(self.source.url)

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.namelist() == ['siri.xml']
            with archive.open('siri.xml') as open_file:
                data = xmltodict.parse(open_file)

        self.source.datetime = parse_datetime(data['Siri']['ServiceDelivery']['ResponseTimestamp'])

        for item in data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']:
            self.handle_item(item)

        self.source.save(update_fields=['datetime'])
