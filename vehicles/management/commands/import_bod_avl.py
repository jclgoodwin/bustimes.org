import io
import zipfile
import xmltodict
import functools
from django.core.cache import cache
from django.conf import settings
from django.db import IntegrityError
from datetime import timedelta, date
from ciso8601 import parse_datetime
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q, Exists, OuterRef
from django.utils.timezone import localtime
from busstops.models import Operator, OperatorCode, Service, Locality, StopPoint, ServiceCode
from bustimes.models import Trip, Route
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleJourney, VehicleLocation


TWELVE_HOURS = timedelta(hours=12)


class Command(ImportLiveVehiclesCommand):
    source_name = 'Bus Open Data'
    wait = 20
    vehicle_id_cache = {}
    vehicle_cache = {}
    reg_operators = {'BDRB', 'COMT', 'TDY', 'ROST', 'CT4N', 'TBTN', 'OTSS'}
    services = Service.objects.using(settings.READ_DATABASE).filter(current=True).defer('geometry', 'search_vector')

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

    @staticmethod
    def get_destination_name(destination_ref):
        destination_ref = destination_ref.removeprefix('NT')
        cache_key = f'stop{destination_ref}locality'
        destination = cache.get(cache_key)
        if destination is None:
            try:
                destination = Locality.objects.get(stoppoint=destination_ref).name
            except Locality.DoesNotExist:
                if destination_ref.isdigit() and destination_ref[0] != '0' and destination_ref[2] == '0':
                    destination = Command.get_destination_name(f'0{destination_ref}')
                destination = ''
            cache.set(cache_key, destination)
        return destination

    @functools.cache
    def get_operator(self, operator_ref):
        if operator_ref == 'TFLO':
            return

        # all operators with a matching OperatorCode,
        # or (if no such OperatorCode) the one with a matching id
        operator_codes = self.source.operatorcode_set.filter(code=operator_ref)
        return Operator.objects.filter(
            Exists(operator_codes.filter(operator=OuterRef('id'))) |
            Q(id=operator_ref) & ~Exists(operator_codes)
        )

    @staticmethod
    def get_vehicle_cache_key(item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        operator_ref = monitored_vehicle_journey['OperatorRef']
        vehicle_ref = monitored_vehicle_journey['VehicleRef'].replace(' ', '')
        return f'{operator_ref}-{vehicle_ref}'

    @staticmethod
    def get_line_name_query(line_ref):
        return (
            Exists(ServiceCode.objects.filter(service=OuterRef('id'), scheme__endswith='SIRI', code=line_ref))
            | Q(line_name__iexact=line_ref)
            | Exists(Route.objects.filter(service=OuterRef('id'), line_name__iexact=line_ref))
        )

    def get_vehicle(self, item):
        # cached wrapper for actually_get_vehicle

        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        operator_ref = monitored_vehicle_journey['OperatorRef']
        vehicle_ref = monitored_vehicle_journey['VehicleRef']

        if vehicle_ref == '20920' and operator_ref == 'DIAM':  # correct BU52/BU54 RHU confusion
            vehicle_ref = '20919'

        cache_key = f'{operator_ref}-{vehicle_ref}'.replace(' ', '')

        if cache_key in self.vehicle_cache:
            return self.vehicle_cache[cache_key], False

        try:
            return self.vehicles.get(id=self.vehicle_id_cache[cache_key]), False
        except (KeyError, Vehicle.DoesNotExist):
            pass

        vehicle, created = self.actually_get_vehicle(vehicle_ref, operator_ref, item)

        self.vehicle_id_cache[cache_key] = vehicle.id

        return vehicle, created

    def actually_get_vehicle(self, vehicle_ref, operator_ref, item):
        vehicle_ref = vehicle_ref.removeprefix(f'{operator_ref}-')
        vehicle_ref = vehicle_ref.removeprefix('nibs_').removeprefix('stephensons_').removeprefix('coachservices_')

        if operator_ref == 'TFLO':
            try:
                return self.vehicles.get(vehiclecode__scheme=operator_ref, vehiclecode__code=vehicle_ref), False
            except Vehicle.DoesNotExist:
                pass

        if not vehicle_ref.isdigit() and len(vehicle_ref) > 7:
            try:
                return self.vehicles.get(code=vehicle_ref), False
            except (Vehicle.DoesNotExist, Vehicle.MultipleObjectsReturned):
                pass

        defaults = {
            'code': vehicle_ref,
            'source': self.source
        }

        operators = self.get_operator(operator_ref)

        if not operators:
            vehicles = self.vehicles.filter(operator=None)
            if operator_ref == 'TFLO':
                defaults['livery_id'] = 262
        elif len(operators) == 1:
            operator = operators[0]

            defaults['operator'] = operator
            if operator.parent:
                condition = Q(operator__parent=operator.parent)

                if operator.id == 'FBRI' and len(vehicle_ref) == 4:
                    condition |= Q(operator="NCTP")
                vehicles = self.vehicles.filter(condition)
            else:
                vehicles = self.vehicles.filter(operator=operator)
        else:
            defaults['operator'] = operators[0]
            vehicles = self.vehicles.filter(operator__in=operators)

        condition = Q(code=vehicle_ref)
        if operators:
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

        if operator_ref == 'MSOT':  # Marshalls of Sutton on Trent
            defaults['fleet_code'] = vehicle_ref
        elif 'fleet_number' not in defaults:
            # VehicleUniqueId
            try:
                fleet_number = item['Extensions']['VehicleJourney']['VehicleUniqueId']
                if len(fleet_number) < len(vehicle_ref):
                    defaults['fleet_code'] = fleet_number
                if fleet_number.isdigit():
                    defaults['fleet_number'] = fleet_number
            except (KeyError, TypeError):
                pass

        try:
            vehicle, created = vehicles.get_or_create(defaults)
            if operator_ref in self.reg_operators and vehicle.code != vehicle_ref:
                vehicle.code = vehicle_ref
                if fleet_number != vehicle.fleet_code:
                    vehicle.fleet_code = fleet_number
                    if fleet_number.isdigit():
                        vehicle.fleet_number = fleet_number
                    vehicle.save(update_fields=['code', 'fleet_code', 'fleet_number'])
                else:
                    vehicle.save(update_fields=['code'])
            elif 'fleet_code' in defaults and not vehicle.fleet_code:
                vehicle.fleet_code = defaults['fleet_code']
                if 'fleet_number' in defaults:
                    vehicle.fleet_number = defaults['fleet_number']
                vehicle.save(update_fields=['fleet_code', 'fleet_number'])
        except Vehicle.MultipleObjectsReturned as e:
            print(e, operator_ref, vehicle_ref)
            vehicle = vehicles.first()
            created = False

        return vehicle, created

    def get_service(self, operators, item, line_ref, vehicle_operator_id):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']

        destination_ref = monitored_vehicle_journey.get("DestinationRef")

        cache_key = f"{vehicle_operator_id}:{line_ref}:{destination_ref}".replace(' ', '')
        service = cache.get(cache_key)
        if service is not None:
            return service or None

        if destination_ref:
            if ' ' in destination_ref or len(destination_ref) < 4 or destination_ref[:3] == '000':
                # destination ref is a fake ATCO code, or maybe a postcode or suttin
                destination_ref = None
            else:
                destination_ref = destination_ref.removeprefix('NT')  # nottingham

        # filter by LineRef or (if present and different) TicketMachineServiceCode
        line_name_query = self.get_line_name_query(line_ref)
        try:
            ticket_machine_service_code = (
                item['Extensions']['VehicleJourney']['Operational']['TicketMachine']['TicketMachineServiceCode']
            )
        except (KeyError, TypeError):
            pass
        else:
            if ticket_machine_service_code.lower() != line_ref.lower():
                line_name_query |= self.get_line_name_query(ticket_machine_service_code)

        services = self.services.filter(line_name_query).defer('geometry')

        if not operators:
            pass
        elif len(operators) == 1 and operators[0].parent and destination_ref:
            operator = operators[0]

            # first try taking OperatorRef at face value
            # (temporary while some services may have no StopUsages)
            try:
                return services.filter(operator=operator).get()
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

            condition = Q(parent=operator.parent)

            # in case the vehicle operator has a different parent (e.g. HCTY)
            if vehicle_operator_id != operator.id:
                condition |= Q(id=vehicle_operator_id)

            services = services.filter(Exists(Operator.objects.filter(condition, service=OuterRef('pk'))))
            # we don't just use 'operator__parent=' because a service can have multiple operators

            # we will use the DestinationRef later to find out exactly which operator it is,
            # because the OperatorRef field is unreliable,
            # e.g. sometimes has the wrong up First Yorkshire operator code

        elif operators:
            if len(operators) == 1:
                operator = operators[0]
                condition = Q(operator=operator)
                if vehicle_operator_id != operator.id:
                    condition |= Q(operator=vehicle_operator_id)
                services = services.filter(condition)
            else:
                services = services.filter(operator__in=operators)

            if len(operators) == 1 or not destination_ref:
                try:
                    return services.get()
                except Service.DoesNotExist:
                    cache.set(cache_key, False, 3600)  # cache 'service not found' for an hour
                    return
                except Service.MultipleObjectsReturned:
                    pass

        if destination_ref:
            # cope with a missing leading zero
            atco_code__startswith = Q(atco_code__startswith=destination_ref[:3])
            if destination_ref.isdigit() and destination_ref[0] != '0' and destination_ref[3] == '0':
                atco_code__startswith |= Q(atco_code__startswith=f'0{destination_ref}[:3]')

            stops = StopPoint.objects.filter(atco_code__startswith, service=OuterRef("pk"))
            services = services.filter(Exists(stops))
            try:
                return services.get()
            except Service.DoesNotExist:
                cache.set(cache_key, False, 3600)
                return
            except Service.MultipleObjectsReturned:
                condition = Exists(StopPoint.objects.filter(
                    service=OuterRef("pk"), atco_code=destination_ref
                ))
                origin_ref = monitored_vehicle_journey.get("OriginRef")
                if origin_ref:
                    condition &= Exists(StopPoint.objects.filter(
                        service=OuterRef("pk"), atco_code=origin_ref
                    ))
                try:
                    return services.get(condition)
                except Service.DoesNotExist:
                    pass
                except Service.MultipleObjectsReturned:
                    services = services.filter(condition)

        else:
            latlong = self.create_vehicle_location(item).latlong
            try:
                return services.get(geometry__bboverlaps=latlong)
            except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                pass

        try:
            # in case there was MultipleObjectsReturned caused by a bogus ServiceCode
            # e.g. both Somerset 21 and 21A have 21A ServiceCode
            return services.get(line_name__iexact=line_ref)
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

        journey_ref = monitored_vehicle_journey.get('VehicleJourneyRef')

        if not journey_ref:
            try:
                journey_ref = monitored_vehicle_journey['FramedVehicleJourneyRef']['DatedVehicleJourneyRef']
            except KeyError:
                pass

        try:
            ticket_machine = item['Extensions']['VehicleJourney']['Operational']['TicketMachine']
            journey_code = ticket_machine['JourneyCode']
        except (KeyError, TypeError):
            journey_code = journey_ref
            ticket_machine = None
        else:
            if journey_code == '0000':
                journey_code = journey_ref
            elif not journey_ref or '_' in journey_ref:
                journey_ref = journey_code  # what we will use for finding matching trip

        route_name = monitored_vehicle_journey.get('PublishedLineName') or monitored_vehicle_journey.get('LineRef', '')
        if not route_name and ticket_machine:
            route_name = ticket_machine.get('TicketMachineServiceCode', '')

        origin_aimed_departure_time = monitored_vehicle_journey.get('OriginAimedDepartureTime')
        if origin_aimed_departure_time:
            origin_aimed_departure_time = parse_datetime(origin_aimed_departure_time)

        journey = None

        journeys = vehicle.vehiclejourney_set.defer('data')

        datetime = self.get_datetime(item)

        if origin_aimed_departure_time and origin_aimed_departure_time - datetime > timedelta(hours=20):
            origin_aimed_departure_time -= timedelta(hours=24)

        latest_journey = vehicle.latest_journey
        if latest_journey:
            if origin_aimed_departure_time:
                if latest_journey.datetime == origin_aimed_departure_time:
                    journey = latest_journey
                else:
                    journey = journeys.filter(datetime=origin_aimed_departure_time).first()
            elif journey_code:
                if '_' in journey_code:
                    if route_name == latest_journey.route_name and journey_code == latest_journey.code:
                        journey = latest_journey
                    else:
                        journey = journeys.filter(route_name=route_name, code=journey_code).first()
                else:
                    datetime = self.get_datetime(item)
                    if route_name == latest_journey.route_name and journey_code == latest_journey.code:
                        if datetime - latest_journey.datetime < TWELVE_HOURS:
                            journey = latest_journey
                    else:
                        twelve_hours_ago = datetime - TWELVE_HOURS
                        journey = journeys.filter(
                            route_name=route_name, code=journey_code,
                            datetime__gt=twelve_hours_ago
                        ).last()

        if not journey:
            journey = VehicleJourney(
                route_name=route_name,
                vehicle=vehicle,
                source=self.source,
                data=item,
                datetime=origin_aimed_departure_time,
            )

        if journey_code:
            journey.code = journey_code

        destination_ref = monitored_vehicle_journey.get('DestinationRef')

        if not journey.destination:
            # use stop locality
            if destination_ref:
                journey.destination = self.get_destination_name(destination_ref)
            # use destination name string (often not very descriptive)
            if not journey.destination:
                destination = monitored_vehicle_journey.get('DestinationName')
                if destination:
                    if route_name:
                        destination = destination.removeprefix(f'{route_name} ')  # TGTC
                    journey.destination = destination

            # fall back to direction
            if not journey.destination:
                journey.direction = monitored_vehicle_journey.get('DirectionRef', '')[:8]

        if not journey.service_id and route_name:
            operator_ref = monitored_vehicle_journey["OperatorRef"]
            operators = self.get_operator(operator_ref)
            journey.service = self.get_service(operators, item, route_name, vehicle.operator_id)

            if not operators and journey.service and operator_ref != 'TFLO' and journey.service.operator.all():
                operator = journey.service.operator.all()[0]
                try:
                    OperatorCode.objects.create(source=self.source, operator=operator, code=operator_ref)
                except IntegrityError:
                    pass
                vehicle.operator = operator
                vehicle.save(update_fields=['operator'])

            # match trip (timetable) to journey:
            if journey.service and (origin_aimed_departure_time or journey_ref and '_' not in journey_ref):

                journey_date = None

                if journey_ref and len(journey_ref) > 11 and journey_ref[10] == ':':

                    # code is like "2021-12-13:203" so separate the date from the other bit
                    try:
                        journey_date = date.fromisoformat(journey_ref[:10])
                        journey_ref = journey_ref[11:]
                        journey.code = journey_ref
                    except ValueError:
                        pass

                journey.trip = journey.get_trip(
                    datetime=datetime,
                    date=journey_date,
                    destination_ref=destination_ref,
                    departure_time=origin_aimed_departure_time,
                    journey_ref=journey_ref
                )

                if not journey.trip:
                    try:
                        # if driver change caused bogus journey code change (Ticketer), continue previous journey
                        if latest_journey and latest_journey.trip and latest_journey.route_name == journey.route_name:
                            if latest_journey.destination == journey.destination:
                                start = localtime(datetime)
                                start = timedelta(hours=start.hour, minutes=start.minute)
                                if latest_journey.trip.start < start < latest_journey.trip.end:
                                    journey.trip = latest_journey.trip
                    except Trip.DoesNotExist:
                        pass

                elif journey.trip.destination_id:
                    if not journey.destination or destination_ref != journey.trip.destination_id:
                        journey.destination = self.get_destination_name(journey.trip.destination_id)

                if journey.trip and journey.trip.garage_id != vehicle.garage_id:
                    vehicle.garage_id = journey.trip.garage_id
                    vehicle.save(update_fields=['garage'])

        return journey

    @staticmethod
    def create_vehicle_location(item):
        monitored_vehicle_journey = item['MonitoredVehicleJourney']
        location = monitored_vehicle_journey['VehicleLocation']
        latlong = GEOSGeometry(f"POINT({location['Longitude']} {location['Latitude']})")
        bearing = monitored_vehicle_journey.get('Bearing')
        if bearing:
            # Assume '0' means None. There's only a 1/360 chance the bus is actually facing exactly north
            bearing = float(bearing) or None
        location = VehicleLocation(
            latlong=latlong,
            heading=bearing,
            occupancy=monitored_vehicle_journey.get('Occupancy', '')
        )
        try:
            extensions = item['Extensions']['VehicleJourney']
            location.occupancy_thresholds = extensions['OccupancyThresholds']
            location.seated_occupancy = int(extensions['SeatedOccupancy'])
            location.seated_capacity = int(extensions['SeatedCapacity'])
            location.wheelchair_occupancy = int(extensions['WheelchairOccupancy'])
            location.wheelchair_capacity = int(extensions['WheelchairCapacity'])
        except (KeyError, TypeError):
            pass
        return location

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
            return

        if 'datafeed' in self.source.url:
            # api response
            data = self.items_from_response(response.content)
        else:
            # bulk download
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                assert archive.namelist() == ['siri.xml']
                with archive.open('siri.xml') as open_file:
                    data = self.items_from_response(open_file)

        self.when = data['Siri']['ServiceDelivery']['ResponseTimestamp']
        self.source.datetime = parse_datetime(self.when)

        return data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery'].get('VehicleActivity')
