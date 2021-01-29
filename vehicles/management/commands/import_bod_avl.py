import io
import zipfile
import xmltodict
from django.core.cache import cache
from django.conf import settings
from datetime import timedelta
from xml.parsers.expat import ExpatError
from ciso8601 import parse_datetime
from django.contrib.gis.geos import Point
from django.db.models import Q, Exists, OuterRef
from busstops.models import Operator, OperatorCode, Service, Locality, StopPoint, ServiceCode
from bustimes.models import Trip
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleJourney, VehicleLocation


TWELVE_HOURS = timedelta(hours=12)


class Command(ImportLiveVehiclesCommand):
    source_name = 'Bus Open Data'
    wait = 20
    operators = {
        'ASC': ['AKSS', 'ARHE', 'AMTM', 'GLAR'],
        'ANE': ['ARDU', 'ANUM', 'ANEA'],
        'ANW': ['ANWE', 'AMSY', 'ACYM'],
        'ATS': ['ARBB', 'ASES', 'GLAR'],
        'AMD': ['AMID', 'AMNO', 'AFCL'],
        'CBBH': ['CBBH', 'CBNL'],
        'UNO': ['UNOE', 'UNIB'],
        'UNIB': ['UNOE', 'UNIB'],
        'TBTN': ['TBTN', 'KBUS'],
        'TDY': ['YCST', 'LNUD', 'ROST', 'BPTR', 'KDTR', 'HRGT'],
        'MTRL': ['MPTR']  # MP Travel using M Travel code (no relation!)
    }
    operator_cache = {}
    vehicle_id_cache = {}
    vehicle_cache = {}
    service_cache = {}
    reg_operators = {'BDRB', 'COMT', 'TDY', 'ROST', 'CT4N', 'TBTN', 'OTSS'}
    identifiers = {}

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item['RecordedAtTime'])

    @staticmethod
    def get_by_vehicle_journey_ref(services, monitored_vehicle_journey):
        vehicle_journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')
        if vehicle_journey_ref and vehicle_journey_ref.isdigit():
            trips = Trip.objects.filter(route__service=OuterRef("pk"), ticket_machine_code=vehicle_journey_ref)
            try:
                return services.get(Exists(trips))
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

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
            operator = Operator.objects.using(settings.READ_DATABASE).get(condition)
            self.operator_cache[operator_ref] = operator
            return operator
        except Operator.DoesNotExist:
            pass

    @staticmethod
    def get_vehicle_cache_key(item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        operator_ref = monitored_vehicle_journey['OperatorRef']
        vehicle_ref = monitored_vehicle_journey['VehicleRef'].replace(' ', '')
        return f'{operator_ref}-{vehicle_ref}'

    def get_vehicle(self, item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        operator_ref = monitored_vehicle_journey['OperatorRef']
        vehicle_ref = monitored_vehicle_journey['VehicleRef']
        cache_key = f'{operator_ref}-{vehicle_ref}'.replace(' ', '')

        if cache_key in self.vehicle_cache:
            return self.vehicle_cache[cache_key], False

        try:
            return self.vehicles.get(id=self.vehicle_id_cache[cache_key]), False
        except (KeyError, Vehicle.DoesNotExist):
            pass

        operator = self.get_operator(operator_ref)

        if operator and vehicle_ref.startswith(f'{operator_ref}-'):
            vehicle_ref = vehicle_ref[len(operator_ref) + 1:]

        assert vehicle_ref

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
            if operator_ref in self.reg_operators and vehicle.code != vehicle_ref:
                vehicle.code = vehicle_ref
                vehicle.save(update_fields=['code'])
        except Vehicle.MultipleObjectsReturned as e:
            print(e, operator, vehicle_ref)
            vehicle = vehicles.first()
            created = False

        self.vehicle_id_cache[cache_key] = vehicle.id
        return vehicle, created

    def get_service(self, operator, item, line_ref, vehicle_operator_id):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        destination_ref = monitored_vehicle_journey.get("DestinationRef")
        if destination_ref:
            if destination_ref.startswith('NT'):
                destination_ref = destination_ref[2:]

        cache_key = f"{operator}:{vehicle_operator_id}:{line_ref}:{destination_ref}"
        if cache_key in self.service_cache:
            return self.service_cache[cache_key]

        services = Service.objects.using(settings.READ_DATABASE).filter(
            Exists(ServiceCode.objects.filter(service=OuterRef('id'), scheme__endswith='SIRI', code=line_ref))
            | Q(line_name__iexact=line_ref),
            current=True
        )

        if type(operator) is Operator and operator.parent and destination_ref:
            condition = Q(parent=operator.parent)

            # in case the vehicle operator has a different parent (e.g. ABUS or HCTY)
            if vehicle_operator_id != operator.id:
                condition |= Q(id=vehicle_operator_id)

            services = services.filter(Exists(Operator.objects.filter(condition, service=OuterRef('pk'))))
            # we don't just use 'operator__parent=' because a service can have multiple operators

            # we will use the DestinationRef later to find out exactly which operator it is,
            # because the OperatorRef field is unreliable,
            # e.g. sometimes has the wrong up First Yorkshire operator code

        elif operator:
            if type(operator) is Operator:
                condition = Q(operator=operator)
                if vehicle_operator_id != operator.id:
                    condition |= Q(operator=vehicle_operator_id)
                services = services.filter(condition)
            else:
                services = services.filter(operator__in=operator)

            if type(operator) is Operator or not destination_ref:
                try:
                    return services.get()
                except Service.DoesNotExist:
                    self.service_cache[cache_key] = None
                    return
                except Service.MultipleObjectsReturned:
                    pass

        if destination_ref:
            try:
                stops = StopPoint.objects.filter(service=OuterRef("pk"), atco_code__startswith=destination_ref[:3])
                return services.get(Exists(stops))
            except Service.DoesNotExist:
                self.service_cache[cache_key] = None
                return
            except Service.MultipleObjectsReturned:
                try:
                    trips = Trip.objects.filter(route__service=OuterRef("pk"), destination=destination_ref)
                    return services.get(Exists(trips))
                except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                    pass

        else:
            try:
                latlong = self.create_vehicle_location(item).latlong
                return services.get(geometry__bboverlaps=latlong)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

        try:
            when = self.get_datetime(item)
            when = when.strftime('%a').lower()
            trips = Trip.objects.filter(**{f'calendar__{when}': True}, route__service=OuterRef("pk"))
            return services.get(Exists(trips))
        except (Service.DoesNotExist, Service.MultipleObjectsReturned):
            pass

        return self.get_by_vehicle_journey_ref(services, monitored_vehicle_journey)

    def get_journey(self, item, vehicle):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        vehicle_journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')
        if vehicle_journey_ref == 'UNKNOWN':
            vehicle_journey_ref = None

        route_name = monitored_vehicle_journey.get('PublishedLineName') or monitored_vehicle_journey.get('LineRef')

        origin_aimed_departure_time = monitored_vehicle_journey.get('OriginAimedDepartureTime')
        if origin_aimed_departure_time:
            origin_aimed_departure_time = parse_datetime(origin_aimed_departure_time)

        journey = None

        journeys = vehicle.vehiclejourney_set

        latest_location = vehicle.latest_location
        if latest_location:
            if origin_aimed_departure_time:
                if latest_location.journey.datetime == origin_aimed_departure_time:
                    journey = latest_location.journey
                else:
                    journey = journeys.filter(datetime=origin_aimed_departure_time).first()
            elif vehicle_journey_ref:
                if '_' in vehicle_journey_ref:
                    if vehicle_journey_ref == latest_location.journey.code:
                        journey = latest_location.journey
                    else:
                        journey = journeys.filter(route_name=route_name, code=vehicle_journey_ref).first()
                else:
                    datetime = self.get_datetime(item)
                    if vehicle_journey_ref == latest_location.journey.code:
                        if datetime - latest_location.journey.datetime < TWELVE_HOURS:
                            journey = latest_location.journey
                    else:
                        twelve_hours_ago = datetime - TWELVE_HOURS
                        journey = journeys.filter(
                            route_name=route_name, code=vehicle_journey_ref,
                            datetime__gt=twelve_hours_ago
                        ).last()

        if not journey:
            journey = VehicleJourney(
                route_name=route_name or '',
                vehicle=vehicle,
                source=self.source,
                data=item,
                datetime=origin_aimed_departure_time,
            )

        if vehicle_journey_ref:
            journey.code = vehicle_journey_ref

        if not journey.destination:
            destination = monitored_vehicle_journey.get('DestinationName')
            if destination:
                if route_name and destination.startswith(f'{route_name} '):  # TGTC
                    destination = destination[len(route_name) + 1:]
                journey.destination = destination
            else:
                destination_ref = monitored_vehicle_journey.get('DestinationRef')
                if destination_ref:
                    if destination_ref.startswith('NT'):
                        destination_ref = destination_ref[2:]
                    cache_key = f'stop{destination_ref}locality'
                    journey.destination = cache.get(cache_key)
                    if journey.destination is None:
                        try:
                            journey.destination = Locality.objects.get(stoppoint=destination_ref).name
                        except Locality.DoesNotExist:
                            journey.destination = ''
                        cache.set(cache_key, journey.destination)
                if not journey.destination:
                    journey.direction = monitored_vehicle_journey.get('DirectionRef', '')[:8]

        if not journey.service_id:
            operator_ref = monitored_vehicle_journey["OperatorRef"]
            operator = self.get_operator(operator_ref)
            journey.service = self.get_service(operator, item, route_name, vehicle.operator_id)

            if not operator and journey.service and journey.service.operator.all():
                operator = journey.service.operator.all()[0]
                OperatorCode.objects.create(source=self.source, operator=operator, code=operator_ref)
                vehicle.operator = operator
                vehicle.save(update_fields=['operator'])

            if journey.service and vehicle_journey_ref and '_' not in vehicle_journey_ref:
                try:
                    trips = Trip.objects.filter(route__service=journey.service, ticket_machine_code=vehicle_journey_ref)
                    journey.trip = trips.distinct('start', 'end', 'destination').get()
                except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                    pass

        return journey

    @staticmethod
    def create_vehicle_location(item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        location = monitored_vehicle_journey['VehicleLocation']
        latlong = Point(float(location['Longitude']), float(location['Latitude']))
        bearing = monitored_vehicle_journey.get('Bearing')
        if bearing:
            bearing = float(bearing)
        return VehicleLocation(
            latlong=latlong,
            heading=bearing,
            occupancy=monitored_vehicle_journey.get('Occupancy', '')
        )

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

        self.when = data['Siri']['ServiceDelivery']['ResponseTimestamp']
        self.source.datetime = parse_datetime(self.when)

        return data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']
