from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.urls import reverse
from busstops.models import Operator, Service, DataSource


class VehicleType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    double_decker = models.NullBooleanField()
    coach = models.NullBooleanField()

    class Meta():
        ordering = ('name',)

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    code = models.CharField(max_length=255)
    fleet_number = models.PositiveIntegerField(null=True, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE, null=True, blank=True)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey(VehicleType, models.SET_NULL, null=True, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    latest_location = models.ForeignKey('VehicleLocation', models.SET_NULL, null=True, blank=True,
                                        related_name='latest_vehicle', editable=False)

    class Meta():
        unique_together = ('code', 'operator')

    def __str__(self):
        return self.code.replace('_', ' ')

    def get_absolute_url(self):
        return reverse('vehicle_detail', args=(self.id,))


class VehicleJourney(models.Model):
    datetime = models.DateTimeField()
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, models.SET_NULL, null=True, blank=True)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)


class VehicleLocation(models.Model):
    data = JSONField(null=True, blank=True)
    datetime = models.DateTimeField()
    latlong = models.PointField()
    journey = models.ForeignKey(VehicleJourney, models.CASCADE)
    heading = models.PositiveIntegerField(null=True, blank=True)
    early = models.IntegerField(null=True, blank=True)
    current = models.BooleanField(default=False, db_index=True)

    class Meta():
        ordering = ('id',)
