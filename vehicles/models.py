from math import ceil
from urllib.parse import quote
from webcolors import html5_parse_simple_color
from django.contrib.gis.db import models
from django.urls import reverse
from django.utils.safestring import mark_safe
from busstops.models import Operator, Service, DataSource, SIRISource


def get_css(colours, direction=None, horizontal=False):
    if len(colours) == 1:
        return colours[0]
    else:
        if direction is None:
            direction = 180
        background = 'linear-gradient('
        if horizontal:
            background += 'to top'
        elif direction < 180:
            background += 'to left'
        else:
            background += 'to right'
        percentage = 100 / len(colours)
        for i, colour in enumerate(colours):
            if i != 0:
                background += ',{} {}%'.format(colour, ceil(percentage * i))
            if i != len(colours) - 1 and colour != colours[i + 1]:
                background += ',{} {}%'.format(colour, ceil(percentage * (i + 1)))
        background += ')'

        return background


def get_brightness(colour):
    return (0.299 * colour.red + 0.587 * colour.green + 0.114 * colour.blue) / 255


class VehicleType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    double_decker = models.NullBooleanField()
    coach = models.NullBooleanField()

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Livery(models.Model):
    name = models.CharField(max_length=255, unique=True)
    colours = models.CharField(max_length=255, blank=True)
    css = models.CharField(max_length=255, blank=True)
    horizontal = models.BooleanField(default=False)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'liveries'

    def __str__(self):
        return self.name

    def preview(self):
        if not self.colours:
            return
        background = get_css(self.colours.split(), None, self.horizontal)
        return mark_safe('<div style="height:1.5em;width:4em;background:{}"></div>'.format(background))


class VehicleFeature(models.Model):
    name = models.CharField(max_length=255, unique=True)

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
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    latest_location = models.ForeignKey('VehicleLocation', models.SET_NULL, null=True, blank=True,
                                        related_name='latest_vehicle', editable=False)
    features = models.ManyToManyField(VehicleFeature, blank=True)

    class Meta:
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

    def get_text_colour(self):
        colours = self.livery and self.livery.colours or self.colours
        if colours:
            colours = colours.split()
            parsed_colours = [html5_parse_simple_color(colour) for colour in colours]
            brightness = sum(get_brightness(colour) for colour in parsed_colours) / len(colours)
            if brightness < .5:
                return '#fff'

    def get_livery(self, direction=None):
        colours = self.livery and self.livery.colours or self.colours
        if colours:
            colours = colours.split()
            return get_css(colours, direction, self.livery and self.livery.horizontal)

    def get_absolute_url(self):
        return reverse('vehicle_detail', args=(self.id,))

    def get_flickr_url(self):
        if self.reg:
            search = f'{self.reg} or "{self.get_reg()}"'
        else:
            search = self.code
        return f'https://www.flickr.com/search/?text={quote(search)}&sort=date-taken-desc'

    def get_flickr_link(self):
        return mark_safe(f'<a href="{self.get_flickr_url()}" target="_blank" rel="noopener">Flickr</a>')

    get_flickr_link.short_description = 'Flickr'


class VehicleJourney(models.Model):
    datetime = models.DateTimeField()
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    route_name = models.CharField(max_length=64, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ('id',)


class JourneyCode(models.Model):
    code = models.CharField(max_length=64, blank=True)
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    data_source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    siri_source = models.ForeignKey(SIRISource, models.SET_NULL, null=True, blank=True)
    destination = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('code', 'service', 'siri_source')


class VehicleLocation(models.Model):
    datetime = models.DateTimeField()
    latlong = models.PointField()
    journey = models.ForeignKey(VehicleJourney, models.CASCADE)
    heading = models.PositiveIntegerField(null=True, blank=True)
    early = models.IntegerField(null=True, blank=True)
    current = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ('id',)
        index_together = (
            ('current', 'datetime')
        )

    def get_json(self, extended=False):
        journey = self.journey
        vehicle = journey.vehicle
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
                    'text_colour': vehicle.get_text_colour(),
                    'livery': vehicle.get_livery(self.heading),
                    'notes': vehicle.notes
                },
                'delta': self.early,
                'direction': self.heading,
                'datetime': self.datetime,
                'destination': journey.destination,
                'source': journey.source_id
            }
        }
        if extended:
            if vehicle.vehicle_type:
                json['properties']['vehicle']['type'] = str(vehicle.vehicle_type)
            if journey.service:
                json['properties']['service'] = {
                    'line_name': journey.service.line_name,
                    'url': journey.service.get_absolute_url()
                }
            else:
                json['properties']['service'] = {
                    'line_name': journey.route_name
                }
            if vehicle.operator:
                json['properties']['operator'] = str(vehicle.operator)
        else:
            if vehicle.vehicle_type:
                json['properties']['vehicle']['coach'] = vehicle.vehicle_type.coach
                json['properties']['vehicle']['decker'] = vehicle.vehicle_type.double_decker
        return json
