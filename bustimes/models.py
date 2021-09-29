from django.contrib.gis.db import models
from django.db.models.functions import Upper
from django.urls import reverse
from .fields import SecondsField
from .formatting import format_timedelta, time_datetime


class Route(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    code = models.CharField(max_length=255, blank=True)  # qualified filename
    service_code = models.CharField(max_length=255, blank=True)
    registration = models.ForeignKey('vosa.Registration', models.SET_NULL, null=True, blank=True)
    line_brand = models.CharField(max_length=255, blank=True)
    line_name = models.CharField(max_length=255, blank=True)
    revision_number = models.PositiveIntegerField(null=True, blank=True)
    description = models.CharField(max_length=255, blank=True)
    outbound_description = models.CharField(max_length=255, blank=True)
    inbound_description = models.CharField(max_length=255, blank=True)
    origin = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    via = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    service = models.ForeignKey('busstops.Service', models.CASCADE)
    public_use = models.BooleanField(null=True)

    def contains(self, date):
        if not self.start_date or self.start_date <= date:
            if not self.end_date or self.end_date >= date:
                return True

    class Meta:
        unique_together = ('source', 'code')
        index_together = (
            ('start_date', 'end_date'),
        )
        indexes = [
            models.Index(Upper('line_name'), name='route_line_name'),
        ]

    def __str__(self):
        return ' – '.join(part for part in (self.line_name, self.line_brand, self.description) if part)

    def get_absolute_url(self):
        return reverse('route_xml', args=(self.source_id, self.code.split('#')[0]))


class RouteLink(models.Model):
    service = models.ForeignKey('busstops.Service', models.CASCADE)
    from_stop = models.ForeignKey('busstops.StopPoint', models.CASCADE, related_name='link_from')
    to_stop = models.ForeignKey('busstops.StopPoint', models.CASCADE, related_name='link_to')
    distance_metres = models.PositiveSmallIntegerField(null=True, blank=True)
    geometry = models.LineStringField()
    override = models.BooleanField(default=False)


class BankHoliday(models.Model):
    id = models.SmallAutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=255)

    def __str__(self):
        return self.name


class BankHolidayDate(models.Model):
    bank_holiday = models.ForeignKey(BankHoliday, models.CASCADE)
    date = models.DateField()
    scotland = models.BooleanField(null=True, help_text="Yes = Scotland only, No = not Scotland, Unknown = both")


class CalendarBankHoliday(models.Model):
    operation = models.BooleanField()
    bank_holiday = models.ForeignKey(BankHoliday, models.CASCADE)
    calendar = models.ForeignKey('bustimes.Calendar', models.CASCADE)

    class Meta:
        unique_together = ('bank_holiday', 'calendar')

    def __str__(self):
        if self.operation:
            return str(self.bank_holiday)
        return f'not {self.bank_holiday}'


day_keys = (
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
)


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

        # for date in self.bank_holiday_exclsions:
        if date in self.bank_holiday_dates:
            return True

    def get_days(self):
        day_values = (self.mon, self.tue, self.wed, self.thu, self.fri, self.sat, self.sun)
        return [day_keys[i] for i, value in enumerate(day_values) if value]

    def get_order(self):
        return [day_keys.index(day) for day in self.get_days()]

    def __str__(self):
        days = self.get_days()
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
        return self.trip_set.first().get_absolute_url()


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    ticket_machine_code = models.CharField(max_length=255, blank=True, db_index=True)
    block = models.ForeignKey('Block', models.SET_NULL, null=True, blank=True)
    destination = models.ForeignKey('busstops.StopPoint', models.SET_NULL, null=True, blank=True)
    calendar = models.ForeignKey(Calendar, models.DO_NOTHING, null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.ManyToManyField(Note, blank=True)
    start = SecondsField()
    end = SecondsField()
    garage = models.ForeignKey('Garage', models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey('VehicleType', models.SET_NULL, null=True, blank=True)
    operator = models.ForeignKey('busstops.Operator', models.SET_NULL, null=True, blank=True)

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
            if stop_time.arrival is not None:
                stop_time.arrival += difference
            if stop_time.departure is not None:
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
    sequence = models.PositiveSmallIntegerField(null=True, blank=True)
    timing_status = models.CharField(max_length=3, blank=True)
    pick_up = models.BooleanField(default=True)
    set_down = models.BooleanField(default=True)

    def get_key(self):
        return self.stop_id or self.stop_code

    class Meta:
        ordering = ('id',)
        index_together = (
            ('stop', 'departure'),
        )

    def __str__(self):
        return format_timedelta(self.arrival_or_departure())

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


class Block(models.Model):
    code = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.code

    def get_absolute_url(self):
        return reverse('block_detail', args=(self.id,))


class Garage(models.Model):
    operator = models.ForeignKey('busstops.Operator', models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=100, blank=True)
    location = models.PointField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        if self.name != self.code:
            if self.name.isupper():
                return self.name.title()
            return self.name
        return self.code


class VehicleType(models.Model):
    code = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.code
