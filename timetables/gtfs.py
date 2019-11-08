import datetime
import difflib
from django.db.models import Min, Q, Prefetch
from multigtfs.models import Trip, StopTime
from bustimes.timetables import Row, Cell


class Timetable(object):
    def __init__(self):
        self.groupings = []

    def date_options(self):
        start_date = min(self.date, datetime.date.today())
        end_date = start_date + datetime.timedelta(weeks=2)
        while start_date <= end_date:
            yield start_date
            start_date += datetime.timedelta(days=1)
        if self.date >= start_date:
            yield self.date


class Grouping(object):
    def __init__(self):
        self.name = ''
        self.rows = []

    def __str__(self):
        return self.name


class Stop:
    def __init__(self, atco_code, name):
        self.atco_code = atco_code
        self.name = name

    def __str__(self):
        return self.name or self.atco_code


def get_grouping_name_part(stop_name):
    return stop_name.split(', ')[0]


def get_grouping_name(grouping):
    return '{} - {}'.format(get_grouping_name_part(grouping.rows[0].stop.name),
                            get_grouping_name_part(grouping.rows[-1].stop.name))


def get_stop_id(stop_id):
    if '_merged_' in stop_id:
        parts = stop_id.split('_')
        return parts[parts.index('merged') - 1]
    return stop_id


differ = difflib.Differ(charjunk=lambda _: True)


def handle_trips(trips, day):
    if not day:
        day = datetime.date.today()

    previous_list = []

    rows = []

    for x, trip in enumerate(trips):
        previous_list = [row.stop.atco_code for row in rows]
        current_list = [get_stop_id(stop.stop.stop_id) for stop in trip.stoptime_set.all()]
        diff = differ.compare(previous_list, current_list)

        y = 0  # how many rows along we are

        for stop in trip.stoptime_set.all():
            stop_id = get_stop_id(stop.stop.stop_id)

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

            assert instruction[2:] == stop_id

            if instruction[0] == '+':
                row = Row(Stop(stop_id, stop.stop.name), [''] * x)
                if not existing_row:
                    rows.append(row)
                else:
                    rows = rows[:y] + [row] + rows[y:]
                existing_row = row
            else:
                row = existing_row
                assert instruction[2:] == existing_row.stop.atco_code

            row.times.append(Cell(None, stop.arrival_time, stop.departure_time))

            y += 1

        if x:
            for row in rows:
                if len(row.times) == x:
                    row.times.append('')

    for row in rows:
        row.has_waittimes = any(cell.wait_time for cell in row.times if type(cell) is Cell)

    grouping = Grouping()
    grouping.rows = rows

    return grouping


def get_timetable(routes, day=None, collection=None):
    if not routes:
        return

    trips_dict = {}

    trips = Trip.objects.filter(route__in=routes).defer('geometry')
    trips = trips.annotate(departure_time=Min('stoptime__departure_time')).order_by('departure_time')
    if day:
        trips = trips.filter(Q(service__servicedate__date=day, service__servicedate__exception_type=1) |
                             Q(service__start_date__lte=day, service__end_date__gte=day,
                               **{'service__' + day.strftime('%A').lower(): True}))
        trips = trips.exclude(service__servicedate__date=day, service__servicedate__exception_type=2)
    else:
        # every trip (for getting full list of stops)
        today = datetime.date.today()
        trips = trips.filter(Q(service__end_date__gte=today) |
                             Q(service__servicedate__date__gte=today, service__servicedate__exception_type=1))
    prefetch = Prefetch('stoptime_set', queryset=StopTime.objects.select_related('stop').order_by('stop_sequence'))
    trips = trips.prefetch_related(prefetch).select_related('service')
    for trip in trips:
        direction = trip.direction
        if direction == '':
            direction = trip.shape_id
        if direction in trips_dict:
            trips_dict[direction].append(trip)
        else:
            trips_dict[direction] = [trip]

    t = Timetable()
    t.groupings = [handle_trips(trips_dict[key], day) for key in trips_dict]
    t.date = day
    for grouping in t.groupings:
        grouping.name = get_grouping_name(grouping)
    return t
