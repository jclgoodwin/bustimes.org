import datetime
from difflib import Differ
from functools import cmp_to_key
from django.db.models import Min
from .models import Calendar, Trip

differ = Differ(charjunk=lambda _: True)


class Timetable:
    def __init__(self, routes, date):
        if not routes:
            return

        self.routes = routes
        self.groupings = (Grouping(), Grouping())

        self.calendars = Calendar.objects.filter(trip__route__in=routes).distinct()

        self.date = date

        if not self.date:
            for date in self.date_options():
                self.date = date
                break
        # if not self.date:
        #     return

        midnight = datetime.datetime.combine(self.date, datetime.time())

        exclusions = Calendar.objects.filter(calendardate__operation=False,
                                             calendardate__start_date__lte=self.date,
                                             calendardate__end_date__gte=self.date)

        trips = Trip.objects.filter(route__in=routes,
                                    calendar__start_date__lte=self.date,
                                    calendar__end_date__gte=self.date,
                                    **{'calendar__' + self.date.strftime('%a').lower(): True})
        trips = trips.exclude(calendar__in=exclusions)
        trips = trips.annotate(departure_time=Min('stoptime__departure')).order_by('departure_time')

        trips = list(trips.prefetch_related('stoptime_set'))
        trips.sort(key=cmp_to_key(Trip.cmp))

        for trip in trips:
            self.handle_trip(trip, midnight)

    def handle_trip(self, trip, midnight):
        if trip.inbound:
            grouping = self.groupings[1]
        else:
            grouping = self.groupings[0]
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

            if stoptime.arrival:
                arrival = (midnight + datetime.timedelta(seconds=stoptime.arrival.seconds)).time()
            else:
                arrival = None

            if stoptime.departure and stoptime.departure != stoptime.arrival:
                departure = (midnight + datetime.timedelta(seconds=stoptime.departure.seconds)).time()
            else:
                departure = None

            cell = Cell(stoptime, arrival or departure, departure)
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
    def __init__(self):
        self.rows = []

    def has_minor_stops(self):
        for row in self.rows:
            if row.timing_status == 'OTH':
                return True


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

    def __str__(self):
        return self.arrival.strftime('%H:%M')

    def __eq__(self, other):
        if type(other) == datetime.time:
            return self.stoptime.arrival == other or self.stoptime.departure == other
        return self.stoptime.arrival == other.stoptime.arrival and self.stoptime.departure == other.stoptime.departure
