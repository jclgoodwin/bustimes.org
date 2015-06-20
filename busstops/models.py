from django.db import models
from geoposition.fields import GeopositionField


class StopPoint(models.Model):

    atco_code   = models.CharField(max_length=16, primary_key=True)
    naptan_code = models.CharField(max_length=16)

    common_name = models.CharField(max_length=48)
    landmark    = models.CharField(max_length=48)
    street      = models.CharField(max_length=48)
    crossing    = models.CharField(max_length=48)
    indicator   = models.CharField(max_length=48)

    location = GeopositionField()
    locality = models.ForeignKey('Locality')
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
        from django.core.urlresolvers import reverse
        return reverse('stoppoint-detail', args=(self.atco_code,))


class Region(models.Model):
    id = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=48)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        from django.core.urlresolvers import reverse
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
        from django.core.urlresolvers import reverse
        return reverse('adminarea-detail', args=(self.id,))


class District(models.Model):
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        from django.core.urlresolvers import reverse
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
        from django.core.urlresolvers import reverse
        return reverse('locality-detail', args=(self.id,))


