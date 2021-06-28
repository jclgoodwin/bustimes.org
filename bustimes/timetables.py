import datetime
from django.utils.timezone import localdate
from difflib import Differ
from functools import cmp_to_key, partial
from django.db.models import Prefetch
from .utils import format_timedelta
from .models import get_calendars, get_routes, Calendar, Trip, StopTime

differ = Differ(charjunk=lambda _: True)


def get_journey_patterns(trips):
    trips = trips.prefetch_related(Prefetch('stoptime_set', queryset=StopTime.objects.filter(stop__isnull=False)))

    patterns = []
    pattern_hashes = set()

    for trip in trips:
        pattern = [stoptime.stop_id for stoptime in trip.stoptime_set.all()]
        pattern_hash = str(pattern)
        if pattern_hash not in pattern_hashes:
            patterns.append(pattern)
            pattern_hashes.add(pattern_hash)

    return patterns


def get_stop_usages(trips):
    groupings = [[], []]

    trips = trips.prefetch_related(Prefetch('stoptime_set', queryset=StopTime.objects.filter(stop__isnull=False)))

    for trip in trips:
        if trip.inbound:
            grouping_id = 1
        else:
            grouping_id = 0
        grouping = groupings[grouping_id]

        stop_times = trip.stoptime_set.all()

        old_rows = [stop_time.stop_id for stop_time in grouping]
        new_rows = [stop_time.stop_id for stop_time in stop_times]
        diff = differ.compare(old_rows, new_rows)

        y = 0  # how many rows down we are

        for stop_time in stop_times:
            if y < len(old_rows):
                existing_row = old_rows[y]
            else:
                existing_row = None

            instruction = next(diff)

            while instruction[0] in '-?':
                if instruction[0] == '-':
                    y += 1
                    if y < len(old_rows):
                        existing_row = old_rows[y]
                    else:
                        existing_row = None
                instruction = next(diff)

            assert instruction[2:] == stop_time.stop_id

            if instruction[0] == '+':
                if not existing_row:
                    grouping.append(stop_time)
                    old_rows.append(stop_time.stop_id)
                else:
                    grouping = grouping[:y] + [stop_time] + grouping[y:]
                    old_rows = old_rows[:y] + [stop_time.stop_id] + old_rows[y:]
                # existing_row = stop_time.stop_id
            else:
                assert instruction[2:] == existing_row

            y += 1

        groupings[grouping_id] = grouping

    return groupings


def compare_trips(rows, trip_ids, a, b):
    a_top = None
    a_bottom = None
    b_top = None
    b_bottom = None
    a_index = trip_ids.index(a.id)
    b_index = trip_ids.index(b.id)

    for i, row in enumerate(rows):
        if row.times[a_index]:
            if a_top is None:
                a_top = i
            a_bottom = i
        if row.times[b_index]:
            if b_top is None:
                b_top = i
            b_bottom = i

    if a_top == b_top:
        a_time = a.start
        b_time = b.start
    elif a_bottom == b_bottom:
        a_time = a.end
        b_time = b.end
    elif a_top >= b_bottom:  # b is above a
        a_time = a.start
        b_time = b.end
    elif b_top >= a_bottom:  # a is above a
        a_time = a.end
        b_time = b.start
    else:
        a_time = a.start
        b_time = b.start

    if a_time > b_time:
        return 1  # a is later
    elif a_time < b_time:
        return -1  # b is later
    elif a_top >= b_bottom:  # b is above a
        return 1
    elif b_top >= a_bottom:  # a is above a
        return -1
    return 0


