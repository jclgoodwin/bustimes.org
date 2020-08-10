from django.db.models import Q, Exists, OuterRef
from django.db import models
from django.contrib.postgres.fields import DateRangeField
from django.urls import reverse


def get_calendars(when, calendar_ids=None):
    calendars = Calendar.objects.filter(Q(end_date__gte=when) | Q(end_date=None),
                                        start_date__lte=when)
    calendar_dates = CalendarDate.objects.filter(Q(end_date__gte=when) | Q(end_date=None),
                                                 start_date__lte=when)
    if calendar_ids is not None:
        # cunningly make the query faster
        calendars = calendars.filter(id__in=calendar_ids)
        calendar_dates = calendar_dates.filter(calendar__in=calendar_ids)
    exclusions = calendar_dates.filter(operation=False)
    inclusions = calendar_dates.filter(operation=True)
    special_inclusions = inclusions.filter(special=True)
    only_certain_dates = Exists(CalendarDate.objects.filter(calendar=OuterRef('id'), special=False, operation=True))
    return calendars.filter(
        ~Q(calendardate__in=exclusions)
    ).filter(
        Q(~only_certain_dates) | Q(calendardate__in=inclusions)
    ).filter(
        Q(**{when.strftime('%a').lower(): True}) | Q(calendardate__in=special_inclusions)
    )


class Route(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    code = models.CharField(max_length=255)
    line_brand = models.CharField(max_length=255, blank=True)
    line_name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    dates = DateRangeField(null=True, blank=True)
    service = models.ForeignKey('busstops.Service', models.CASCADE)

    class Meta:
        unique_together = ('source', 'code')
        index_together = (
            ('start_date', 'end_date'),
        )

    def __str__(self):
        return ' – '.join(part for part in (self.line_name, self.line_brand, self.description) if part)

    def get_absolute_url(self):
        return reverse('route_xml', args=(self.source_id, self.code.split('#')[0]))


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
    dates = DateRangeField(null=True)

    class Meta:
        index_together = (
            ('start_date', 'end_date'),
        )

    def allows(self, date):
        if getattr(self, date.strftime('%a').lower()):
            for calendar_date in self.calendardate_set.all():
                if not calendar_date.operation and calendar_date.contains(date):
                    return False
            return True
        for calendar_date in self.calendardate_set.all():
            if calendar_date.operation and calendar_date.special and calendar_date.contains(date):
                return True

    def __str__(self):
        return f'{self.start_date} to {self.end_date}'


class CalendarDate(models.Model):
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    dates = DateRangeField(null=True)
    operation = models.BooleanField(db_index=True)
    special = models.BooleanField(default=False, db_index=True)

    def contains(self, date):
        return self.start_date <= date and (not self.end_date or self.end_date >= date)

    def __str__(self):
        if not self.operation:
            prefix = 'Not '
        elif self.special:
            prefix = 'Also '
        if self.start_date == self.end_date:
            return f'{prefix}{self.start_date}'
        return f'{prefix}{self.start_date} to {self.end_date}'


class Note(models.Model):
    code = models.CharField(max_length=16)
    text = models.CharField(max_length=255)

    def get_absolute_url(self):
        return self.trip_set.first().route.service.get_absolute_url()


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    destination = models.ForeignKey('busstops.StopPoint', models.SET_NULL, null=True, blank=True)
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    start = models.DurationField()
    end = models.DurationField()

    def __str__(self):
        return f'{self.start}'

    class Meta:
        index_together = (
            ('route', 'start', 'end'),
        )

    def __cmp__(a, b):
        """Compare two journeys"""
        if a.sequence is not None and a.sequence is not None:
            a_time = a.sequence
            b_time = b.sequence
        else:
            a_time = a.start
            b_time = b.start
            a_times = a.stoptime_set.all()
            b_times = b.stoptime_set.all()
            if a_times[0].get_key() != b_times[0].get_key():
                if a.destination_id == b.destination_id:
                    a_time = a.end
                    b_time = b.end
                else:
                    times = {time.get_key(): time.arrival or time.departure for time in a_times}
                    for time in b_times:
                        key = time.get_key()
                        if key in times:
                            a_time = times[key]
                            b_time = time.arrival or time.departure
                            break
        if a_time > b_time:
            return 1
        if a_time < b_time:
            return -1
        return 0

    def __repr__(self):
        return str(self.start)


class StopTime(models.Model):
    id = models.BigAutoField(primary_key=True)
    trip = models.ForeignKey(Trip, models.CASCADE)
    stop_code = models.CharField(max_length=255, blank=True)
    stop = models.ForeignKey('busstops.StopPoint', models.SET_NULL, null=True, blank=True)
    arrival = models.DurationField()
    departure = models.DurationField()
    sequence = models.PositiveSmallIntegerField()
    timing_status = models.CharField(max_length=3, blank=True)
    activity = models.CharField(max_length=16, blank=True)

    def get_key(self):
        return self.stop_id or self.stop_code

    class Meta:
        ordering = ('sequence',)
        index_together = (
            ('stop', 'departure'),
        )
