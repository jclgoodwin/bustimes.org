from django.db.models import Q, Exists, OuterRef
from django.contrib.gis.db import models
from django.urls import reverse
from .fields import SecondsField
from .utils import format_timedelta, time_datetime


def get_routes(routes, when):
    routes = [route for route in routes if route.contains(when)]

    if len(routes) == 1:
        return routes

    # use maximum revision number for each service_code
    revision_numbers = set(route.revision_number for route in routes)
    if len(revision_numbers) > 1:
        revision_numbers = {}
        for route in routes:
            if (
                route.service_code not in revision_numbers
                or route.revision_number > revision_numbers[route.service_code]
            ):
                revision_numbers[route.service_code] = route.revision_number
        routes = [route for route in routes if route.revision_number == revision_numbers[route.service_code]]

    sources = set(route.source_id for route in routes)

    # remove duplicates
    if len(sources) > 1 and all(route.source.name.startswith('First Bus') for route in routes):
        routes_by_service_code = {}
        for route in routes:
            routes_by_service_code[route.service_code] = route
        return list(routes_by_service_code.values())

    if len(sources) == 1:
        prefixes = set(route.code.split('.zip')[0] for route in routes if '.zip' in route.code)
        # use latest passenger zipfile filename
        if len(prefixes) > 1:
            latest_prefix = f'{max(prefixes)}.zip'
            routes = [route for route in routes if route.code.startswith(latest_prefix)]
        else:
            override_routes = [route for route in routes if route.start_date == route.end_date == when]
            if override_routes:  # e.g. Lynx BoxingDayHoliday
                routes = override_routes

    return routes


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


class CalendarBankHoliday(models.Model):
    operation = models.BooleanField()
    bank_holiday = models.ForeignKey(BankHoliday, models.CASCADE)
    calendar = models.ForeignKey('bustimes.Calendar', models.CASCADE)

    class Meta:
        unique_together = ('bank_holiday', 'calendar')


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
    summary = models.CharField(max_length=255, blank=True)
    bank_holidays = models.ManyToManyField(BankHoliday, through=CalendarBankHoliday)

    contains = Route.contains

    class Meta:
        index_together = (
            ('start_date', 'end_date'),
        )

    def is_sufficiently_simple(self, future):
        if self.summary or all(date.start_date > future for date in self.calendardate_set.all()):
            if str(self):
                return True
        return False

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
            days = f'{days[0]}s'
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
    operation = models.BooleanField(db_index=True)
    special = models.BooleanField(default=False, db_index=True)
    summary = models.CharField(max_length=255, blank=True)

    contains = Route.contains

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
    calendar = models.ForeignKey(Calendar, models.DO_NOTHING)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    start = SecondsField()
    end = SecondsField()
    garage = models.ForeignKey('Garage', models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey('VehicleType', models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return format_timedelta(self.start)

    def start_time(self):
        return format_timedelta(self.start)

    def end_time(self):
        return format_timedelta(self.end)

    def start_datetime(self, date):
        return time_datetime(self.start, date)

    def end_datetime(self, date):
        return time_datetime(self.end, date)

    class Meta:
        index_together = (
            ('route', 'start', 'end'),
        )

    def copy(self, start):
        difference = start - self.start
        new_trip = Trip.objects.get(id=self.id)
        times = list(new_trip.stoptime_set.all())
        new_trip.id = None
        new_trip.start += difference
        new_trip.end += difference
        new_trip.save()
        for stop_time in times:
            stop_time.id = None
            stop_time.arrival += difference
            stop_time.departure += difference
            stop_time.trip = new_trip
            stop_time.save()

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

    def arrival_or_departure(self):
        if self.arrival is not None:
            return self.arrival
        return self.departure

    def departure_or_arrival(self):
        if self.departure is not None:
            return self.departure
        return self.arrival

    def arrival_time(self):
        return format_timedelta(self.arrival)

    def arrival_datetime(self, date):
        return time_datetime(self.arrival, date)

    def departure_time(self):
        return format_timedelta(self.departure)

    def departure_datetime(self, date):
        return time_datetime(self.departure, date)

    def is_minor(self):
        return self.timing_status == 'OTH'


class Garage(models.Model):
    operator = models.ForeignKey('busstops.Operator', models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=100, blank=True)
    location = models.PointField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        if self.name:
            if self.name.isupper():
                return self.name.title()
            return self.name
        return self.code


class VehicleType(models.Model):
    code = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=100, blank=True)
