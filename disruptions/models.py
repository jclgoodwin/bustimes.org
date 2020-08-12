from django.db import models
from django.contrib.postgres.fields import DateTimeRangeField
from django.urls import reverse
from django.utils.timezone import localdate


class Situation(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    situation_number = models.CharField(max_length=36)
    reason = models.CharField(max_length=25)
    summary = models.CharField(max_length=255)
    text = models.TextField()
    data = models.TextField()
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
        lower = self.period.lower and localdate(self.period.lower)
        upper = self.period.upper and localdate(self.period.upper)
        if lower:
            if upper:
                if lower == upper:
                    return lower.strftime('%A %-d %B')
                return lower.strftime('%A %-d %B') + ' – ' + upper.strftime('%A %-d %B')
            return 'From ' + lower.strftime('%A %-d %B')
        if upper:
            return 'Until ' + upper.strftime('%A %-d %B')
        return ''


class Consequence(models.Model):
    situation = models.ForeignKey(Situation, models.CASCADE)
    stops = models.ManyToManyField('busstops.StopPoint')
    services = models.ManyToManyField('busstops.Service')
    operators = models.ManyToManyField('busstops.Operator')
    text = models.TextField()
    data = models.TextField()

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
