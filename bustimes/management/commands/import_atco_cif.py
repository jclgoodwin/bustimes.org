import os
import zipfile
from datetime import date, datetime, timedelta, timezone
from functools import cache

from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand

from busstops.models import DataSource, Service, StopPoint, Operator

from ...models import (
    BankHoliday,
    Calendar,
    CalendarBankHoliday,
    CalendarDate,
    Note,
    Route,
    StopTime,
    Trip,
)


@cache
def get_operator(code, source):
    if code:
        try:
            return Operator.objects.get(noc=code)
        except Operator.DoesNotExist as e:
            pass
        try:
            return Operator.objects.get(
                operatorcode__code=code, operatorcode__source=source
            )
        except (Operator.DoesNotExist, Operator.MultipleObjectsReturned) as e:
            print(e, code)


def parse_date(string):
    if string == b"99999999":
        return
    try:
        return date(year=int(string[:4]), month=int(string[4:6]), day=int(string[6:]))
    except ValueError:
        print(string)


@cache
def get_note(note_code, note_text):
    return Note.objects.get_or_create(code=note_code or "", text=note_text[:255])[0]


def parse_time(string):
    return timedelta(hours=int(string[:2]), minutes=int(string[2:]))


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument("filenames", nargs="+", type=str)

    def handle(self, *args, **options):
        for archive_name in options["filenames"]:
            if "ulb" in archive_name.lower() or "ulsterbus" in archive_name.lower():
                source_name = "ULB"
            else:
                source_name = "MET"

            self.source, _ = DataSource.objects.get_or_create(name=source_name)

            self.source.datetime = datetime.fromtimestamp(
                os.path.getmtime(archive_name), timezone.utc
            )

            self.handle_archive(archive_name)

    def handle_archive(self, archive_name):
        self.routes = {}
        self.calendars = {}

        self.bank_holiday, _ = BankHoliday.objects.get_or_create(
            name="Northern Ireland bank holidays"
        )

        with zipfile.ZipFile(archive_name) as archive:
            for filename in archive.namelist():
                if (
                    filename.endswith(".cif")
                    and "/archive/" not in filename.lower()
                    and "/Y20/" not in filename.upper()
                ):
                    with archive.open(filename) as open_file:
                        self.handle_file(open_file)
        assert self.stop_times == []

        services = {
            route.service.id: route.service for route in self.routes.values()
        }.values()

        for service in services:
            service.do_stop_usages()

            service.update_geometry(save=False)

        Service.objects.bulk_update(
            services,
            fields=[
                "geometry",
                "description",
            ],
        )
        Route.objects.bulk_update(
            self.routes.values(),
            ["inbound_description", "revision_number", "start_date"],
        )
        for service in services:
            service.update_search_vector()

        print(
            self.source.route_set.exclude(
                code__in=self.routes.keys(), trip__isnull=False
            ).delete()
        )
        print(
            self.source.service_set.filter(current=True, route__isnull=True).update(
                current=False
            )
        )
        self.source.save(update_fields=["datetime"])

    def handle_file(self, open_file):
        self.route = None
        self.trip = None
        self.stop_times = []
        self.stop_time_notes = []
        self.notes = []

        encoding = "cp1252"

        # first, create/update StopPoints
        self.stops = {}
        for line in open_file:
            identity = line[:2]
            if identity == b"QL" or identity == b"QB":
                stop_code = line[3:15].decode().strip()
                if identity == b"QL":
                    name = line[15:63]
                    if name and stop_code not in self.stops:
                        name = name.decode(encoding).strip()
                        self.stops[stop_code] = StopPoint(
                            atco_code=stop_code,
                            common_name=name,
                            active=True,
                            source=self.source,
                        )
                elif stop_code in self.stops:
                    easting = line[15:23].strip().decode()
                    northing = line[23:31].strip().decode()
                    if easting:
                        self.stops[stop_code].latlong = GEOSGeometry(
                            f"SRID=29902;POINT({easting} {northing})"
                        )
        StopPoint.objects.bulk_create(
            self.stops.values(),
            update_conflicts=True,
            update_fields=["common_name", "latlong", "active", "source"],
            unique_fields=["atco_code"],
        )

        open_file.seek(0)

        self.filename = open_file.name

        # everything else
        previous_line = None
        for line in open_file:
            self.handle_line(line, previous_line, encoding)
            previous_line = line

    def get_calendar(self):
        line = self.trip_header
        key = line[13:38].decode() + str(self.exceptions)
        if key in self.calendars:
            return self.calendars[key]
        calendar = Calendar(
            mon=line[29:30] == b"1",
            tue=line[30:31] == b"1",
            wed=line[31:32] == b"1",
            thu=line[32:33] == b"1",
            fri=line[33:34] == b"1",
            sat=line[34:35] == b"1",
            sun=line[35:36] == b"1",
            start_date=parse_date(line[13:21]),
            end_date=parse_date(line[21:29]),
            source=self.source,
        )
        summary = []
        if line[36:37] == b"S":
            summary.append("school term time only")
        elif line[36:37] == b"H":
            summary.append("school holidays only")

        if line[37:38] == b"A":
            summary.append("and bank holidays")
        elif line[37:38] == b"B":
            summary.append("bank holidays only")
        elif line[37:38] == b"X":
            summary.append("not bank holidays")

        calendar.summary = ",".join(summary)
        calendar.save()

        if line[37:38] == b"A":
            CalendarBankHoliday.objects.create(
                operation=True,
                bank_holiday=self.bank_holiday,
                calendar=calendar,
            )
        elif line[37:38] == b"B":
            CalendarBankHoliday.objects.create(
                operation=True,
                bank_holiday=self.bank_holiday,
                calendar=calendar,
            )
        elif line[37:38] == b"X":
            CalendarBankHoliday.objects.create(
                operation=False,
                bank_holiday=self.bank_holiday,
                calendar=calendar,
            )

        CalendarDate.objects.bulk_create(
            CalendarDate(
                calendar=calendar,
                start_date=parse_date(exception[2:10]),
                end_date=parse_date(exception[10:18]),
                operation=exception[18:19] == b"1",
                special=exception[18:19] == b"1",
            )
            for exception in self.exceptions
        )

        self.calendars[key] = calendar
        return calendar

    def handle_line(self, line, previous_line, encoding):
        identity = line[:2]

        match identity:
            case b"QD":
                operator_code = line[3:7].decode().strip()
                line_name = line[7:11].decode().strip()
                service_code = f"{line_name}_{operator_code}".upper()
                route_code = f"{self.filename}#{service_code}"
                direction = line[11:12]
                description = line[12:80].decode().strip()
                if route_code in self.routes:
                    self.route = self.routes[route_code]
                    if direction == b"O":
                        self.route.service.description = description
                        self.route.description = description
                        self.route.outbound_description = description
                    else:
                        if description != self.route.inbound_description:
                            self.route.inbound_description = description
                            self.route.save()
                else:
                    defaults = {
                        "line_name": line_name,
                        "current": True,
                        "source": self.source,
                        "region_id": "NI",
                    }
                    route_defaults = {
                        "line_name": line_name,
                        "description": description,
                        "service_code": service_code,
                    }
                    if direction == b"O":
                        defaults["description"] = description
                        route_defaults["description"] = description
                        route_defaults["outbound_description"] = description
                    else:
                        route_defaults["inbound_description"] = description
                    service, _ = Service.objects.update_or_create(
                        defaults, service_code=service_code
                    )
                    route_defaults["service"] = service
                    if operator := get_operator(operator_code, self.source):
                        service.operator.add(operator)
                    self.route, created = Route.objects.update_or_create(
                        route_defaults,
                        code=route_code,
                        source=self.source,
                    )
                    if not created:
                        self.route.trip_set.all().delete()
                    self.routes[route_code] = self.route

            case b"QS":
                self.sequence = 0
                self.trip_header = line
                self.exceptions = []
                operator_code = self.trip_header[3:7].decode().strip()
                self.operator = get_operator(operator_code, self.source)

            case b"QE":
                self.exceptions.append(line)

            case b"QO" | b"QI" | b"QT":  # stop time
                stop_time = StopTime(sequence=self.sequence, trip=self.trip)
                self.sequence += 1

                stop_id = line[2:14].decode().strip()
                if stop_id in self.stops:
                    stop_time.stop_id = stop_id
                elif StopPoint.objects.filter(atco_code=stop_id).exists():
                    stop_time.stop_id = stop_id
                    self.stops[stop_id] = True
                else:
                    print(stop_id)
                    stop_time.stop_code = stop_id
                self.stop_times.append(stop_time)

                if identity == b"QO":  # origin stop
                    departure = parse_time(line[14:18])

                    calendar = self.get_calendar()
                    if self.trip and not self.trip.id:
                        print("unterminated trip!")
                        self.stop_times = []

                    self.trip = Trip(
                        operator=self.operator,
                        ticket_machine_code=self.trip_header[7:13].decode().strip(),
                        block=self.trip_header[42:48].decode().strip(),
                        start=departure,
                        route=self.route,
                        calendar=calendar,
                        inbound=self.trip_header[64:65] == b"I",
                    )
                    stop_time.trip = self.trip
                    stop_time.departure = departure
                    stop_time.sequence = 0

                    if (
                        not self.route.start_date
                        or calendar.start_date < self.route.start_date
                    ):
                        self.route.start_date = calendar.start_date
                        self.route.revision_number = calendar.start_date.strftime(
                            "%Y%m%d"
                        )

                elif identity == b"QI":  # intermediate stop
                    timing_status = line[26:28]
                    if timing_status == b"T1":
                        timing_status = "PTP"
                    elif timing_status == b"T0":
                        timing_status = "OTH"
                    else:
                        print(line)
                        return

                    stop_time.arrival = parse_time(line[14:18])
                    stop_time.departure = parse_time(line[18:22])
                    stop_time.timing_status = timing_status

                elif identity == b"QT":  # destination stop
                    stop_time.arrival = parse_time(line[14:18])

                    self.trip.destination_id = stop_time.stop_id
                    self.trip.end = stop_time.arrival

                    self.trip.save()

                    if self.notes:
                        self.trip.notes.add(*self.notes)
                        self.notes = []

                    for stop_time in self.stop_times:
                        stop_time.trip = stop_time.trip  # set trip_id
                        assert stop_time.trip_id
                    StopTime.objects.bulk_create(self.stop_times)

                    if self.stop_time_notes:
                        StopTime.notes.through.objects.bulk_create(self.stop_time_notes)
                        self.stop_time_notes = []
                    self.stop_times = []

            case b"QN":  # note
                previous_identity = previous_line[:2]
                note = line[7:81].decode(encoding).strip()
                code = line[2:7].decode(encoding).strip()
                if (
                    previous_identity == b"QO"
                    or previous_identity == b"QI"
                    or previous_identity == b"QT"
                ):
                    # stop time note
                    note_lower = note.lower()
                    if note_lower == "pick up only" or note_lower == "pick up  only":
                        if previous_identity != b"QT":
                            self.stop_times[-1].set_down = False
                    elif (
                        note_lower == "set down only"
                        or note_lower == ".set down only"
                        or note_lower == "drop off only"
                    ):
                        if previous_identity != b"QT":
                            self.stop_times[-1].pick_up = False
                    else:
                        note = get_note(code, note)
                        if self.stop_times:
                            self.stop_time_notes.append(
                                StopTime.notes.through(
                                    stoptime=self.stop_times[-1], note=note
                                )
                            )
                        self.notes.append(note)
                elif (
                    previous_identity == b"QS"
                    or previous_identity == b"QE"
                    or previous_identity == b"QN"
                ):
                    # trip note
                    note = get_note(code, note)
                    self.notes.append(note)
                else:
                    print(previous_identity[:2], line)
