from datetime import datetime
from difflib import Differ

from django.db.models import OuterRef, Q
from sql_util.utils import Exists

from .models import BankHolidayDate, Calendar, CalendarBankHoliday, CalendarDate

differ = Differ(charjunk=lambda _: True)


class log_time_taken:
    def __init__(self, logger):
        self.logger = logger

    def __enter__(self):
        self.start = datetime.now()

    def __exit__(self, _, __, ___):
        self.logger.info(f"  ⏱️ {datetime.now() - self.start}")


def get_routes(routes, when=None, from_date=None):
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

    if len(routes) == 1:
        return routes

    sources = set(route.source for route in routes)
    if len(sources) > 1 and any(source.name == "W" for source in sources):
        routes = [route for route in routes if route.source.name == "W"]
        if len(routes) == 1:
            return routes

    # use maximum revision number for each service_code
    if when and len(revision_numbers) > 1:
        revision_numbers = {}
        for route in routes:
            route.key = f"{route.service_code}:{route.service_id}"

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
                and route.start_date <= when
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

    # use latest passenger zipfile filename
    if any(".zip" in route.code for route in routes) and len(routes) > 1:
        prefixes = set(route.code.split(".zip")[0] for route in routes)
        if when or all(
            route.end_date == routes[0].end_date
            and route.start_date == routes[0].start_date
            for route in routes[1:]
        ):
            if len(prefixes) > 1:
                latest_prefix = f"{max(prefixes)}.zip"
                return [
                    route for route in routes if route.code.startswith(latest_prefix)
                ]

    elif when and len(sources) == 1:
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
