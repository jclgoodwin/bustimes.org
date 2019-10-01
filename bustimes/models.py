import datetime
import difflib
from django.contrib.gis.db import models
from django.urls import reverse


differ = difflib.Differ(charjunk=lambda _: True)


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

        trips = trips.prefetch_related('stoptime_set')

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
        return ' – '.join(part for part in set((self.line_name, self.line_brand, self.description)) if part)

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


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    calendar = models.ForeignKey(Calendar, models.CASCADE)


class StopTime(models.Model):
    trip = models.ForeignKey(Trip, models.CASCADE)
    stop_code = models.CharField(max_length=255)
    arrival = models.DurationField()
    departure = models.DurationField()
    sequence = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ('sequence',)
