from datetime import datetime, timedelta

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Q

from busstops.models import Operator, Service
from bustimes.models import Route, Trip

from ...models import Vehicle, VehicleJourney, VehicleLocation
from ..import_live_vehicles import ImportLiveVehiclesCommand


def parse_date(date):
    return datetime.strptime(date, "%d.%m.%Y").date()


class Command(ImportLiveVehiclesCommand):
    source_name = vehicle_code_scheme = "Translink"
    url = "https://vpos.translinkniplanner.co.uk/velocmap/vmi/VMI"

    def do_source(self):
        self.operators = Operator.objects.filter(
            noc__in=("FY", "GLE", "GDR", "MET", "ULB", "UTS")
        ).in_bulk()

        return super().do_source()

    @staticmethod
    def get_datetime(item):
        return datetime.fromisoformat(item["Timestamp"])

    @staticmethod
    def get_vehicle_identity(item):
        return item["VehicleIdentifier"]

    @staticmethod
    def get_journey_identity(item):
        return (
            item["DayOfOperation"],
            item["JourneyIdentifier"],
            item.get("DirectionText"),
            item.get("LineText"),
        )

    @staticmethod
    def get_item_identity(item):
        return item["Timestamp"]

    def get_vehicle(self, item) -> tuple[Vehicle, bool]:
        vehicle_code = item["VehicleIdentifier"]

        operator_id, fleet_code = vehicle_code.split("-", 1)

        if operator_id == "TM":
            operator_id = "MET"

        vehicle = self.vehicles.filter(
            fleet_code__iexact=fleet_code,
            operator=operator_id,
        ).first()
        if not vehicle:
            vehicle = self.vehicles.filter(
                fleet_code__iexact=fleet_code,
                operator__in=self.operators,
            ).first()

        if vehicle:
            return vehicle, False

        return Vehicle.objects.get_or_create(
            {"fleet_code": fleet_code, "source": self.source},
            operator_id=operator_id,
            code=vehicle_code,
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(
            code=item["JourneyIdentifier"],
            destination=item.get("DirectionText", ""),
            route_name=item.get("LineText", ""),
        )

        if "#" in journey.code:
            journey.code = journey.code.split("#", 1)[0]

        if (latest_journey := vehicle.latest_journey) and (
            journey.code == latest_journey.code
            and journey.route_name == latest_journey.route_name
        ):
            return latest_journey

        date = parse_date(item["DayOfOperation"])
        if trip := self.get_trip(item, journey, date):
            journey.trip = trip
            journey.service = trip.route.service
            journey.date = date
            return journey

        journey.service = Service.objects.filter(
            Q(route__line_name__iexact=journey.route_name)
            | Q(route__line_name__iexact=f"G{journey.route_name}"),
            operator=vehicle.operator_id,
            current=True,
        ).first()
        if not journey.service:
            journey.service = Service.objects.filter(
                operator__in=self.operators,
                route__line_name__iexact=journey.route_name,
                current=True,
            ).first()

        if journey.service:
            journey.trip = journey.get_trip(
                date=date,
                journey_code=journey.code,
                next_stop=item.get("CurrentStop"),
                approximate_datetime=True,
                datetime=self.get_datetime(item),
            )

        return journey

    def get_trip(self, item, journey, date):
        routes = Route.objects.filter(
            Q(line_name__iexact=journey.route_name)
            | Q(line_name__iexact=f"G{journey.route_name}"),
            service__current=True,
            service__operator__in=self.operators,
        ).active_on(date)
        trips = list(
            Trip.objects.filter(route__in=routes, ticket_machine_code=journey.code)
            .active_on(date)
            .select_related("route__service")
        )

        # the same journey identifier might be used for both directions,
        # or for a same-numbered route elsewhere
        # - prefer a trip calling at CurrentStop then NextStop
        if len(trips) > 1 and (current_stop := item.get("CurrentStop")):
            next_stop = item.get("NextStop")

            def score(trip):
                stops = list(
                    trip.stoptime_set.order_by("id").values_list("stop_id", flat=True)
                )
                if current_stop not in stops:
                    return 0
                if next_stop in stops[stops.index(current_stop) + 1 :]:
                    return 2
                return 1

            trips.sort(key=score, reverse=True)

        if trips:
            return trips[0]

    def create_vehicle_location(self, item):
        delay = item.get("Delay")
        if delay is not None:
            delay = timedelta(seconds=delay)
        return VehicleLocation(
            latlong=GEOSGeometry(f"POINT({item['X']} {item['Y']})"),
            delay=delay,
            prev_stop=item.get("CurrentStop"),
            next_stop=item.get("NextStop"),
        )
