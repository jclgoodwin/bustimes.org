# from django.db import models
from django.contrib.gis.db import models
from geoposition.fields import GeopositionField
from django.core.urlresolvers import reverse


class StopPoint(models.Model):

    atco_code   = models.CharField(max_length=16, primary_key=True)
    naptan_code = models.CharField(max_length=16)

    common_name = models.CharField(max_length=48)
    landmark    = models.CharField(max_length=48)
    street      = models.CharField(max_length=48)
    crossing    = models.CharField(max_length=48)
    indicator   = models.CharField(max_length=48)

    latlong = models.PointField()
    objects = models.GeoManager()

    locality = models.ForeignKey('Locality', editable=False)
    suburb = models.CharField(max_length=48)
    town   = models.CharField(max_length=48) 
    locality_centre = models.BooleanField()

    BEARING_CHOICES = (
        ('N', 'north'),
        ('NE', 'north east'),
        ('E', 'east'),
        ('SE', 'south east'),
        ('S', 'south'),
        ('SW', 'south west'),
        ('W', 'west'),
        ('NW', 'north west')
    )
    bearing = models.CharField(max_length=2, choices=BEARING_CHOICES)

    stop_type = models.CharField(max_length=3)
    bus_stop_type = models.CharField(max_length=3)
    timing_status = models.CharField(max_length=3)
    admin_area = models.ForeignKey('AdminArea')
    active = models.BooleanField()

    def __unicode__(self):
        if not self.indicator or self.indicator == '---':
            return self.common_name
        else:
            return "%s (%s)" % (self.common_name, self.indicator)

    def heading(self):
        if self.bearing == 'N':
            return 0
        elif self.bearing == 'NE':
            return 45
        elif self.bearing == 'E':
            return 90
        elif self.bearing == 'SE':
            return 135
        elif self.bearing == 'S':
            return 180
        elif self.bearing == 'SW':
            return 125
        elif self.bearing == 'W':
            return 270
        elif self.bearing == 'NW':
            return 315

    def get_absolute_url(self):
        return reverse('stoppoint-detail', args=(self.atco_code,))


class Region(models.Model):
    id = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=48)

    def __unicode__(self):
        return self.name

    def the(self):
        """
        The name for use in a sentence, with the definite article prepended if neccessary.
        E.g. "the East Midlands" (with "the"), or "Scotland" (no need for "the")

        """
        if self.name[-1:] == 't' or self.name[-2:] == 'ds':
            return 'the ' + self.name
        else:
            return self

    def get_absolute_url(self):
        return reverse('region-detail', args=(self.id,))


class AdminArea(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    atco_code = models.PositiveIntegerField()
    name = models.CharField(max_length=48)
    short_name = models.CharField(max_length=48)
    country = models.CharField(max_length=3)
    region = models.ForeignKey(Region)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('adminarea-detail', args=(self.id,))


class District(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('district-detail', args=(self.id,))


class Locality(models.Model):
    id = models.CharField(max_length=48, primary_key=True)
    name = models.CharField(max_length=48)
    # short_name? 
    qualifier_name = models.CharField(max_length=48, blank=True)
    admin_area = models.ForeignKey(AdminArea)
    district = models.ForeignKey(District, null=True)
    easting = models.PositiveIntegerField()
    northing = models.PositiveIntegerField()

    def __unicode__(self):
        return self.name # TODO qualifier name?

    def get_absolute_url(self):
        return reverse('locality-detail', args=(self.id,))


class Operator(models.Model):
    id = models.CharField(max_length=10, primary_key=True) # e.g. 'YCST'
    short_name = models.CharField(max_length=48)
    public_name = models.CharField(max_length=100)
    reference_name = models.CharField(max_length=100)
    license_name = models.CharField(max_length=100)
    vehicle_mode = models.CharField(max_length=48)
    parent = models.CharField(max_length=48)
    region = models.ForeignKey(Region)

    def __unicode__(self):
        return self.public_name

    def get_absolute_url(self):
        return reverse('operator-detail', args=(self.id,))

    def a_mode(self):
        """
        'Airline' becomes 'An airline', 'Bus' becomes 'A bus'

        Doesn't support modes that begin with other vowels, because there aren't any (unimog? 'overcraft?)
        """
        mode = self.vehicle_mode.lower()
        if mode[0] == 'a':
            return 'An ' + mode
        return 'A ' + mode

class Service(models.Model):
    service_code = models.CharField(max_length=24, primary_key=True)
    operator = models.ForeignKey('Operator')
    stops = models.ManyToManyField(StopPoint)

    def __unicode__(self):
        example_version = ServiceVersion.objects.filter(service=self).first()
        if example_version is not None:
            return example_version.line_name + ' - ' + example_version.description
        else:
            return self.service_code

    def get_absolute_url(self):
        return reverse('service-detail', args=(self.service_code,))


class ServiceVersion(models.Model):
    name = models.CharField(max_length=24, primary_key=True) # e.g. 'YEABCL1-2015-04-10-1'
    line_name = models.CharField(max_length=10)
    service = models.ForeignKey(Service, editable=False)
    mode = models.CharField(max_length=10)
    description = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True)

    def __unicode__(self):
        return self.line_name + ' ' + self.description

