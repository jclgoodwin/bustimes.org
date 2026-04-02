import requests
import ciso8601

from django.contrib.gis.geos import GEOSGeometry
from django.utils import timezone
from django.db.models import Q

from busstops.models import Service

from ...models import VehicleJourney, VehicleLocation, Operator
from ..import_live_vehicles import ImportLiveVehiclesCommand
from .import_bod_avl import get_line_name_query


def parse_datetime(string):
    datetime = ciso8601.parse_datetime(string)
    return timezone.make_aware(datetime)


class Command(ImportLiveVehiclesCommand):
    wait = 92

    def get_items(self):
        self.session = requests.Session()
        return super().get_items()

    @staticmethod
    def add_arguments(parser):
        parser.add_argument("source_name", type=str)
        ImportLiveVehiclesCommand.add_arguments(parser)

    def handle(self, source_name, **options):
        self.source_name = self.vehicle_code_scheme = source_name
        super().handle(**options)

    @staticmethod
    def get_vehicle_identity(item):
        return f"{item['OperatorRef']}:{item['VehicleRef']}"

    @staticmethod
    def get_journey_identity(item):
        return (
            item["JourneyCode"],
            item["PublishedLineName"],
            item["DestinationRef"],
        )

    @staticmethod
    def get_item_identity(item):
        return item["RecordedAtTime"]

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item["RecordedAtTime"])

    def get_operators(self, item):
        code = item["OperatorRef"]
        return Operator.objects.filter(
            Q(noc=code) | Q(operatorcode__code=code, operatorcode__source=self.source)
        )

    def get_vehicle(self, item):
        code = item["VehicleRef"]
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        operators = self.get_operators(item)

        defaults = {
            "fleet_number": fleet_number,
            "source": self.source,
            "operator": operators[0],
            "code": code,
        }

        try:
            return self.vehicles.get_or_create(
                defaults, code__iexact=code, operator__in=operators
            )
        except self.vehicles.model.MultipleObjectsReturned:
            return (
                self.vehicles.filter(code__iexact=code, operator__in=operators).first(),
                False,
            )

    def get_service(self, item):
        line_name = item["PublishedLineName"]
        if not line_name:
            return
        services = Service.objects.filter(
            get_line_name_query(line_name),
            current=True,
            operator__in=self.get_operators(item),
        )
        try:
            try:
                return services.get()
            except Service.MultipleObjectsReturned:
                return (
                    services.filter(stops__locality__stoppoint=item["DestinationRef"])
                    .distinct()
                    .get()
                )
        except (Service.DoesNotExist, Service.MultipleObjectsReturned) as e:
            print(
                e,
                item["OperatorRef"],
                item["PublishedLineName"],
                item["DestinationRef"],
            )

    def get_journey(self, item, vehicle):
        code = item["JourneyCode"]
        datetime = item["DepartureTime"]
        if datetime:
            datetime = parse_datetime(datetime)
        else:
            datetime = None

        latest_journey = vehicle.latest_journey
        if (
            latest_journey
            and latest_journey.code == code
            and latest_journey.datetime == datetime
        ):
            return latest_journey

        if datetime and (
            journey := vehicle.vehiclejourney_set.filter(
                date=timezone.localdate(datetime), datetime=datetime
            ).first()
        ):
            return journey

        journey = VehicleJourney(
            datetime=datetime,
            code=code or "",
            route_name=item["PublishedLineName"] or "",
            service=self.get_service(item),
            destination=item["DestinationStopLocality"]
            or item["DestinationStopName"]
            or "",
            direction=item["DirectionRef"],
        )

        if journey.service_id and not journey.id and datetime:
            journey.trip = journey.get_trip(
                departure_time=datetime, destination_ref=item["DestinationRef"]
            )
            if journey.trip and not journey.destination:
                journey.destination = journey.trip.headsign or ""

        return journey

    def create_vehicle_location(self, item):
        bearing = item["Bearing"]
        if bearing == "-1" or bearing == "0":
            bearing = None
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['Longitude']} {item['Latitude']})"),
            heading=bearing,
        )
