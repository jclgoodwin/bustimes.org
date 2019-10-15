import datetime
from difflib import Differ
from django.db.models import Q
# from functools import cmp_to_key
from .models import Calendar, Trip

differ = Differ(charjunk=lambda _: True)


def get_journey_patterns(trips):
    trips = trips.prefetch_related('stoptime_set')

    patterns = []
    pattern_hashes = set()

    for trip in trips:
        pattern = [stoptime.stop_code for stoptime in trip.stoptime_set.all()]
        pattern_hash = str(pattern)
        if pattern_hash not in pattern_hashes:
            patterns.append(pattern)
            pattern_hashes.add(pattern_hash)

    return patterns


def get_stop_usages(trips):
    groupings = [[], []]

    trips = trips.prefetch_related('stoptime_set')

    for trip in trips:
        if trip.inbound:
            grouping = 1
        else:
            grouping = 0
        rows = groupings[grouping]

        new_rows = [stoptime.stop_code for stoptime in trip.stoptime_set.all()]
        diff = differ.compare(rows, new_rows)

        y = 0  # how many rows down we are

        for stoptime in trip.stoptime_set.all():
            if y < len(rows):
                existing_row = rows[y]
            else:
                existing_row = None

            instruction = next(diff)

            while instruction[0] in '-?':
                if instruction[0] == '-':
                    y += 1
                    if y < len(rows):
                        existing_row = rows[y]
                    else:
                        existing_row = None
                instruction = next(diff)

            assert instruction[2:] == stoptime.stop_code

            if instruction[0] == '+':
                if not existing_row:
                    rows.append(stoptime.stop_code)
                else:
                    rows = groupings[grouping] = rows[:y] + [stoptime.stop_code] + rows[y:]
                existing_row = stoptime.stop_code
            else:
                assert instruction[2:] == existing_row

            y += 1

    return groupings


class Timetable:
    def __init__(self, routes, date):
        self.routes = routes
        self.groupings = (Grouping(), Grouping(True))

        self.date = date

        self.calendars = Calendar.objects.filter(trip__route__in=routes).distinct()

        if not routes:
            return

        if not self.date:
            for date in self.date_options():
                self.date = date
                break
        if not self.date:
            return

        exclusions = Calendar.objects.filter(Q(calendardate__end_date__gte=self.date) | Q(calendardate__end_date=None),
                                             calendardate__start_date__lte=self.date,
                                             calendardate__operation=False)
        trips = Trip.objects.filter(Q(calendar__end_date__gte=self.date) | Q(calendar__end_date=None),
                                    route__in=routes,
                                    calendar__start_date__lte=self.date,
                                    **{'calendar__' + self.date.strftime('%a').lower(): True})
        trips = trips.exclude(calendar__in=exclusions).order_by('start').prefetch_related('notes')

        trips = list(trips.prefetch_related('stoptime_set'))
        # trips.sort(key=cmp_to_key(Trip.cmp))

        for trip in trips:
            self.handle_trip(trip)

        for grouping in self.groupings:
            grouping.do_heads_and_feet()

    def handle_trip(self, trip):
        if trip.inbound:
            grouping = self.groupings[1]
        else:
            grouping = self.groupings[0]
        grouping.trips.append(trip)
        rows = grouping.rows
        if rows:
            x = len(rows[0].times)
        else:
            x = 0
        previous_list = [row.stop.atco_code for row in rows]
        current_list = [stoptime.stop_code for stoptime in trip.stoptime_set.all()]
        diff = differ.compare(previous_list, current_list)

        y = 0  # how many rows along we are

        for stoptime in trip.stoptime_set.all():
            if y < len(rows):
                existing_row = rows[y]
            else:
                existing_row = None

            instruction = next(diff)

            while instruction[0] in '-?':
                if instruction[0] == '-':
                    y += 1
                    if y < len(rows):
                        existing_row = rows[y]
                    else:
                        existing_row = None
                instruction = next(diff)

            assert instruction[2:] == stoptime.stop_code

            if instruction[0] == '+':
                row = Row(Stop(stoptime.stop_code), [''] * x)
                row.timing_status = stoptime.timing_status
                if not existing_row:
                    rows.append(row)
                else:
                    rows = grouping.rows = rows[:y] + [row] + rows[y:]
                existing_row = row
            else:
                row = existing_row
                assert instruction[2:] == existing_row.stop.atco_code

            cell = Cell(stoptime, stoptime.arrival, stoptime.departure)
            row.times.append(cell)

            y += 1

        cell.last = True

        if x:
            for row in rows:
                if len(row.times) == x:
                    row.times.append('')

    def date_options(self):
        date = datetime.date.today()
        start_dates = [route.start_date for route in self.routes if route.start_date]
        if start_dates:
            date = max(date, max(start_dates))

        end_date = date + datetime.timedelta(days=21)
        end_dates = [route.end_date for route in self.routes if route.end_date]
        if end_dates:
            end_date = min(end_date, max(end_dates))

        if self.date and self.date < date:
            yield self.date
        while date <= end_date:
            if any(getattr(calendar, date.strftime('%a').lower()) for calendar in self.calendars):
                yield date
            date += datetime.timedelta(days=1)
        if self.date and self.date > end_date:
            yield self.date


class Grouping:
    def __init__(self, inbound=False):
        self.rows = []
        self.trips = []
        self.inbound = inbound
        self.column_feet = {}

    def __str__(self):
        if self.inbound:
            return 'Inbound'
        return 'Outbound'

    def has_minor_stops(self):
        for row in self.rows:
            if row.timing_status == 'OTH':
                return True

    def do_heads_and_feet(self):
        # previous_trip = None

        for i, trip in enumerate(self.trips):
            for note in trip.notes.all():
                # print(note)
                # if note.code in self.column_feet:
                #     if note in previous_trip.notes.all():
                #         self.column_feet[note.code][-1].span += 1
                #     else:
                #         self.column_feet[note.code].append(ColumnFoot(note))
                if i:
                    self.column_feet[note.code] = [ColumnFoot(None, i), ColumnFoot(note)]
                else:
                    self.column_feet[note.code] = [ColumnFoot(note)]
            # for key in self.column_feet:
            #     if key not in trip.notes:
            #         if not self.column_feet[key][-1].notes:
            #             self.column_feet[key][-1].span += 1
            #         else:
            #             self.column_feet[key].append(ColumnFoot(None, 1))
            # previous_trip = trip


class ColumnHead(object):
    def __init__(self, service, span):
        self.service = service
        self.span = span


class ColumnFoot(object):
    def __init__(self, note, span=1):
        self.notes = note and note.text
        self.span = span


class Row:
    def __init__(self, stop, times=[]):
        self.stop = stop
        self.times = times


class Stop:
    def __init__(self, atco_code):
        self.atco_code = atco_code

    def __str__(self):
        return self.atco_code


class Cell:
    last = False

    def __init__(self, stoptime, arrival, departure):
        self.stoptime = stoptime
        self.arrival = arrival
        self.departure = departure
        self.activity = stoptime.activity

    def __str__(self):
        arrival = self.arrival
        string = str(arrival)[:-3]
        string = string.replace('1 day, ', '', 1)
        if len(string) == 4:
            return '0' + string
        return string

    def __eq__(self, other):
        if type(other) == datetime.time:
            return self.stoptime.arrival == other or self.stoptime.departure == other
        return self.stoptime.arrival == other.stoptime.arrival and self.stoptime.departure == other.stoptime.departure
