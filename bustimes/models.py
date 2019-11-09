from django.db.models import Q
from django.contrib.gis.db import models


def get_calendars(when):
    calendar_dates = CalendarDate.objects.filter(Q(end_date__gte=when) | Q(end_date=None),
                                                 start_date__lte=when)
    exclusions = calendar_dates.filter(operation=False)
    inclusions = calendar_dates.filter(operation=True)
    calendars = Calendar.objects.filter(start_date__lte=when)
    return calendars.filter(Q(end_date__gte=when) | Q(end_date=None),
                            ~Q(calendardate__in=exclusions),
                            Q(calendardate__in=inclusions) | Q(**{when.strftime('%a').lower(): True}))


class Route(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    code = models.CharField(max_length=255)
    line_brand = models.CharField(max_length=255)
    line_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    service = models.ForeignKey('busstops.Service', models.CASCADE)

    class Meta:
        unique_together = ('source', 'code')

    def __str__(self):
        return ' – '.join(part for part in (self.line_name, self.line_brand, self.description) if part)


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
    end_date = models.DateField(null=True, blank=True)
    operation = models.BooleanField()


class Note(models.Model):
    code = models.CharField(max_length=16)
    text = models.CharField(max_length=255)

    def get_absolute_url(self):
        return self.trip_set.first().route.service.get_absolute_url()


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    destination = models.ForeignKey('busstops.StopPoint', models.CASCADE)
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    start = models.DurationField()
    end = models.DurationField()

    class Meta:
        index_together = (
            ('route', 'start', 'end'),
        )

    def __cmp__(a, b):
        """Compare two journeys"""
        if a.sequence is not None and a.sequence is not None:
            a.time = a.sequence
            b.time = b.sequence
        else:
            a_time = a.start
            b_time = b.start
            a_times = a.stoptime_set.all()
            b_times = b.stoptime_set.all()
            if a_times[0].stop_code != b_times[0].stop_code:
                if a.destination_id == b.destination_id:
                    a_time = a.end
                    b_time = b.end
                else:
                    times = {time.stop_code: time.arrival or time.departure for time in a_times}
                    for time in b_times:
                        if time.stop_code in times:
                            a_time = times[time.stop_code]
                            b_time = time.arrival or time.departure
                            break
                        # if cell.arrival_time >= y.departure_time:
                        #     if times[cell.stopusage.stop.atco_code] >= x.departure_time:
                        #         x_time = times[cell.stopusage.stop.atco_code]
                        #         y_time = cell.arrival_time
                        # break
        if a_time > b_time:
            return 1
        if a_time < b_time:
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
        index_together = (
            ('stop_code', 'departure'),
        )
