import functools
import io
import json
import zipfile
from datetime import date, timedelta

import xmltodict
from ciso8601 import parse_datetime
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.dateparse import parse_duration

from busstops.models import (
    Locality,
    Operator,
    OperatorCode,
    Service,
    ServiceCode,
    StopPoint,
)
from bustimes.models import Route, Trip

from ...models import Vehicle, VehicleCode, VehicleJourney, VehicleLocation
from ...utils import redis_client
from ..import_live_vehicles import ImportLiveVehiclesCommand, logger


def get_destination_ref(destination_ref):
    destination_ref = destination_ref.removeprefix("NT")  # Nottingham City Transport

    if (
        " " in destination_ref
        or len(destination_ref) < 4
        or not destination_ref[:4].isdigit()
        or destination_ref[:3] == "000"
        or destination_ref[:3] == "999"
        or destination_ref[:3] == "980"
    ):
        # destination ref is a fake ATCO code, or maybe a postcode or other placeholder
        return

    return destination_ref


@functools.cache
def get_destination_name(destination_ref):
    try:
        return Locality.objects.get(stoppoint=destination_ref).name
    except Locality.DoesNotExist:
        if (
            destination_ref.isdigit()
            and destination_ref[0:1] != "0"
            and destination_ref[2:3] == "0"
        ):
            return get_destination_name(f"0{destination_ref}")
    return ""


def get_line_name_query(line_ref):
    line_name = line_ref.replace("_", " ").strip()
    return (
        Exists(
            ServiceCode.objects.filter(
                service=OuterRef("id"), scheme__endswith="SIRI", code=line_ref
            )
        )
        | Q(line_name__iexact=line_name)
        | Exists(
            Route.objects.filter(service=OuterRef("id"), line_name__iexact=line_name)
        )
    )


