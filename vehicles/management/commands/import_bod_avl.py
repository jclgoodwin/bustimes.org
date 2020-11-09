import io
import zipfile
from xml.parsers.expat import ExpatError
from ciso8601 import parse_datetime
from multiprocessing.dummy import Pool
import xmltodict
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.db.models import Q, Exists, OuterRef
from ..import_live_vehicles import ImportLiveVehiclesCommand
from busstops.models import Operator, Service, Locality, StopPoint
from bustimes.models import Trip
from ...models import Vehicle, VehicleJourney, VehicleLocation


class Command(ImportLiveVehiclesCommand):
    source_name = 'Bus Open Data'
    wait = 30
    cache = set()
    operators = {
        'ASC': ['AKSS', 'ARHE', 'AMTM', 'GLAR'],
        'ANE': ['ANEA', 'ANUM', 'ARDU'],
        'ANW': ['ANWE', 'AMSY', 'ACYM'],
        'ATS': ['ARBB', 'ASES', 'GLAR'],
        'AMD': ['AMID', 'AMNO', 'AFCL'],
        'AYT': ['YTIG'],
        'AYK': ['WRAY'],
        'FAR': ['FSRV'],
        'GOEA': ['KCTB', 'HEDO', 'CHAM'],
        'BOWE': ['HIPK'],
        'CBBH': ['CBBH', 'CBNL'],
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
        'PB': ['MTLN'],
        'YOP': ['KJTR']
    }
    operator_cache = {}
    vehicle_cache = {}
    reg_operators = {'BDRB', 'COMT', 'TDY', 'ROST'}

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['RecordedAtTime'])

    def get_operator(self, operator_ref):
        if operator_ref == "SCEM":
            operator_ref = "SCGH"
        elif operator_ref == "SCSO":
            operator_ref = "SCCO"

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
                condition = Q(operator__parent=operator.parent)

                # Abus operate the 349 using First ticket machines
                if operator.id == 'FBRI' and not vehicle_ref.isdigit() and vehicle_ref.isupper():
                    condition |= Q(operator='ABUS')
                # Connexions Buses 64
                elif operator.id == 'FWYO' and not vehicle_ref.isdigit() and vehicle_ref.isupper():
                    condition |= Q(operator='HCTY')

                vehicles = self.vehicles.filter(condition)
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
                        defaults['fleet_number'] = fleet_number
                        reg = reg.replace('_', '')
                        defaults['reg'] = reg
                        if operator_ref in self.reg_operators:
                            condition |= Q(reg=reg)
                elif operator_ref in self.reg_operators:
                    reg = vehicle_ref.replace('_', '')
                    condition |= Q(reg=reg)
                elif operator_ref == 'WHIP':
                    code = vehicle_ref.replace('_', '')
                    condition |= Q(fleet_code=code)
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

        services = Service.objects.filter(current=True)

        if line_ref == 'TP':  # High Peak Transpeak
            services = services.filter(line_name__startswith=line_ref)
        else:
            services = services.filter(line_name__iexact=line_ref)

        if type(operator) is Operator and operator.parent == 'Stagecoach':
            services = services.filter(operator__parent='Stagecoach')
        else:
            if type(operator) is Operator:
                services = services.filter(operator=operator)
            elif type(operator) is list:
                services = services.filter(operator__in=operator)

            try:
                return services.get()
            except Service.DoesNotExist:
                return
            except Service.MultipleObjectsReturned:
                pass

        destination_ref = monitored_vehicle_journey.get('DestinationRef')
        if destination_ref:
            try:
                stops = StopPoint.objects.filter(service=OuterRef("pk"), locality__stoppoint=destination_ref)
                return services.filter(Exists(stops)).get()
            except Service.DoesNotExist:
                return
            except Service.MultipleObjectsReturned:
                pass

        vehicle_journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')
        if vehicle_journey_ref and vehicle_journey_ref.isdigit():
            try:
                trips = Trip.objects.filter(route__service=OuterRef('pk'), ticket_machine_code=vehicle_journey_ref)
                return services.filter(Exists(trips)).get()
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

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

        # do destination now, in case the route name is in the destination field
        destination = monitored_vehicle_journey.get('DestinationName') or ''
        if vehicle.operator_id == 'TGTC' and destination and not route_name:
            parts = destination.split()
            if parts[0].isdigit() or parts[0][:-1].isdigit():
                route_name = parts[0]
                destination = ' '.join(parts[1:])
                monitored_vehicle_journey['LineRef'] = route_name

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
                destination=destination
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

        if (
            latest_location and latest_location.journey.service
            and latest_location.journey.code == journey.code
            and latest_location.journey.route_name == journey.route_name
        ):
            journey.service = latest_location.journey.service
        else:
            operator_ref = monitored_vehicle_journey['OperatorRef']
            if operator_ref == 'FWYO' and vehicle.operator_id == 'HCTY':
                operator = ['FWYO', 'HCTY']  # First West Yorkshire/Connexions
            elif operator_ref == 'RRAR':
                operator = ['RRAR', 'FTVA']  # Reading RailAir/First Berkshire
            elif operator_ref == 'ROST':
                operator = ['ROST', 'LNUD']  # Rosso/Blackburn
            else:
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

    def update(self):
        now = timezone.now()

        self.current_location_ids = set()

        pool = Pool(4)
        items = self.get_items()
        if items:
            pool.starmap(self.handle_item, ((item, now) for item in items))

            self.get_old_locations().update(current=False)

            print(self.operator_cache)
        else:
            return 300  # no items - wait five minutes

        time_taken = (timezone.now() - now)
        print(time_taken)
        time_taken = time_taken.total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait

    def get_items(self):
        response = self.session.get(self.source.url, params=self.source.settings)
        if not response.ok:
            if 'datafeed' in self.source.url:
                print(response.content.decode())
            else:
                print(response)
            return

        if 'datafeed' in self.source.url:
            try:
                data = xmltodict.parse(
                    response.content,
                    dict_constructor=dict  # override OrderedDict, cos dict is ordered in modern versions of Python
                )
            except ExpatError:
                print(response.content.decode())
                return
        else:
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    assert archive.namelist() == ['siri.xml']
                    with archive.open('siri.xml') as open_file:
                        try:
                            data = xmltodict.parse(open_file, dict_constructor=dict)
                        except ExpatError:
                            print(open_file.read())
                            return
            except zipfile.BadZipFile:
                print(response.content.decode())

        self.source.datetime = parse_datetime(data['Siri']['ServiceDelivery']['ResponseTimestamp'])

        return data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']