class Timetable:
    def __init__(self, routes, date):
        self.today = localdate()

        routes = list(routes.select_related('source'))
        self.routes = routes
        self.current_routes = routes

        self.date = date

        self.groupings = [Grouping(), Grouping(True)]

        self.calendar = None
        self.start_date = None
        if not routes:
            self.calendars = ()
            return

        self.calendars = Calendar.objects.filter(
            trip__route__in=self.routes
        ).distinct().prefetch_related('calendardate_set')

        if not date and len(self.calendars) == 1 and len(routes) == 1:
            calendar = self.calendars[0]
            # calendar has a summary like 'school days only', or no exceptions within 21 days
            if calendar.is_sufficiently_simple(self.today + datetime.timedelta(days=21)):
                self.calendar = calendar
                if calendar.start_date > self.today:  # starts in the future
                    self.start_date = calendar.start_date

        if not self.calendar:
            self.date_options = list(self.get_date_options())
            if not self.date:
                if self.date_options:
                    self.date = self.date_options[0]
                else:
                    return

            if len(routes) > 1:
                # consider revision numbers:
                routes = get_routes(routes, self.date)
                self.current_routes = routes

        trips = Trip.objects.filter(route__in=routes)
        if not self.calendar:
            calendar_ids = [calendar.id for calendar in self.calendars]
            trips = trips.filter(calendar__in=get_calendars(self.date, calendar_ids))
        trips = trips.defer(
            'route__service__geometry'
        ).select_related(
            'route__service'
        ).prefetch_related(
            'notes',
            'stoptime_set'
        )

        for trip in trips:
            if trip.inbound:
                self.groupings[1].trips.append(trip)
            else:
                self.groupings[0].trips.append(trip)

        del trips

        for grouping in self.groupings:

            # longest trips first, to minimise duplicate rows
            grouping.trips.sort(key=lambda t: -len(t.stoptime_set.all()))

            # build the table
            for trip in grouping.trips:
                grouping.handle_trip(trip)

            trip_ids = [trip.id for trip in grouping.trips]

            # sort columns properly, now we have the rows
            grouping.trips.sort(key=cmp_to_key(partial(compare_trips, grouping.rows, trip_ids)))

            new_trip_ids = [trip.id for trip in grouping.trips]
            indices = [trip_ids.index(trip_id) for trip_id in new_trip_ids]

            for row in grouping.rows:
                # reassemble in order
                row.times = [row.times[i] for i in indices]

                row.has_waittimes = any(type(cell) is Cell and cell.wait_time for cell in row.times)

            grouping.do_heads_and_feet()

        if all(grouping.trips for grouping in self.groupings):
            self.groupings.sort(key=Grouping.get_order)

    def get_date_options(self):
        date = self.today

        for calendar in self.calendars:
            for calendar_date in calendar.calendardate_set.all():
                if not calendar_date.operation and calendar_date.contains(date):
                    calendar.start_date = calendar_date.end_date
                    break
        start_dates = [calendar.start_date for calendar in self.calendars]
        if start_dates:
            date = max(date, min(start_dates))

        end_date = date + datetime.timedelta(days=21)
        end_dates = [route.end_date for route in self.routes]
        if end_dates and all(end_dates):
            end_date = min(end_date, max(end_dates))  # 21 days in the future, or the end date, whichever is sooner

        if self.date and self.date < date:
            yield self.date
        while date <= end_date:
            if any(calendar.allows(date) for calendar in self.calendars) or date == self.date:
                yield date
            date += datetime.timedelta(days=1)
        if self.date and self.date > end_date:
            yield self.date

    def has_set_down_only(self):
        for grouping in self.groupings:
            for row in grouping.rows:
                for cell in row.times:
                    if type(cell) is Cell and not cell.last and cell.stoptime.activity == 'setDown':
                        return True

    def credits(self):
        return set(route.source.credit(route) for route in self.current_routes)


