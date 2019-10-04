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

        self.date = date
        midnight = datetime.datetime.combine(self.date, datetime.time())

        trips = self.route.trip_set.filter(**{'calendar__' + self.date.strftime('%a').lower(): True})
        trips = trips.exclude(calendar__calendardate__operation=False,
                              calendar__calendardate__start_date__lte=self.date,
                              calendar__calendardate__end_date__gte=self.date)
        trips = trips.annotate(departure_time=Min('stoptime__departure')).order_by('departure_time')

        trips = list(trips.prefetch_related('stoptime_set'))
        trips.sort(key=cmp_to_key(Trip.cmp))

        for trip in trips:
            if trip.inbound:
                rows = self.groupings[1].rows
            else:
                rows = self.groupings[0].rows
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
                    if not existing_row:
                        rows.append(row)
                    else:
                        rows = rows[:y] + [row] + rows[y:]
                    existing_row = row
                else:
                    row = existing_row
                    assert instruction[2:] == existing_row.stop

                time = datetime.timedelta(seconds=(stoptime.departure or stoptime.arrival).seconds)
                time = (midnight + time).time()
                row.times.append(time)

                y += 1

            if x:
                for row in rows:
                    if len(row.times) == x:
                        row.times.append('')

    def date_options(self):
        date = max(self.route.start_date, datetime.date.today())
        end_date = min(self.route.end_date, date + datetime.timedelta(days=21))
        while date <= end_date:
            yield date
            date += datetime.timedelta(days=1)


class Grouping:
    def __init__(self):
        self.rows = []


class Row:
    def __init__(self, stop, times=[]):
        self.stop = stop
        self.times = times


class Source(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class Route(models.Model):
    source = models.ForeignKey(Source, models.CASCADE)
    code = models.CharField(max_length=255)
    line_brand = models.CharField(max_length=255)
    line_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

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
