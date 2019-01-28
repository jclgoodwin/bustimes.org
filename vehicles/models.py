from webcolors import html5_parse_simple_color
from django.contrib.gis.db import models
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
        if len(self.reg) > 3:
            reg = self.get_reg()
            if self.fleet_number:
                return '{} - {}'.format(self.fleet_number, reg)
            return reg
        if self.fleet_number:
            return str(self.fleet_number)
        return self.code.replace('_', ' ')

    def get_reg(self):
        if self.reg[-3:].isalpha():
            return self.reg[:-3] + ' ' + self.reg[-3:]
        if self.reg[:3].isalpha():
            return self.reg[:3] + ' ' + self.reg[3:]
        if self.reg[-2:].isalpha():
            return self.reg[:-2] + ' ' + self.reg[-2:]
        return self.reg

    def get_absolute_url(self):
        return reverse('vehicle_detail', args=(self.id,))


class VehicleJourney(models.Model):
    datetime = models.DateTimeField()
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)

    class Meta():
        ordering = ('id',)


class VehicleLocation(models.Model):
    datetime = models.DateTimeField()
    latlong = models.PointField()
    journey = models.ForeignKey(VehicleJourney, models.CASCADE)
    heading = models.PositiveIntegerField(null=True, blank=True)
    early = models.IntegerField(null=True, blank=True)
    current = models.BooleanField(default=False, db_index=True)

    class Meta():
        ordering = ('id',)
        index_together = (
            ('current', 'datetime')
        )

    def get_json(self, extended=False):
        journey = self.journey
        vehicle = journey.vehicle
        colours = vehicle.colours.split()
        text_colour = None
        if colours:
            parsed_colours = [html5_parse_simple_color(colour) for colour in colours]
            lightness = sum(c.red + c.blue + c.green for c in parsed_colours) / len(parsed_colours) / 3
            if lightness < 170:
                text_colour = '#fff'
        json = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': tuple(self.latlong),
            },
            'properties': {
                'vehicle': {
                    'url': vehicle.get_absolute_url(),
                    'name': str(vehicle),
                    'colours': colours,
                    'text_colour': text_colour
                },
                'delta': self.early,
                'direction': self.heading,
                'datetime': self.datetime,
                'destination': journey.destination
            }
        }
        if extended:
            if vehicle.vehicle_type:
                json['properties']['vehicle']['type'] = str(vehicle.vehicle_type)
            if journey.service:
                json['properties']['service'] = {
                    'line_name': journey.service.line_name,
                    'url': journey.service.get_absolute_url(),
                }
            if vehicle.operator:
                json['properties']['operator'] = str(vehicle.operator)
        return json