class Repetition:
    """Represents a special cell in a timetable, spanning multiple rows and columns,
    with some text like 'then every 5 minutes until'.
    """
    def __init__(self, colspan, duration):
        self.colspan = colspan
        self.duration = duration

    def __str__(self):
        # cleverly add non-breaking spaces if there aren't many rows
        if self.duration.seconds == 3600:
            if self.min_height < 3:
                return 'then\u00A0hourly until'
            return 'then hourly until'
        if self.duration.seconds % 3600 == 0:
            duration = '{} hours'.format(int(self.duration.seconds / 3600))
        else:
            duration = '{} minutes'.format(int(self.duration.seconds / 60))
        if self.min_height < 3:
            return 'then\u00A0every {}\u00A0until'.format(duration.replace(' ', '\u00A0'))
        if self.min_height < 4:
            return 'then every\u00A0{} until'.format(duration.replace(' ', '\u00A0'))
        return 'then every {} until'.format(duration)


def abbreviate(grouping, i, in_a_row, difference):
    """Given a Grouping, and a timedelta, modify each row and..."""
    seconds = difference.total_seconds()
    if not seconds or (seconds != 3600 and seconds > 1800):  # neither hourly nor more than every 30 minutes
        return
    repetition = Repetition(in_a_row + 1, difference)
    grouping.rows[0].times[i - in_a_row - 2] = repetition
    for j in range(i - in_a_row - 1, i - 1):
        grouping.rows[0].times[j] = None
    for j in range(i - in_a_row - 2, i - 1):
        for row in grouping.rows[1:]:
            row.times[j] = None


def journey_patterns_match(trip_a, trip_b):
    if trip_a.journey_pattern:
        if trip_a.journey_pattern == trip_b.journey_pattern:
            if trip_a.destination_id == trip_b.destination_id:
                if trip_a.end - trip_a.start == trip_b.end - trip_b.start:
                    return True
    return False