class Command(ImportLiveVehiclesCommand):
    source_name = "Bus Open Data"
    services = (
        Service.objects.using(settings.READ_DATABASE)
        .filter(current=True)
        .defer("geometry", "search_vector")
    )
    fallback_mode = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hist = {}
        self.identifiers = {}
        self.journeys_ids = {}
        self.journeys_ids_ids = {}

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item["RecordedAtTime"])

    @functools.cache
    def get_operator(self, operator_ref):
        # all operators with a matching OperatorCode,
        # or (if no such OperatorCode) the one with a matching id
        operator_codes = self.source.operatorcode_set.filter(code=operator_ref)
        return Operator.objects.filter(
            Exists(operator_codes.filter(operator=OuterRef("pk")))
            | Q(noc=operator_ref) & ~Exists(operator_codes)
        )

    def get_vehicle(self, item):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]
        operator_ref = monitored_vehicle_journey["OperatorRef"]
        vehicle_ref = monitored_vehicle_journey["VehicleRef"] or ""

        vehicle_ref = vehicle_ref.removeprefix(f"{operator_ref}-")
        vehicle_ref = vehicle_ref.removeprefix("nibs_").removeprefix("stephensons_")

        try:
            vehicle_unique_id = item["Extensions"]["VehicleJourney"]["VehicleUniqueId"]
        except (KeyError, TypeError):
            vehicle_unique_id = None

        if not vehicle_ref and vehicle_unique_id:
            vehicle_ref = vehicle_unique_id

        if (
            not vehicle_ref.isdigit()
            and vehicle_ref.isupper()
            and len(vehicle_ref) > 6
            and not vehicle_ref.startswith("BUS")
        ):
            # assume vehicle ref is globally unique (cos it looks like a vehicle reg?)
            try:
                return self.vehicles.get(code__iexact=vehicle_ref), False
            except (Vehicle.DoesNotExist, Vehicle.MultipleObjectsReturned):
                pass

        # ffs
        if operator_ref == "MARS" and vehicle_unique_id:
            vehicle_ref = vehicle_unique_id

        defaults = {"code": vehicle_ref, "source": self.source}

        operators = self.get_operator(operator_ref)

        if operator_ref == "TFLO":
            defaults["livery_id"] = 262
            if vehicle_ref.startswith("TMP"):
                defaults["notes"] = "Spare ticket machine"
                defaults["locked"] = True
            vehicles = self.vehicles.filter(
                Q(operator__in=operators) | Q(operator=None)
            )
        elif not operators:
            vehicles = self.vehicles.filter(operator=None)
        elif len(operators) == 1:
            operator = operators[0]

            defaults["operator"] = operator
            if operator.parent:
                condition = Q(operator__parent=operator.parent)
                vehicles = self.vehicles.filter(condition)
            else:
                vehicles = self.vehicles.filter(operator=operator)
        else:
            defaults["operator"] = operators[0]
            vehicles = self.vehicles.filter(operator__in=operators)

        condition = Q(code__iexact=vehicle_ref)
        if vehicle_ref.isdigit():
            defaults["fleet_number"] = vehicle_ref
            if operators:
                condition |= Q(code__endswith=f"-{vehicle_ref}") | Q(
                    code__startswith=f"{vehicle_ref}_"
                )
        elif "_-_" in vehicle_ref:
            fleet_number, reg = vehicle_ref.split("_-_", 2)
            if fleet_number.isdigit():
                defaults["fleet_number"] = fleet_number
                reg = reg.replace("_", "")
                defaults["reg"] = reg
        if "fleet_number" not in defaults and vehicle_unique_id:
            # VehicleUniqueId
            if len(vehicle_unique_id) < len(vehicle_ref):
                defaults["fleet_code"] = vehicle_unique_id
                if vehicle_unique_id.isdigit():
                    defaults["fleet_number"] = vehicle_unique_id

        vehicles = vehicles.filter(condition)

        try:
            vehicle, created = vehicles.get_or_create(defaults)
        except (Vehicle.MultipleObjectsReturned, IntegrityError) as e:
            print(e, operator_ref, vehicle_ref)
            vehicle = vehicles.first()
            created = False
        else:
            if "fleet_code" in defaults and not vehicle.fleet_code:
                vehicle.fleet_code = defaults["fleet_code"]
                if "fleet_number" in defaults:
                    vehicle.fleet_number = defaults["fleet_number"]
                vehicle.save(update_fields=["fleet_code", "fleet_number"])

        return vehicle, created

    def get_service(self, operators, item, line_ref, vehicle_operator_id):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]

        destination_ref = monitored_vehicle_journey.get("DestinationRef")

        cache_key = f"{vehicle_operator_id}:{line_ref}:{destination_ref}".replace(
            " ", ""
        )
        service = cache.get(cache_key)
        if service is not None:
            return service or None

        if destination_ref:
            destination_ref = get_destination_ref(destination_ref)

        # filter by LineRef or (if present and different) TicketMachineServiceCode
        line_name_query = get_line_name_query(line_ref)
        try:
            ticket_machine_service_code = item["Extensions"]["VehicleJourney"][
                "Operational"
            ]["TicketMachine"]["TicketMachineServiceCode"]
        except (KeyError, TypeError):
            pass
        else:
            if ticket_machine_service_code.lower() != line_ref.lower():
                line_name_query |= get_line_name_query(ticket_machine_service_code)

        services = self.services.filter(line_name_query).defer("geometry")

        if item["MonitoredVehicleJourney"]["OperatorRef"] == "TFLO":
            return services.filter(source__name="L").first()

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
            if vehicle_operator_id != operator.noc:
                condition |= Q(noc=vehicle_operator_id)

            services = services.filter(
                Exists(Operator.objects.filter(condition, service=OuterRef("pk")))
            )
            # we don't just use 'operator__parent=' because a service can have multiple operators

            # we will use the DestinationRef later to find out exactly which operator it is,
            # because the OperatorRef field is unreliable,
            # e.g. sometimes has the wrong up First Yorkshire operator code

        elif operators:
            if len(operators) == 1:
                operator = operators[0]
                condition = Q(operator=operator)
                if vehicle_operator_id != operator.noc:
                    condition |= Q(operator=vehicle_operator_id)
                services = services.filter(condition)
            else:
                services = services.filter(
                    Exists(
                        Service.operator.through.objects.filter(
                            operator__in=operators, service=OuterRef("id")
                        )
                    )
                )

            if len(operators) == 1 or not destination_ref:
                try:
                    return services.get()
                except Service.DoesNotExist:
                    cache.set(
                        cache_key, False, 3600
                    )  # cache 'service not found' for an hour
                    return
                except Service.MultipleObjectsReturned:
                    pass

        if destination_ref:
            # cope with a missing leading zero
            atco_code__startswith = Q(atco_code__startswith=destination_ref[:3])
            if (
                destination_ref.isdigit()
                and destination_ref[0] != "0"
                and destination_ref[3] == "0"
            ):
                atco_code__startswith |= Q(
                    atco_code__startswith=f"0{destination_ref}[:3]"
                )

            stops = StopPoint.objects.filter(
                atco_code__startswith, service=OuterRef("pk")
            )
            services = services.filter(Exists(stops))
            try:
                return services.get()
            except Service.DoesNotExist:
                cache.set(cache_key, False, 3600)
                return
            except Service.MultipleObjectsReturned:
                condition = Exists(
                    StopPoint.objects.filter(
                        service=OuterRef("pk"), atco_code=destination_ref
                    )
                )
                origin_ref = monitored_vehicle_journey.get("OriginRef")
                if origin_ref:
                    condition &= Exists(
                        StopPoint.objects.filter(
                            service=OuterRef("pk"), atco_code=origin_ref
                        )
                    )
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
            trips = Trip.objects.filter(
                **{f"calendar__{when:%a}".lower(): True}, route__service=OuterRef("pk")
            )
            return services.get(Exists(trips))
        except (Service.DoesNotExist, Service.MultipleObjectsReturned):
            pass

    def get_journey(self, item, vehicle):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]

        journey_ref = monitored_vehicle_journey.get("VehicleJourneyRef")
        journey_date = None

        if not journey_ref:
            try:
                framed = monitored_vehicle_journey["FramedVehicleJourneyRef"]
                journey_ref = framed["DatedVehicleJourneyRef"]
                journey_date = date.fromisoformat(framed["DataFrameRef"])
            except KeyError:
                pass

        if journey_ref == "UNKNOWN":
            journey_ref = None

        try:
            ticket_machine = item["Extensions"]["VehicleJourney"]["Operational"][
                "TicketMachine"
            ]
            journey_code = ticket_machine["JourneyCode"]
        except (KeyError, TypeError):
            journey_code = journey_ref
            ticket_machine = None
        else:
            if journey_code == "0000":
                journey_code = journey_ref
            elif not journey_ref:
                journey_ref = journey_code  # what we will use for finding matching trip

        route_name = monitored_vehicle_journey.get(
            "PublishedLineName"
        ) or monitored_vehicle_journey.get("LineRef", "")
        if not route_name and ticket_machine:
            route_name = ticket_machine.get("TicketMachineServiceCode", "")

        origin_aimed_departure_time = monitored_vehicle_journey.get(
            "OriginAimedDepartureTime"
        )
        if origin_aimed_departure_time:
            origin_aimed_departure_time = parse_datetime(origin_aimed_departure_time)

            # detect and correct Ticketer timezone bug during British Summer Time
            if (
                journey_code
                and len(journey_code) == 4
                and journey_code.isdigit()
                and int(journey_code) < 2400
            ):
                hours = int(journey_code[:-2])
                minutes = int(journey_code[-2:])
                if (
                    minutes == origin_aimed_departure_time.minute
                    and hours == origin_aimed_departure_time.hour
                ):
                    origin_aimed_departure_time = timezone.localtime(
                        origin_aimed_departure_time
                    )
                    HOUR = timedelta(hours=1)
                    if (origin_aimed_departure_time - HOUR).hour == hours:
                        origin_aimed_departure_time -= HOUR

        journey = None

        journeys = vehicle.vehiclejourney_set

        datetime = self.get_datetime(item)

        operator_ref = monitored_vehicle_journey["OperatorRef"]

        # treat the weird Nottingham City Transport data specially
        if (
            operator_ref == "NCTR"
            and origin_aimed_departure_time is None
            and journey_ref[:2] == "NT"
            and journey_ref.count("-") == 9
        ):
            origin_aimed_departure_time = timezone.make_aware(
                parse_datetime(journey_ref[-30:-11])
            )
            journey_date = date.fromisoformat(journey_ref[-10:])

        if origin_aimed_departure_time:
            difference = origin_aimed_departure_time - datetime
            if difference > timedelta(
                hours=20
            ):  # more than 20 hours in the future? subtract a day
                origin_aimed_departure_time -= timedelta(days=1)
            elif operator_ref == "TFLO":
                if origin_aimed_departure_time.utcoffset():
                    logger.warning(
                        "TFL vehicle with non-UTC time, so bug may have been fixed"
                    )
                elif difference > timedelta(minutes=50):
                    origin_aimed_departure_time -= timedelta(hours=1)

        latest_journey = vehicle.latest_journey
        if latest_journey:
            if origin_aimed_departure_time:
                if latest_journey.datetime == origin_aimed_departure_time:
                    journey = latest_journey
                else:
                    journey = journeys.filter(
                        datetime=origin_aimed_departure_time
                    ).first()
            elif journey_ref:
                datetime = self.get_datetime(item)
                THREE_HOURS = timedelta(hours=3)
                if (
                    route_name == latest_journey.route_name
                    and journey_ref == latest_journey.code
                ):
                    if datetime - latest_journey.datetime < THREE_HOURS:
                        journey = latest_journey
                else:
                    three_hours_ago = datetime - THREE_HOURS
                    journey = journeys.filter(
                        route_name=route_name,
                        code=journey_ref,
                        datetime__gt=three_hours_ago,
                    ).last()

        if not journey:
            journey = VehicleJourney(
                route_name=route_name,
                vehicle=vehicle,
                source=self.source,
                datetime=origin_aimed_departure_time,
            )

        if journey_ref:
            journey.code = journey_ref

        destination_ref = monitored_vehicle_journey.get("DestinationRef")
        if destination_ref:
            destination_ref = get_destination_ref(destination_ref)

        if not journey.destination:
            # use stop locality
            if destination_ref:
                journey.destination = get_destination_name(destination_ref)
            # use destination name string (often not very descriptive)
            if not journey.destination:
                destination = monitored_vehicle_journey.get("DestinationName")
                if destination:
                    if route_name:
                        destination = destination.removeprefix(f"{route_name} ")  # TGTC
                    journey.destination = destination

            # fall back to direction
            if not journey.destination:
                journey.direction = monitored_vehicle_journey.get("DirectionRef", "")[
                    :8
                ]

        if not journey.service_id and route_name:
            operators = self.get_operator(operator_ref)
            journey.service = self.get_service(
                operators, item, route_name, vehicle.operator_id
            )

            if not operators and journey.service and journey.service.operator.all():
                # create new OperatorCode
                operator = journey.service.operator.all()[0]
                try:
                    OperatorCode.objects.create(
                        source=self.source, operator=operator, code=operator_ref
                    )
                except IntegrityError:
                    pass

                if not vehicle.operator_id:
                    vehicle.operator = operator
                    try:
                        vehicle.save(update_fields=["operator"])
                    except IntegrityError:
                        pass

            # match trip (timetable) to journey:
            if journey.service and (origin_aimed_departure_time or journey_ref):
                block_ref = monitored_vehicle_journey.get("BlockRef")

                arrival_time = monitored_vehicle_journey.get(
                    "DestinationAimedArrivalTime"
                )
                if arrival_time:
                    arrival_time = parse_datetime(arrival_time)

                journey.trip = journey.get_trip(
                    datetime=datetime,
                    date=journey_date,
                    operator_ref=operator_ref,
                    origin_ref=monitored_vehicle_journey.get("OriginRef"),
                    destination_ref=destination_ref,
                    departure_time=origin_aimed_departure_time,
                    arrival_time=arrival_time,
                    journey_code=journey_code,
                    block_ref=block_ref,
                )

                if trip := journey.trip:
                    if (
                        not (destination_ref and journey.destination)
                        and trip.destination_id
                    ):
                        journey.destination = get_destination_name(trip.destination_id)

                    update_fields = []

                    if trip.garage_id != vehicle.garage_id:
                        vehicle.garage_id = trip.garage_id
                        update_fields.append("garage")

                    if not vehicle.operator_id and trip.operator_id:
                        vehicle.operator_id = trip.operator_id
                        update_fields.append("operator")

                    update_fields.append("operator")
                    if update_fields:
                        vehicle.save(update_fields=update_fields)

        return journey

    @staticmethod
    def create_vehicle_location(item):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]
        location = monitored_vehicle_journey["VehicleLocation"]
        latlong = GEOSGeometry(f"POINT({location['Longitude']} {location['Latitude']})")
        bearing = monitored_vehicle_journey.get("Bearing")
        if bearing:
            # Assume '0' means None. There's only a 1/360 chance the bus is actually facing exactly north
            bearing = float(bearing) or None
        delay = monitored_vehicle_journey.get("Delay")
        if delay:
            delay = parse_duration(delay)
        location = VehicleLocation(
            latlong=latlong,
            heading=bearing,
            occupancy=monitored_vehicle_journey.get("Occupancy"),
            block=monitored_vehicle_journey.get("BlockRef"),
        )
        if monitored_vehicle_journey["OperatorRef"] == "TFLO":
            location.tfl_code = monitored_vehicle_journey["VehicleRef"]
        extensions = item.get("Extensions")
        if extensions:
            extensions = extensions.get("VehicleJourney") or extensions.get(
                "VehicleJourneyExtensions"
            )
        if extensions:
            location.occupancy_thresholds = extensions.get("OccupancyThresholds")
            if "SeatedOccupancy" in extensions:
                location.seated_occupancy = int(extensions["SeatedOccupancy"])
            if "SeatedCapacity" in extensions:
                location.seated_capacity = int(extensions["SeatedCapacity"])
            if "WheelchairOccupancy" in extensions:
                location.wheelchair_occupancy = int(extensions["WheelchairOccupancy"])
            if "WheelchairCapacity" in extensions:
                location.wheelchair_capacity = int(extensions["WheelchairCapacity"])
        return location

    def get_items(self):
        url = self.source.url
        if self.fallback_mode:
            url = self.source.settings.get("fallback_url") or url

        response = self.session.get(url, timeout=30)

        if not response.ok:
            return []

        if response.headers["content-type"] == "application/zip":
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                namelist = archive.namelist()
                assert len(namelist) == 1
                with archive.open(namelist[0]) as open_file:
                    data = open_file.read()
        else:
            data = response.content

        data = xmltodict.parse(
            data,
            dict_constructor=dict,  # override OrderedDict, cos dict is ordered in modern versions of Python
            force_list=["VehicleActivity"],
        )

        previous_time = self.source.datetime

        self.source.datetime = parse_datetime(
            data["Siri"]["ServiceDelivery"]["ResponseTimestamp"]
        )

        if (
            self.source.datetime
            and previous_time
            and self.source.datetime < previous_time
        ):
            return  # don't return old data

        return data["Siri"]["ServiceDelivery"]["VehicleMonitoringDelivery"].get(
            "VehicleActivity"
        )

    @staticmethod
    def get_vehicle_identity(item):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]
        operator_ref = monitored_vehicle_journey["OperatorRef"]
        vehicle_ref = monitored_vehicle_journey["VehicleRef"]

        try:
            vehicle_unique_id = item["Extensions"]["VehicleJourney"]["VehicleUniqueId"]
        except (KeyError, TypeError):
            pass
        else:
            vehicle_ref = f"{vehicle_ref}:{vehicle_unique_id}"

        return f"{operator_ref}:{vehicle_ref}"

    @staticmethod
    def get_journey_identity(item):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]
        line_ref = monitored_vehicle_journey.get("LineRef")
        line_name = monitored_vehicle_journey.get("PublishedLineName")

        try:
            journey_ref = monitored_vehicle_journey["FramedVehicleJourneyRef"]
        except (KeyError, ValueError):
            journey_ref = monitored_vehicle_journey.get("VehicleJourneyRef")

        departure = monitored_vehicle_journey.get("OriginAimedDepartureTime")
        direction = monitored_vehicle_journey.get("DirectionRef")
        destination = monitored_vehicle_journey.get("DestinationName")

        return f"{line_ref} {line_name} {journey_ref} {departure} {direction} {destination}"

    def handle_items(self, items, identities):
        vehicle_codes = VehicleCode.objects.filter(
            code__in=identities, scheme="BODS"
        ).select_related("vehicle__latest_journey__trip")

        vehicles_by_identity = {code.code: code.vehicle for code in vehicle_codes}

        vehicle_locations = redis_client.mget(
            [f"vehicle{vc.vehicle_id}" for vc in vehicle_codes]
        )
        vehicle_locations = {
            vehicle_codes[i].vehicle_id: json.loads(item)
            for i, item in enumerate(vehicle_locations)
            if item
        }

        for i, item in enumerate(items):
            vehicle_identity = identities[i]

            journey_identity = self.journeys_ids[vehicle_identity]

            if vehicle_identity in vehicles_by_identity:
                vehicle = vehicles_by_identity[vehicle_identity]
            else:
                vehicle, created = self.get_vehicle(item)
                # print(vehicle_identity, vehicle, created)
                if vehicle:
                    VehicleCode.objects.create(
                        code=vehicle_identity, scheme="BODS", vehicle=vehicle
                    )

            keep_journey = False
            if vehicle_identity in self.journeys_ids_ids:
                journey_identity_id = self.journeys_ids_ids[vehicle_identity]
                if journey_identity_id == (journey_identity, vehicle.latest_journey_id):
                    keep_journey = True  # can dumbly keep same latest_journey

            result = self.handle_item(
                item,
                self.source.datetime,
                vehicle=vehicle,
                latest=vehicle_locations.get(vehicle.id, False),
                keep_journey=keep_journey,
            )

            if result:
                location, vehicle = result

                self.journeys_ids_ids[vehicle_identity] = (
                    journey_identity,
                    vehicle.latest_journey_id,
                )

            self.identifiers[vehicle_identity] = item["RecordedAtTime"]

            if i and not i % 500:
                self.save()

        self.save()

    def get_changed_items(self, items=None):
        changed_items = []
        changed_journey_items = []
        changed_item_identities = []
        changed_journey_identities = []
        # (changed items and changed journey items are separate
        # so we can do the quick ones first)

        total_items = 0

        for i, item in enumerate(items or self.get_items() or ()):
            vehicle_identity = self.get_vehicle_identity(item)

            journey_identity = self.get_journey_identity(item)

            total_items += 1

            if self.identifiers.get(vehicle_identity) == item["RecordedAtTime"]:
                if journey_identity == self.journeys_ids[vehicle_identity]:
                    continue
                print(self.journeys_ids[vehicle_identity], item)
            if (
                vehicle_identity not in self.journeys_ids
                or journey_identity != self.journeys_ids[vehicle_identity]
            ):
                changed_journey_items.append(item)
                changed_journey_identities.append(vehicle_identity)
            else:
                changed_items.append(item)
                changed_item_identities.append(vehicle_identity)

            self.journeys_ids[vehicle_identity] = journey_identity

        return (
            changed_items,
            changed_journey_items,
            changed_item_identities,
            changed_journey_identities,
            total_items,
        )

    def update(self):
        now = timezone.now()

        (
            changed_items,
            changed_journey_items,
            changed_item_identities,
            changed_journey_identities,
            total_items,
        ) = self.get_changed_items()

        age = int((now - self.source.datetime).total_seconds())
        self.hist[now.second % 10] = age
        print(self.hist)
        print(
            f"{now.second=} {age=}  {total_items=}  {len(changed_items)=}  {len(changed_journey_items)=}"
        )

        self.handle_items(changed_items, changed_item_identities)
        self.handle_items(changed_journey_items, changed_journey_identities)

        # stats for last 10 updates:
        bod_status = cache.get("bod_avl_status", [])
        bod_status.append(
            (
                now,
                self.source.datetime,
                total_items,
                len(changed_items) + len(changed_journey_items),
            )
        )
        bod_status = bod_status[-50:]
        cache.set("bod_avl_status", bod_status, None)

        time_taken = (timezone.now() - now).total_seconds()
        print(f"{time_taken=}")

        if self.fallback_mode:
            self.fallback_mode = False
            return 30  # wait
        elif age > 150 and not changed_items:
            self.fallback_mode = True

        # bods updates "every 10 seconds",
        # it's usually worth waiting 0-9 seconds
        # before the next fetch
        # for maximum freshness:

        witching_hour = min(self.hist, key=self.hist.get)
        worst_hour = max(self.hist, key=self.hist.get)
        now = timezone.now().second % 10
        wait = witching_hour - now
        if wait < 0:
            wait += 10
        diff = worst_hour - witching_hour
        print(f"{witching_hour=} {worst_hour=} {diff=} {now=} {wait=}\n")
        if diff % 10 == 9:
            return wait

        return max(11 - time_taken, 0)
