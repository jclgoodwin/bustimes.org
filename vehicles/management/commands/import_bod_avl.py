import io
import requests
import zipfile
from ciso8601 import parse_datetime
from datetime import datetime
import xmltodict
from django.contrib.gis.geos import Point
from django.db.models import Q
from ..import_live_vehicles import ImportLiveVehiclesCommand
from busstops.models import Operator, Service, Locality
from ...models import Vehicle, VehicleJourney, VehicleLocation


class Command(ImportLiveVehiclesCommand):
    source_name = 'Bus Open Data'

    cache = set()
    operators = {
        'ASC': ['ARHE', 'AKSS', 'AMTM', 'GLAR'],
        'ANE': ['ANEA', 'ANUM', 'ARDU'],
        'ANW': ['ANWE', 'AMSY', 'ACYM'],
        'ATS': ['ASES', 'ARBB', 'GLAR'],
        'AMD': ['AMID', 'AMNO', 'AFCL'],
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
        'WOB': ['WBTR'],
        'TDY': ['YCST', 'LNUD', 'ROST', 'BPTR', 'KDTR', 'HRGT'],
    }
    operator_cache = {}
    vehicle_cache = {}

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['RecordedAtTime'])

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

    def get_vehicle(self, item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        operator_ref = monitored_vehicle_journey['OperatorRef']
        vehicle_ref = monitored_vehicle_journey['VehicleRef']
        cache_key = f'{operator_ref}-{vehicle_ref}'
        try:
            return self.vehicles.get(id=self.vehicle_cache[cache_key]), False
        except (KeyError, Vehicle.DoesNotExist):
            pass

        operator = self.get_operator(operator_ref)

        if operator and vehicle_ref.startswith(f'{operator_ref}-'):
            vehicle_ref = vehicle_ref[len(operator_ref) + 1:]

        defaults = {
            'code': vehicle_ref,
            'source': self.source
        }

        if type(operator) is Operator:
            defaults['operator'] = operator
            if operator.parent:
                vehicles = self.vehicles.filter(operator__parent=operator.parent)
            else:
                vehicles = self.vehicles.filter(operator=operator)
        elif type(operator) is list:
            defaults['operator_id'] = operator[0]
            vehicles = self.vehicles.filter(operator__in=operator)
        else:
            vehicles = self.vehicles.filter(operator=None)

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
            vehicle, created = vehicles.get_or_create(defaults)
        except Vehicle.MultipleObjectsReturned as e:
            print(e, operator, vehicle_ref)
            vehicle = vehicles.first()
            created = False

        self.vehicle_cache[cache_key] = vehicle.id
        return vehicle, created

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

    def get_journey(self, item, vehicle):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        vehicle_journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')
        if vehicle_journey_ref == 'UNKNOWN':
            vehicle_journey_ref = None

        route_name = monitored_vehicle_journey.get('LineRef') or ''

        origin_aimed_departure_time = monitored_vehicle_journey.get('OriginAimedDepartureTime')
        if origin_aimed_departure_time:
            origin_aimed_departure_time = parse_datetime(origin_aimed_departure_time)

        journey = None

        latest_location = vehicle.latest_location
        if latest_location:
            if origin_aimed_departure_time == latest_location.journey.datetime:
                journey = latest_location.journey
            elif vehicle_journey_ref:
                if vehicle_journey_ref != latest_location.journey.code and '_' in vehicle_journey_ref:
                    journey = vehicle.vehiclejourney_set.filter(route_name=route_name, code=vehicle_journey_ref).first()

            if not journey:
                journey = vehicle.vehiclejourney_set.filter(datetime=origin_aimed_departure_time).first()

        if not journey:
            journey = VehicleJourney(
                route_name=route_name,
                vehicle=vehicle,
                source=self.source,
                data=item,
                datetime=origin_aimed_departure_time,
                destination=monitored_vehicle_journey.get('DestinationName') or ''
            )

        if vehicle_journey_ref:
            journey.code = vehicle_journey_ref

        if not journey.destination:
            destination_ref = monitored_vehicle_journey.get('DestinationRef')
            if destination_ref:
                try:
                    journey.destination = Locality.objects.get(stoppoint=destination_ref).name
                except Locality.DoesNotExist:
                    pass

        if latest_location and (latest_location.journey.code == journey.code
                                and latest_location.journey.route_name == journey.route_name):
            journey.service = latest_location.journey.service
        else:
            operator_ref = monitored_vehicle_journey['OperatorRef']
            operator = self.get_operator(operator_ref)
            journey.service = self.get_service(operator, monitored_vehicle_journey)

        return journey

    def create_vehicle_location(self, item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        location = monitored_vehicle_journey['VehicleLocation']
        latlong = Point(float(location['Longitude']), float(location['Latitude']))
        return VehicleLocation(
            latlong=latlong,
        )

    def get_items(self):
        before = datetime.now()

        response = requests.get(self.source.url)

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert archive.namelist() == ['siri.xml']
            with archive.open('siri.xml') as open_file:
                data = xmltodict.parse(open_file)

        self.source.datetime = parse_datetime(data['Siri']['ServiceDelivery']['ResponseTimestamp'])

        for item in data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']:
            yield item

        after = datetime.now()

        print(after - before)

        # self.source.save(update_fields=['datetime'])
