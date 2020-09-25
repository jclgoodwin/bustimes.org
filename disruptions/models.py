from django.db import models
from django.contrib.postgres.fields import DateTimeRangeField
from django.urls import reverse
from busstops.templatetags.date_range import date_range


class Situation(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    situation_number = models.CharField(max_length=36, blank=True)
    reason = models.CharField(max_length=25, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    text = models.TextField(blank=True)
    data = models.TextField(blank=True)
    created = models.DateTimeField()
    publication_window = DateTimeRangeField()
    current = models.BooleanField(default=True)

    def __str__(self):
        return self.summary

    def get_absolute_url(self):
        return reverse('situation', args=(self.id,))

    class Meta:
        unique_together = ('source', 'situation_number')


class Link(models.Model):
    url = models.URLField()
    situation = models.ForeignKey(Situation, models.CASCADE)

    def __str__(self):
        return self.url

    get_absolute_url = __str__


class ValidityPeriod(models.Model):
    situation = models.ForeignKey(Situation, models.CASCADE)
    period = DateTimeRangeField()

    def __str__(self):
        return date_range(self.period)


class Consequence(models.Model):
    situation = models.ForeignKey(Situation, models.CASCADE)
    stops = models.ManyToManyField('busstops.StopPoint', blank=True)
    services = models.ManyToManyField('busstops.Service', blank=True)
    operators = models.ManyToManyField('busstops.Operator', blank=True)
    text = models.TextField(blank=True)
    data = models.TextField(blank=True)

    def __str__(self):
        return self.text

    def get_absolute_url(self):
        service = self.services.first()
        if service:
            return service.get_absolute_url()
        return ''


class StopSuspension(models.Model):
    dates = DateTimeRangeField(null=True, blank=True)
    text = models.TextField(blank=True)
    stops = models.ManyToManyField('busstops.StopPoint')
    service = models.ForeignKey('busstops.Service', models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.text or str(self.dates)
