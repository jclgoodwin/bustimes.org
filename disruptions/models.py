from django.db import models
# from django.contrib.postgres.fields import DateRangeField
from django.urls import reverse
# from busstops.models import DataSource Operator, Service, StopPoint


class Mode(models.Model):
    name = models.CharField(max_length=24)

    def __str__(self):
        return self.name


class Disruption(models.Model):
    source = models.ForeignKey('busstops.DataSource', models.CASCADE)
    stops = models.ManyToManyField('busstops.StopPoint')
    services = models.ManyToManyField('busstops.Service')
    operator = models.ManyToManyField('busstops.Operator')
    text = models.TextField()
    # data = models.TextField()
    # created = models.DateTimeField()
    # publication = DateRangeField()
    # validity = DateRangeField()

    def get_absolute_url(self):
        return reverse('disruption', args=(self.id,))
