from django.db.models import Q, Exists, OuterRef
from django.contrib.gis.db import models
from django.contrib.postgres.fields import DateRangeField
from django.urls import reverse
from .fields import SecondsField
from .utils import format_timedelta


def get_routes(routes, when):
    if any(route.revision_number for route in routes):
        routes = [route for route in routes if route.contains(when)]
        revision_numbers = set(route.revision_number or 0 for route in routes)
        if len(revision_numbers) > 1:
            max_revision_number = max(revision_numbers)
            if max_revision_number:
                routes = [route for route in routes if route.revision_number == max_revision_number]
        elif all('/first/' in route.source.url for route in routes):
            start_dates = set(route.start_date for route in routes)
            if start_dates:
                max_start_date = max(start_dates)
                routes = [route for route in routes if route.start_date == max_start_date]
    else:
        override_routes = [route for route in routes if route.start_date == route.end_date == when]
        if override_routes:  # e.g. Lynx BoxingDayHoliday
            routes = override_routes
    return list(routes)


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
    code = models.CharField(max_length=255)  # qualified filename
    service_code = models.CharField(max_length=255, blank=True)
    registration = models.ForeignKey('vosa.Registration', models.SET_NULL, null=True, blank=True)
    line_brand = models.CharField(max_length=255, blank=True)
    line_name = models.CharField(max_length=255, blank=True)
    revision_number = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    origin = models.CharField(max_length=255, blank=True)
    destinaton = models.CharField(max_length=255, blank=True)
    via = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    dates = DateRangeField(null=True, blank=True)
    service = models.ForeignKey('busstops.Service', models.CASCADE)
    geometry = models.MultiLineStringField(null=True, blank=True, editable=False)

    def contains(self, date):
        if not self.start_date or self.start_date <= date:
            if not self.end_date or self.end_date >= date:
                return True

    class Meta:
        unique_together = ('source', 'code')
        index_together = (
            ('start_date', 'end_date'),
        )

    def __str__(self):
        return ' – '.join(part for part in (self.line_name, self.line_brand, self.description) if part)

    def get_absolute_url(self):
        return reverse('route_xml', args=(self.source_id, self.code.split('#')[0]))


class BankHoliday(models.Model):
    name = models.CharField(unique=True, max_length=255)


class BankHolidayDate(models.Model):
    bank_holiday = models.ForeignKey(BankHoliday, models.CASCADE)
    date = models.DateField()
    scotland = models.BooleanField(null=True)


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
    summary = models.CharField(max_length=255, blank=True)

    contains = Route.contains

    class Meta:
        index_together = (
            ('start_date', 'end_date'),
        )

    def allows(self, date):
        if not self.contains(date):
            return False

        if getattr(self, date.strftime('%a').lower()):
            for calendar_date in self.calendardate_set.all():
                if not calendar_date.operation and calendar_date.contains(date):
                    return False
            return True

        for calendar_date in self.calendardate_set.all():
            if calendar_date.operation and calendar_date.special and calendar_date.contains(date):
                return True

    def __str__(self):
        day_keys = (
            'Monday',
            'Tuesday',
            'Wednesday',
            'Thursday',
            'Friday',
            'Saturday',
            'Sunday',
        )
        day_values = (self.mon, self.tue, self.wed, self.thu, self.fri, self.sat, self.sun)
        days = [day_keys[i] for i, value in enumerate(day_values) if value]
        if not days:
            return self.summary
        if len(days) == 1:
            days = f'{days[0]}s only'
        elif days[0] == 'Monday' and days[-1] == day_keys[len(days)-1]:
            days = f'{days[0]} to {days[-1]}'
        else:
            days = f"{'s, '.join(days[:-1])}s and {days[-1]}s"

        if self.summary:
            return f'{days}, {self.summary}'

        return days


class CalendarDate(models.Model):
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    dates = DateRangeField(null=True)
    operation = models.BooleanField(db_index=True)
    special = models.BooleanField(default=False, db_index=True)
    summary = models.CharField(max_length=255, blank=True)

    contains = Route.contains

    def relevant(self, operating_period):
        if self.end_date:
            if self.end_date < self.start_date:
                return False
            if operating_period.start > self.end_date:
                return False
        if operating_period.end and operating_period.end < self.start_date:
            return False
        return True

    def __str__(self):
        string = str(self.start_date)
        if self.end_date != self.start_date:
            string = f'{string}–{self.end_date}'
        if not self.operation:
            string = f'not {string}'
        if self.special:
            string = f'also {string}'
        if self.summary:
            string = f'{string} ({self.summary})'
        return string


class Note(models.Model):
    code = models.CharField(max_length=16)
    text = models.CharField(max_length=255)

    def get_absolute_url(self):
        return self.trip_set.first().route.service.get_absolute_url()


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    ticket_machine_code = models.CharField(max_length=255, blank=True, db_index=True)
    block = models.CharField(max_length=255, blank=True, db_index=True)
    destination = models.ForeignKey('busstops.StopPoint', models.SET_NULL, null=True, blank=True)
    calendar = models.ForeignKey(Calendar, models.CASCADE)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    start = SecondsField()
    end = SecondsField()

    def __str__(self):
        return format_timedelta(self.start)

    def start_time(self):
        return format_timedelta(self.start)

    def end_time(self):
        return format_timedelta(self.end)

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
            if a_times and b_times and a_times[0].get_key() != b_times[0].get_key():
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

    def copy(self, start):
        difference = start - self.start
        new_trip = Trip.objects.get(id=self.id)
        times = list(new_trip.stoptime_set.all())
        new_trip.id = None
        new_trip.start += difference
        new_trip.end += difference
        new_trip.save()
        for time in times:
            time.id = None
            time.arrival += difference
            time.departure += difference
            time.trip = new_trip
            time.save()

    def __repr__(self):
        return str(self.start)

    def get_absolute_url(self):
        return reverse('trip_detail', args=(self.id,))


class StopTime(models.Model):
    id = models.BigAutoField(primary_key=True)
    trip = models.ForeignKey(Trip, models.CASCADE)
    stop_code = models.CharField(max_length=255, blank=True)
    stop = models.ForeignKey('busstops.StopPoint', models.SET_NULL, null=True, blank=True)
    arrival = SecondsField(null=True, blank=True)
    departure = SecondsField(null=True, blank=True)
    sequence = models.PositiveSmallIntegerField()
    timing_status = models.CharField(max_length=3, blank=True)
    activity = models.CharField(max_length=16, blank=True)
    pick_up = models.BooleanField(default=True)
    set_down = models.BooleanField(default=True)

    def get_key(self):
        return self.stop_id or self.stop_code

    class Meta:
        ordering = ('sequence',)
        index_together = (
            ('stop', 'departure'),
        )

    def arrival_time(self):
        return format_timedelta(self.arrival)

    def departure_time(self):
        return format_timedelta(self.departure)

    def is_minor(self):
        return self.timing_status == 'OTH' or self.timing_status == 'TIP'
