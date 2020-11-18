import io
import zipfile
from xml.parsers.expat import ExpatError
from ciso8601 import parse_datetime
import xmltodict
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.exceptions import ChannelFull
from django.contrib.gis.geos import Point
from django.db.models import Q, Exists, OuterRef
from ..import_live_vehicles import ImportLiveVehiclesCommand
from busstops.models import Operator, Service, Locality, StopPoint, ServiceCode
from bustimes.models import Trip
from ...models import Vehicle, VehicleJourney, VehicleLocation


class Command(ImportLiveVehiclesCommand):
    source_name = 'Bus Open Data'
    wait = 20
    cache = set()
    operators = {
        'ASC': ['AKSS', 'ARHE', 'AMTM', 'GLAR'],
        'ANE': ['ARDU', 'ANUM', 'ANEA'],
        'ANW': ['ANWE', 'AMSY', 'ACYM'],
        'ATS': ['ARBB', 'ASES', 'GLAR'],
        'AMD': ['AMID', 'AMNO', 'AFCL'],
        'GOEA': ['KCTB', 'HEDO', 'CHAM'],
        'CBBH': ['CBBH', 'CBNL'],
        'UNO': ['UNOE', 'UNIB'],
        'UNIB': ['UNOE', 'UNIB'],
        'TDY': ['YCST', 'LNUD', 'ROST', 'BPTR', 'KDTR', 'HRGT'],
    }
    operator_cache = {}
    vehicle_cache = {}
    service_cache = {}
    reg_operators = {'BDRB', 'COMT', 'TDY', 'ROST'}
    identifiers = {}

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

        condition = Exists(self.source.operatorcode_set.filter(operator=OuterRef('id'), code=operator_ref))
        if len(operator_ref) == 4:
            condition |= Q(id=operator_ref)

        try:
            operator = Operator.objects.get(condition)
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

                if not vehicle_ref.isdigit() and vehicle_ref.isupper():
                    # Abus operate the 349 using First ticket machines
                    if operator.id == "FBRI":
                        condition |= Q(operator="ABUS")
                    # Connexions Buses 64
                    elif operator.id == "FWYO":
                        condition |= Q(operator="HCTY")

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

    def get_service(self, operator, item, vehicle_operator_id):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        line_ref = monitored_vehicle_journey.get('LineRef')
        if not line_ref:
            return

        destination_ref = monitored_vehicle_journey.get("DestinationRef")

        cache_key = f"{operator}:{vehicle_operator_id}:{line_ref}:{destination_ref}"
        if cache_key in self.service_cache:
            return self.service_cache[cache_key]

        services = Service.objects.filter(
            Exists(ServiceCode.objects.filter(service=OuterRef('id'), scheme__endswith=' SIRI', code=line_ref))
            | Q(line_name__iexact=line_ref),
            current=True
        )

        if type(operator) is Operator and operator.parent and destination_ref:
            services = services.filter(operator__parent=operator.parent)
            # we will use the destination ref to find out exactly which operator it is

        else:
            if type(operator) is Operator:
                condition = Q(operator=operator)
                if vehicle_operator_id != operator.id:
                    condition |= Q(operator=vehicle_operator_id)
                services = services.filter(condition)
            elif type(operator) is list:
                services = services.filter(operator__in=operator)

            try:
                return services.get()
            except Service.DoesNotExist:
                self.service_cache[cache_key] = None
                return
            except Service.MultipleObjectsReturned:
                pass

        if destination_ref:
            try:
                stops = StopPoint.objects.filter(service=OuterRef("pk"), locality__stoppoint=destination_ref)
                return services.filter(Exists(stops)).get()
            except Service.DoesNotExist:
                self.service_cache[cache_key] = None
                return
            except Service.MultipleObjectsReturned:
                try:
                    trips = Trip.objects.filter(route__service=OuterRef("pk"), destination=destination_ref)
                    return services.filter(Exists(trips)).get()
                except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                    pass

        try:
            when = self.get_datetime(item)
            when = when.strftime('%a').lower()
            trips = Trip.objects.filter(**{f'calendar__{when}': True}, route__service=OuterRef("pk"))
            return services.filter(Exists(trips)).get()
        except (Service.DoesNotExist, Service.MultipleObjectsReturned):
            pass

        vehicle_journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')
        if vehicle_journey_ref and vehicle_journey_ref.isdigit():
            try:
                trips = Trip.objects.filter(route__service=OuterRef("pk"), ticket_machine_code=vehicle_journey_ref)
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
            operator_ref = monitored_vehicle_journey["OperatorRef"]
            if operator_ref == "FWYO":
                if vehicle.operator_id == "HCTY":
                    operator = ["HCTY"]  # First West Yorkshire/Connexions
                else:
                    operator = ["FWYO", "FLDS"]
            elif operator_ref == "FHAL":
                operator = ["FHAL", "FHUD"]
            elif operator_ref == "FBRI" and vehicle.operator_id == "ABUS":
                operator = ["ABUS"]
            elif operator_ref == "RRAR":
                operator = ["RRAR", "FTVA"]  # Reading RailAir/First Berkshire
            elif operator_ref == "ROST":
                operator = ["ROST", "LNUD", "BPTR"]  # Rosso/Blackburn/Burnley
            else:
                operator = self.get_operator(operator_ref)
            journey.service = self.get_service(operator, item, vehicle.operator_id)

        return journey

    @staticmethod
    def create_vehicle_location(item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        location = monitored_vehicle_journey['VehicleLocation']
        latlong = Point(float(location['Longitude']), float(location['Latitude']))
        return VehicleLocation(
            latlong=latlong,
        )

    def send_items(self, send, items):
        modified_items = []
        identifiers = {}
        for item in items:
            monitored_vehicle_journey = item['MonitoredVehicleJourney']
            key = f"{monitored_vehicle_journey['OperatorRef']}-{monitored_vehicle_journey['VehicleRef']}"
            if self.identifiers.get(key) != item['RecordedAtTime']:
                modified_items.append(item)
                identifiers[key] = item['RecordedAtTime']

        try:
            send('sirivm', {
                'type': 'sirivm',
                'items': modified_items
            })
            self.identifiers.update(identifiers)
        except ChannelFull:
            print('full')

    def update(self):
        now = timezone.now()

        items = self.get_items()

        if items:
            send = async_to_sync(get_channel_layer().send)
            chunk = []
            for item in items:
                chunk.append(item)

                if len(chunk) == 100:
                    self.send_items(send, chunk)
                    chunk = []

            # remainder
            self.send_items(send, chunk)
        else:
            return 300  # no items - wait five minutes

        time_taken = timezone.now() - now
        print(time_taken)
        time_taken = time_taken.total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait

    @staticmethod
    def items_from_response(response):
        return xmltodict.parse(
            response,
            dict_constructor=dict,  # override OrderedDict, cos dict is ordered in modern versions of Python
            force_list=['VehicleActivity']
        )

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
                data = self.items_from_response(response.content)
            except ExpatError:
                print(response.content.decode())
                return
        else:
            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                    assert archive.namelist() == ['siri.xml']
                    with archive.open('siri.xml') as open_file:
                        try:
                            data = self.items_from_response(open_file)
                        except ExpatError:
                            print(open_file.read())
                            return
            except zipfile.BadZipFile:
                print(response.content.decode())
                return

        self.source.datetime = parse_datetime(data['Siri']['ServiceDelivery']['ResponseTimestamp'])

        return data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']