class Grouping:
    def __init__(self, inbound=False):
        self.heads = []
        self.rows = []
        self.trips = []
        self.inbound = inbound
        self.column_feet = {}

    def __str__(self):
        if self.inbound:
            return 'Inbound'
        return 'Outbound'

    def has_minor_stops(self):
        return any(row.is_minor() for row in self.rows)

    def has_major_stops(self):
        return any(not row.is_minor() for row in self.rows)

    def get_order(self):
        if self.trips:
            return self.trips[0].start

    def width(self):
        return len(self.rows[0].times)

    def rowspan(self):
        return sum(2 if row.has_waittimes else 1 for row in self.rows)

    def min_height(self):
        return sum(2 if row.has_waittimes else 1 for row in self.rows if not row.is_minor())

    def handle_trip(self, trip):
        rows = self.rows
        if rows:
            x = len(rows[0].times)  # number of existing columns
        else:
            x = 0
        previous_list = [row.stop.atco_code for row in rows]
        current_list = [stoptime.get_key() for stoptime in trip.stoptime_set.all()]
        diff = differ.compare(previous_list, current_list)

        y = 0  # how many rows along we are
        first = True

        for stoptime in trip.stoptime_set.all():
            key = stoptime.get_key()

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

            assert instruction[2:] == key

            if instruction[0] == '+':
                row = Row(Stop(key), [''] * x)
                row.timing_status = stoptime.timing_status
                if not existing_row:
                    rows.append(row)
                else:
                    rows = self.rows = rows[:y] + [row] + rows[y:]
                existing_row = row
            else:
                row = existing_row
                assert instruction[2:] == existing_row.stop.atco_code

            cell = Cell(stoptime, stoptime.arrival, stoptime.departure)
            if first:
                cell.first = True
                first = False
            row.times.append(cell)

            y += 1

        if not first:  # (there was at least 1 stoptime in the trip)
            cell.last = True

        if x:
            for row in rows:
                if len(row.times) == x:
                    row.times.append('')

    def do_heads_and_feet(self):
        if not self.trips:
            return

        previous_trip = None
        previous_note_ids = None
        in_a_row = 0
        prev_difference = None

        max_notes = max(len(trip.notes.all()) for trip in self.trips)

        for i, trip in enumerate(self.trips):
            difference = None
            notes = trip.notes.all()
            note_ids = {note.id for note in notes}

            # add notes
            for note in notes:
                if note.id in self.column_feet:
                    if note.id in previous_note_ids:
                        self.column_feet[note.id][-1].span += 1
                    else:
                        self.column_feet[note.id].append(ColumnFoot(note))
                elif note.id in previous_note_ids:
                    assert max_notes == 1
                    for note_id in self.column_feet:
                        self.column_feet[note_id][-1].span += 1
                elif i:  # not the first trip
                    if max_notes == 1 and self.column_feet:
                        # assert len(self.column_feet) == 1
                        for note_id in self.column_feet:
                            self.column_feet[note_id].append(ColumnFoot(note))
                    else:
                        self.column_feet[note.id] = [ColumnFoot(None, i), ColumnFoot(note)]
                else:
                    self.column_feet[note.id] = [ColumnFoot(note)]

            # add or expand empty cells
            if max_notes > 1 or not notes:
                for key in self.column_feet:
                    if key not in note_ids:
                        if not self.column_feet[key][-1].notes:
                            # expand existing empty cell
                            self.column_feet[key][-1].span += 1
                        else:
                            # new empty cell
                            self.column_feet[key].append(ColumnFoot(None, 1))

            if previous_trip:
                if previous_trip.route.service_id != trip.route.service_id:
                    self.heads.append(
                        ColumnHead(previous_trip.route.service, i - sum(head.span for head in self.heads)))

                if previous_note_ids != note_ids:
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0
                elif journey_patterns_match(previous_trip, trip):
                    difference = trip.start - previous_trip.start
                    if difference == prev_difference:
                        in_a_row += 1
                    else:
                        if in_a_row > 1:
                            abbreviate(self, i, in_a_row - 1, prev_difference)
                        in_a_row = 0
                else:
                    if in_a_row > 1:
                        abbreviate(self, i, in_a_row - 1, prev_difference)
                    in_a_row = 0

            prev_difference = difference
            previous_trip = trip
            previous_note_ids = note_ids

        if previous_trip:
            self.heads.append(ColumnHead(previous_trip.route.service,
                                         len(self.trips) - sum(head.span for head in self.heads)))

        if in_a_row > 1:
            abbreviate(self, len(self.trips), in_a_row - 1, prev_difference)

        for row in self.rows:
            # remove 'None' cells created during the abbreviation process
            # (actual empty cells will contain an empty string '')
            row.times = [time for time in row.times if time is not None]

    def apply_stops(self, stops):
        for row in self.rows:
            row.stop = stops.get(row.stop.atco_code, row.stop)
        self.rows = [row for row in self.rows if not row.permanently_suspended()]
        min_height = self.min_height()
        rowspan = self.rowspan()
        for cell in self.rows[0].times:
            if type(cell) is Repetition:
                cell.min_height = min_height
                cell.rowspan = rowspan

        if self.has_minor_stops() and not self.has_major_stops():
            for row in self.rows:
                if row.stop and row.stop.timing_status:
                    row.timing_status = row.stop.timing_status


class ColumnHead:
    def __init__(self, service, span):
        self.service = service
        self.span = span


class ColumnFoot:
    def __init__(self, note, span=1):
        self.notes = note and note.text
        self.span = span


class Row:
    def __init__(self, stop, times=[]):
        self.stop = stop
        self.times = times

    def is_minor(self):
        return self.timing_status == 'OTH'

    def permanently_suspended(self):
        return hasattr(self.stop, 'suspended') and self.stop.suspended


class Stop:
    def __init__(self, atco_code):
        self.timing_status = None
        self.atco_code = atco_code

    def __str__(self):
        return self.atco_code


class Cell:
    def __init__(self, stoptime, arrival, departure):
        self.first = False
        self.last = False
        self.stoptime = stoptime
        self.arrival = arrival
        self.departure = departure
        if arrival is None:
            self.arrival = departure
        elif departure is None:
            self.departure = arrival
        self.wait_time = arrival and departure and departure - arrival

    def __repr__(self):
        return format_timedelta(self.arrival)

    def departure_time(self):
        return format_timedelta(self.departure)
