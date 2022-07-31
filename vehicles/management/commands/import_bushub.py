import requests
from django.contrib.gis.geos import Point
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney
from .import_nx import parse_datetime
from ..import_live_vehicles import ImportLiveVehiclesCommand


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
        self.source_name = source_name
        super().handle(**options)

    @staticmethod
    def get_datetime(item):
        return parse_datetime(item["RecordedAtTime"])

    def get_vehicle(self, item):
        code = item["VehicleRef"]
        if code.isdigit():
            fleet_number = code
        else:
            fleet_number = None

        if self.source.settings and "OperatorRef" in self.source.settings:
            item["OperatorRef"] = self.source.settings["OperatorRef"]
        else:
            item["OperatorRef"] = [item["OperatorRef"]]

        operators = item["OperatorRef"]
        defaults = {
            "fleet_number": fleet_number,
            "source": self.source,
            "operator_id": operators[0],
        }

        try:
            return self.vehicles.get_or_create(
                defaults, code=code, operator__in=operators
            )
        except self.vehicles.model.MultipleObjectsReturned:
            return (
                self.vehicles.filter(code=code, operator__in=operators).first(),
                False,
            )

    @classmethod
    def get_service(cls, item):
        line_name = item["PublishedLineName"]
        if not line_name:
            return
        services = Service.objects.filter(current=True, line_name__iexact=line_name)
        services = services.filter(operator__in=item["OperatorRef"])
        try:
            return services.get()
        except Service.DoesNotExist as e:
            if line_name[-1].isalpha():
                item["PublishedLineName"] = line_name[:-1]
            elif line_name[0].isalpha():
                item["PublishedLineName"] = line_name[1:]
            else:
                print(e, item["OperatorRef"], line_name)
                return
            return cls.get_service(item)
        except Service.MultipleObjectsReturned:
            try:
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

        if datetime:
            try:
                return vehicle.vehiclejourney_set.select_related("service").get(
                    datetime=datetime
                )
            except VehicleJourney.DoesNotExist:
                pass

        journey = VehicleJourney(
            datetime=datetime,
            code=code,
            route_name=item["PublishedLineName"],
            service=self.get_service(item),
            destination=item["DestinationStopLocality"],
        )

        if journey.service_id and not journey.id:
            journey.trip = journey.get_trip(
                departure_time=datetime, destination_ref=item["DestinationRef"]
            )

        return journey

    def create_vehicle_location(self, item):
        bearing = item["Bearing"]
        if bearing == "-1":
            bearing = None
        return VehicleLocation(
            latlong=Point(float(item["Longitude"]), float(item["Latitude"])),
            heading=bearing,
        )
