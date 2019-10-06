import datetime
from difflib import Differ
from functools import cmp_to_key
from django.contrib.gis.db import models
from django.db.models import Min
from django.urls import reverse


differ = Differ(charjunk=lambda _: True)


class Timetable:
    def __init__(self, route, date):
        self.route = route
        self.groupings = (Grouping(), Grouping())

        self.calendars = Calendar.objects.filter(trip__route=self.route).distinct()

        self.date = date

        if not self.date:
            for date in self.date_options():
                self.date = date
                break
        if not self.date:
            return

        midnight = datetime.datetime.combine(self.date, datetime.time())

        trips = self.route.trip_set.filter(**{'calendar__' + self.date.strftime('%a').lower(): True})
        trips = trips.exclude(calendar__calendardate__operation=False,
                              calendar__calendardate__start_date__lte=self.date,
                              calendar__calendardate__end_date__gte=self.date)
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
        previous_list = [row.stop for row in rows]
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
                row = Row(stoptime.stop_code, [''] * x)
                row.timing_status = stoptime.timing_status
                if not existing_row:
                    rows.append(row)
                else:
                    rows = grouping.rows = rows[:y] + [row] + rows[y:]
                existing_row = row
            else:
                row = existing_row
                assert instruction[2:] == existing_row.stop

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
        date = max(self.route.start_date, datetime.date.today())
        end_date = min(self.route.end_date, date + datetime.timedelta(days=21))
        while date <= end_date:
            if any(getattr(calendar, date.strftime('%a').lower()) for calendar in self.calendars):
                yield date
            date += datetime.timedelta(days=1)


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


class Cell(object):
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


class Route(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    code = models.CharField(max_length=255)
    line_brand = models.CharField(max_length=255)
    line_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    service = models.ForeignKey('busstops.Service', models.CASCADE)

    class Meta:
        unique_together = ('source', 'code')

    def __str__(self):
        return ' – '.join(part for part in (self.line_name, self.line_brand, self.description) if part)

    def get_absolute_url(self):
        return reverse('route_detail', args=(self.id,))

    def get_timetable(self, date):
        return Timetable(self, date)


class Calendar(models.Model):
    mon = models.BooleanField()
    tue = models.BooleanField()
    wed = models.BooleanField()
    thu = models.BooleanField()
    fri = models.BooleanField()
    sat = models.BooleanField()
    sun = models.BooleanField()
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)


class CalendarDate(models.Model):
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    operation = models.BooleanField()


class Note(models.Model):
    code = models.CharField(max_length=16)
    text = models.CharField(max_length=255)


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)

    def cmp(a, b):
        """Compare two journeys"""
        # if x.sequencenumber is not None and y.sequencenumber is not None:
        #     if x.sequencenumber > y.sequencenumber:
        #         return 1
        #     if x.sequencenumber < y.sequencenumber:
        #         return -1
        #     return 0
        a_times = a.stoptime_set.all()
        b_times = b.stoptime_set.all()
        a_time = a_times[0].arrival
        b_time = b_times[0].arrival
        if a_times[0].stop_code != b_times[0].stop_code:
            times = {time.stop_code: time.arrival for time in a_times}
            for time in b_times:
                if time.stop_code in times:
                    if time.arrival >= b_time:
                        if times[time.stop_code] >= a_time:
                            a_time = times[time.stop_code]
                            b_time = time.arrival
        #             break
        if a_time > b_time:
            return 1
        if b_time < a_time:
            return -1
        return 0


class StopTime(models.Model):
    trip = models.ForeignKey(Trip, models.CASCADE)
    stop_code = models.CharField(max_length=255)
    arrival = models.DurationField()
    departure = models.DurationField()
    sequence = models.PositiveSmallIntegerField()
    timing_status = models.CharField(max_length=3, blank=True)
    activity = models.CharField(max_length=16, blank=True)

    class Meta:
        ordering = ('sequence',)
