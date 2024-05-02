from datetime import date, datetime, timedelta
from difflib import Differ

from django.db.models import FilteredRelation, OuterRef, Q
from django.utils import timezone
from sql_util.utils import Exists

from .models import (
    BankHolidayDate,
    Calendar,
    CalendarBankHoliday,
    CalendarDate,
    StopTime,
    Trip,
)

differ = Differ(charjunk=lambda _: True)


class log_time_taken:
    def __init__(self, logger):
        self.logger = logger

    def __enter__(self):
        self.start = datetime.now()

    def __exit__(self, _, __, ___):
        self.logger.info(f"  ⏱️ {datetime.now() - self.start}")


def get_routes(routes, when=None, from_date=None):
    # complicated way of working out which Passenger .zip applies
    current_prefixes = {}
    for route in routes:
        if route.source.settings and route.source_id not in route.source.settings:
            prefix_dates = [
                (prefix, date.fromisoformat(dates[0]), date.fromisoformat(dates[1]))
                for prefix, dates in route.source.settings.items()
            ]
            prefix_dates.sort(key=lambda p, f, t: f)  # sort by from_date
            for prefix, from_date, to_date in prefix_dates:
                if when and (from_date <= when < to_date):
                    current_prefixes[route.source_id] = prefix
                    break
    if current_prefixes:
        routes = [
            route
            for route in routes
            if route.source_id not in current_prefixes
            or route.code.startswith(current_prefixes[route.source_id])
        ]
        return routes

    revision_numbers = set(route.revision_number for route in routes)

    if len(revision_numbers) == 1:
        if when:
            routes = [route for route in routes if route.contains(when)]

        if from_date:
            # just filter out previous versions
            routes = [
                route
                for route in routes
                if route.end_date is None or route.end_date >= from_date
            ]

    if len(routes) <= 1:
        return routes

    sources = set(route.source for route in routes)
    if len(sources) > 1 and any(
        route.code.startswith("Merged") and route.source.name == "W" for route in routes
    ):
        routes = [route for route in routes if route.source.name == "W"]
        if len(routes) <= 1:
            return routes

    # https://techforum.tfl.gov.uk/t/duplicate-files-in-journey-planner-datastore-is-there-a-way-to-choose-the-right-one/2571
    if routes and all(
        route.source.name == "L"
        and route.code.split("-")[:-1] == routes[0].code.split("-")[:-1]
        and route.start_date == routes[0].start_date
        and route.end_date == routes[0].end_date
        for route in routes[1:]
    ):
        return [max(routes, key=lambda r: r.code)]

    # use maximum revision number for each service_code (TxC Service)
    if when and len(revision_numbers) > 1:
        routes = list(routes)
        routes.sort(key=lambda r: r.revision_number)
        revision_numbers = {}
        for route in routes:
            route.key = route.service_code.replace(":0", ":")

            if route.source.name.startswith(
                "First Bus_"
            ) or route.source.name.startswith(
                "National Express West Midlands"
            ):  # journeys may be split between sources (First Bristol)
                route.key = f"{route.key}:{route.source_id}"

            # use some clues in the filename (or a very good clue in the source URL)
            # to tell if the data is from Ticketer, and adapt accordingly
            # - the revision number applies to a bit of the filename
            # (e.g. the '10W' bit in 'AMSY_10W_AMSYP...') *not* the service_code
            parts = route.code.split("_")
            looks_like_ticketer_route = (
                7 >= len(parts) >= 6
                and parts[3].isdigit()
                and (parts[4].isdigit() or parts[4] == "-")
                and len(parts[-1]) == 40
            )

            if ".ticketer." in route.source.url:
                assert looks_like_ticketer_route
                route.key = f"{route.key}:{parts[1]}"
            elif looks_like_ticketer_route:
                route.key = f"{route.key}:{parts[1]}"

            if route.key not in revision_numbers or (
                route.revision_number > revision_numbers[route.key]
                and (not route.start_date or route.start_date <= when)
            ):
                revision_numbers[route.key] = route.revision_number
        routes = [
            route
            for route in routes
            if route.revision_number == revision_numbers[route.key]
        ]

    sources = set(route.source_id for route in routes)

    # remove duplicates
    if len(sources) > 1:
        sources_by_sha1 = {
            route.source.sha1: route.source_id for route in routes if route.source.sha1
        }
        # if multiple sources have the same sha1 hash, we're only interested in one
        routes = [
            route
            for route in routes
            if not route.source.sha1
            or route.source_id == sources_by_sha1[route.source.sha1]
        ]
    elif len(routes) == 2 and all(
        route.code.startswith("NCSD_TXC") for route in routes
    ):
        # favour the TxC 2.1 version of NCSD data, if both versions' dates are current
        routes = [route for route in routes if route.code.startswith("NCSD_TXC/")]

    if when and len(sources) == 1:
        override_routes = [
            route for route in routes if route.start_date == route.end_date == when
        ]
        if override_routes:  # e.g. Lynx BoxingDayHoliday
            routes = override_routes

    return routes


