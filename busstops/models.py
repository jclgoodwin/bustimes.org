from django.contrib.gis.db import models
from django.core.urlresolvers import reverse


class Region(models.Model):
    "The largest type of geographical area."
    id = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=48)

    def __unicode__(self):
        return self.name

    def the(self):
        "The name for use in a sentence, with the definite article prepended if appropriate."
        if self.name[-1:] == 't' or self.name[-2:] == 'ds':
            return 'the ' + self.name
        else:
            return self.name

    def get_absolute_url(self):
        return reverse('region-detail', args=(self.id,))


class AdminArea(models.Model):
    """
    An administrative area within a region,
    or possibly a national transport (rail/air/ferry) network.
    """
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
    """
    A district within an administrative area.

    Note: some administrative areas *do not* have districts.
    """
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('district-detail', args=(self.id,))


class Locality(models.Model):
    """
    A locality within an administrative area, and possibly within a district.

    Localities may be children of other localities...
    """
    id = models.CharField(max_length=48, primary_key=True)
    name = models.CharField(max_length=48)
    # short_name? 
    qualifier_name = models.CharField(max_length=48, blank=True)
    admin_area = models.ForeignKey(AdminArea)
    district = models.ForeignKey(District, null=True)
    parent = models.ForeignKey('Locality', null=True)
    easting = models.PositiveIntegerField()
    northing = models.PositiveIntegerField()

    def __unicode__(self):
        return self.name # TODO qualifier name?

    def get_absolute_url(self):
        return reverse('locality-detail', args=(self.id,))


class StopArea(models.Model):
    id = models.CharField(max_length=16, primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea)

    TYPE_CHOICES = (
        ('GPBS', 'on-street pair'),
        ('GCLS', 'on-street cluster'),
        ('GAIR', 'airport building'),
        ('GBCS', 'bus/coach station'),
        ('GFTD', 'ferry terminal/dock'),
        ('GTMU', 'tram/metro station'),
        ('GRLS', 'rail station'),
        ('GCCH', 'coach service coverage'),
    )
    stop_area_type = models.CharField(max_length=4, choices=TYPE_CHOICES)

    parent = models.ForeignKey('StopArea', null=True, editable=False)
    location = models.PointField(srid=27700)
    active = models.BooleanField()

    def __unicode__(self):
        return self.name


class StopPoint(models.Model):
    "The smallest type of geographical point; a point at which vehicles stop."
    atco_code = models.CharField(max_length=16, primary_key=True)
    naptan_code = models.CharField(max_length=16)

    common_name = models.CharField(max_length=48)
    landmark = models.CharField(max_length=48)
    street = models.CharField(max_length=48)
    crossing = models.CharField(max_length=48)
    indicator = models.CharField(max_length=48)

    latlong = models.PointField()
    objects = models.GeoManager()

    stop_area = models.ForeignKey(StopArea, null=True)
    locality = models.ForeignKey('Locality', editable=False)
    suburb = models.CharField(max_length=48)
    town = models.CharField(max_length=48) 
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
        if self.indicator:
            return "%s (%s)" % (self.common_name, self.indicator)
        return self.common_name

    def heading(self):
        "Return the stop's bearing converted to degrees, for use with Google Street View."
        headings = {
            'N':    0,
            'NE':  45,
            'E':   90,
            'SE': 135,
            'S':  180,
            'SW': 125,
            'W':  270,
            'NW': 315,
        }
        return headings.get(self.bearing)

    def get_absolute_url(self):
        return reverse('stoppoint-detail', args=(self.atco_code,))


class Operator(models.Model):
    "An entity that operates public transport services."
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
        Return the the name of the operator's vehicle mode, with the correct indefinite article
        depending on whether it begins with a vowel sound.

        'Airline' becomes 'An airline', 'Bus' becomes 'A bus'.

        Doesn't support modes that begin with other vowels, because there aren't any (unimog? 'overcraft?).
        """
        mode = str(self.vehicle_mode).lower()
        if mode:
            if mode[0] == 'a':
                return 'An ' + mode
            return 'A ' + mode
        return 'A public transport'


class Service(models.Model):
    "A bus service."
    service_code = models.CharField(max_length=24, primary_key=True)
    operator = models.ForeignKey('Operator')
    stops = models.ManyToManyField(StopPoint, editable=False)

    def __unicode__(self):
        example_version = ServiceVersion.objects.filter(service=self).first()
        if example_version is not None:
            return example_version.line_name + ' - ' + example_version.description
        else:
            return self.service_code

    def get_absolute_url(self):
        return reverse('service-detail', args=(self.service_code,))


class ServiceVersion(models.Model):
    """
    A "version" of a service, usually represented as a separate file in a region's TNDS zip archive.

    There are usually at least two versions of a service, one per direction of travel.
    Further "versions" exist when services are revised.
    """
    name = models.CharField(max_length=24, primary_key=True) # e.g. 'YEABCL1-2015-04-10-1'
    line_name = models.CharField(max_length=10)
    service = models.ForeignKey(Service, editable=False)
    mode = models.CharField(max_length=10)
    description = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(null=True)

    def __unicode__(self):
        return self.line_name + ' ' + self.description

