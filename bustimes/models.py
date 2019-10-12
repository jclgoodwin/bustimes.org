from django.contrib.gis.db import models
from django.urls import reverse


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

    def get_absolute_url(self):
        return reverse('route_detail', args=(self.id,))


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


class Trip(models.Model):
    route = models.ForeignKey(Route, models.CASCADE)
    inbound = models.BooleanField(default=False)
    journey_pattern = models.CharField(max_length=255, blank=True)
    destination = models.ForeignKey('busstops.StopPoint', models.CASCADE)
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
        index_together = (
            ('stop_code', 'departure'),
        )