def get_calendars(when, calendar_ids=None):
    between_dates = Q(start_date__lte=when) & (Q(end_date__gte=when) | Q(end_date=None))

    calendars = Calendar.objects.filter(between_dates)
    calendar_calendar_dates = CalendarDate.objects.filter(calendar=OuterRef("id"))
    calendar_dates = calendar_calendar_dates.filter(between_dates)

    if calendar_ids is not None:
        # cunningly make the query faster
        calendars = calendars.filter(id__in=calendar_ids)
        calendar_dates = calendar_dates.filter(calendar__in=calendar_ids)
    exclusions = calendar_dates.filter(operation=False)
    inclusions = calendar_dates.filter(operation=True)
    special_inclusions = Exists(inclusions.filter(special=True))
    only_certain_dates = Exists(
        calendar_calendar_dates.filter(special=False, operation=True)
    )

    calendar_bank_holidays = CalendarBankHoliday.objects.filter(
        Exists(
            BankHolidayDate.objects.filter(
                date=when, bank_holiday=OuterRef("bank_holiday")
            )
        ),
        calendar=OuterRef("id"),
    )
    bank_holiday_inclusions = Exists(calendar_bank_holidays.filter(operation=True))
    bank_holiday_exclusions = ~Exists(calendar_bank_holidays.filter(operation=False))

    return calendars.filter(
        ~Exists(exclusions),
        Q(
            bank_holiday_exclusions,
            ~only_certain_dates | Exists(inclusions),
            **{f"{when:%a}".lower(): True},
        )
        | special_inclusions
        | bank_holiday_inclusions & bank_holiday_exclusions,
    )


def get_stop_times(date: datetime, time: timedelta, stop, services_routes: dict):
    times = StopTime.objects.filter(pick_up=True)

    try:
        times = times.filter(stop__stop_area=stop)
    except ValueError:
        times = times.filter(stop=stop)

    if time:
        times = times.filter(departure__gte=time)
    else:
        times = times.filter(departure__isnull=False)
    routes = []
    for service_routes in services_routes.values():
        routes += get_routes(service_routes, date)
    return times.annotate(
        trips=FilteredRelation("trip", condition=Q(trip__route__in=routes))
    ).filter(trips__calendar__in=get_calendars(date))


def get_descriptions(routes):
    inbound_outbound_descriptions = {
        (route.outbound_description, route.inbound_description): None
        for route in routes
        if route.outbound_description != route.inbound_description
    }.keys()

    origins_and_destinations = list(
        {
            tuple(filter(None, [route.origin, route.via, route.destination])): None
            for route in routes
            if route.origin and route.destination
        }.keys()
    )

    if len(origins_and_destinations) > 1:
        for i, parts in enumerate(origins_and_destinations):
            for j, other_parts in enumerate(origins_and_destinations[i:]):
                if parts[0] == other_parts[-1]:
                    origins_and_destinations[i + j] = other_parts + parts[1:]
                    origins_and_destinations[i] = None
                    break
                elif parts[-1] == other_parts[0]:
                    origins_and_destinations[i + j] = parts + other_parts[1:]
                    origins_and_destinations[i] = None
                    break
        origins_and_destinations = list(filter(None, origins_and_destinations))
        inbound_outbound_descriptions = ()

        if (
            len(origins_and_destinations) == 2
            and len(origins_and_destinations[0]) == 2
            and len(origins_and_destinations[1]) == 2
        ):
            if origins_and_destinations[0][1] == origins_and_destinations[1][1]:
                origins_and_destinations = [
                    (
                        f"{origins_and_destinations[0][0]} or {origins_and_destinations[1][0]}",
                        origins_and_destinations[0][1],
                    )
                ]
            elif origins_and_destinations[0][0] == origins_and_destinations[1][0]:
                origins_and_destinations = [
                    (
                        origins_and_destinations[0][0],
                        f"{origins_and_destinations[0][1]} or {origins_and_destinations[1][1]}",
                    )
                ]

    return inbound_outbound_descriptions, origins_and_destinations


def get_trip(
    journey,
    datetime=None,
    date=None,
    operator_ref=None,
    origin_ref=None,
    destination_ref=None,
    departure_time=None,
    journey_code="",
):
    if not journey.service:
        return

    if not datetime:
        datetime = journey.datetime
    if not date:
        date = (departure_time or datetime).date()

    routes = get_routes(journey.service.route_set.select_related("source"), date)
    if not routes:
        return
    trips = Trip.objects.filter(route__in=routes)

    if destination_ref and " " not in destination_ref and destination_ref[:3].isdigit():
        destination = Q(destination=destination_ref)
    else:
        destination = None

    if journey.direction == "outbound":
        direction = Q(inbound=False)
    elif journey.direction == "inbound":
        direction = Q(inbound=True)
    else:
        direction = None

    if departure_time:
        start = timezone.localtime(departure_time)
        start = timedelta(hours=start.hour, minutes=start.minute)
    elif len(journey_code) == 4 and journey_code.isdigit() and int(journey_code) < 2400:
        hours = int(journey_code[:-2])
        minutes = int(journey_code[-2:])
        start = timedelta(hours=hours, minutes=minutes)
    else:
        start = None

    if start is not None:
        trips_at_start = trips.filter(start=start)

        # special strategy for TfL data
        if operator_ref == "TFLO" and departure_time and origin_ref and destination_ref:
            trips_at_start = trips_at_start.filter(
                Exists("stoptime", filter=Q(stop=origin_ref)),
                Exists("stoptime", filter=Q(stop=destination_ref)),
            )
        elif destination:
            if direction:
                destination |= direction
            trips_at_start = trips_at_start.filter(destination)
        elif direction:
            trips_at_start = trips_at_start.filter(direction)

        try:
            return trips_at_start.get()
        except Trip.MultipleObjectsReturned:
            try:
                return trips_at_start.get(calendar__in=get_calendars(date))
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass
        except Trip.DoesNotExist:
            if destination and departure_time:
                try:
                    return trips.get(start=start, calendar__in=get_calendars(date))
                except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                    pass

    if not journey.code:
        return

    trips = trips.filter(
        Q(ticket_machine_code=journey.code) | Q(vehicle_journey_code=journey.code)
    )

    try:
        return trips.get()
    except Trip.DoesNotExist:
        return
    except Trip.MultipleObjectsReturned:
        return trips.filter(calendar__in=get_calendars(date)).first()
