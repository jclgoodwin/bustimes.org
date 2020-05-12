from django.db import models
from django.contrib.postgres.fields import DateTimeRangeField
from django.urls import reverse
# from busstops.models import DataSource Operator, Service, StopPoint


# class Mode(models.Model):
#     name = models.CharField(max_length=24)

#     def __str__(self):
#         return self.name


class Situation(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    situation_number = models.CharField(max_length=36)
    stops = models.ManyToManyField('busstops.StopPoint')
    services = models.ManyToManyField('busstops.Service')
    operator = models.ManyToManyField('busstops.Operator')
    summary = models.CharField(max_length=255)
    reason = models.CharField(max_length=25)
    text = models.TextField()
    data = models.TextField()
    created = models.DateTimeField()
    publication_window = DateTimeRangeField()
    validity_period = DateTimeRangeField()

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
