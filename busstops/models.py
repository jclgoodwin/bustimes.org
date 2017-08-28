"Model definitions"

from __future__ import unicode_literals
import re
try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode
from autoslug import AutoSlugField
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.postgres.fields import JSONField
from django.urls import reverse
from django.utils.encoding import python_2_unicode_compatible
from .utils import sign_url


TIMING_STATUS_CHOICES = (
    ('PPT', 'Principal point'),
    ('TIP', 'Time info point'),
    ('PTP', 'Principal and time info point'),
    ('OTH', 'Other bus stop'),
)
SERVICE_ORDER_REGEX = re.compile(r'(\D*)(\d*)(\D*)')


class ValidateOnSaveMixin(object):
    """https://www.xormedia.com/django-model-validation-on-save/"""
    def save(self, force_insert=False, force_update=False, **kwargs):
        if not (force_insert or force_update):
            self.full_clean()
        super(ValidateOnSaveMixin, self).save(force_insert, force_update, **kwargs)


@python_2_unicode_compatible
class Region(models.Model):
    """The largest type of geographical area"""
    id = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=48)

    def __str__(self):
        return self.name

    def the(self):
        """Return the name for use in a sentence,
        with the definite article prepended if appropriate"""
        if self.name[-2:] in ('ds', 'st'):
            return 'the ' + self.name
        else:
            return self.name

    def get_absolute_url(self):
        return reverse('region-detail', args=(self.id,))


@python_2_unicode_compatible
class AdminArea(models.Model):
    """An administrative area within a region,
    or possibly a national transport (rail/air/ferry) network
    """
    id = models.PositiveIntegerField(primary_key=True)
    atco_code = models.PositiveIntegerField()
    name = models.CharField(max_length=48)
    short_name = models.CharField(max_length=48, blank=True)
    country = models.CharField(max_length=3, blank=True)
    region = models.ForeignKey(Region, models.CASCADE)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('adminarea-detail', args=(self.id,))


@python_2_unicode_compatible
class District(models.Model):
    """A district within an administrative area.
    Note: some administrative areas *do not* have districts.
    """
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('district-detail', args=(self.id,))


@python_2_unicode_compatible
class Locality(models.Model):
    """A locality within an administrative area,
    and possibly within a district.

    Localities may be children of other localities...
    """
    id = models.CharField(max_length=48, primary_key=True)
    name = models.CharField(max_length=48)
    slug = AutoSlugField(populate_from='name', editable=True, blank=True)
    # short_name?
    qualifier_name = models.CharField(max_length=48, blank=True)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)
    district = models.ForeignKey(District, models.SET_NULL, null=True, blank=True)
    parent = models.ForeignKey('Locality', models.SET_NULL, null=True, editable=False)
    latlong = models.PointField(null=True)
    adjacent = models.ManyToManyField('Locality', related_name='neighbour', blank=True)

    def __str__(self):
        return self.name

    def get_qualified_name(self):
        """Return the name and qualifier (e.g. 'Reepham, Lincs')"""
        if self.qualifier_name:
            return "%s, %s" % (self.name, self.qualifier_name)
        return self.name

    def get_absolute_url(self):
        return reverse('locality-detail', args=(self.id,))


@python_2_unicode_compatible
class StopArea(models.Model):
    """A small area containing multiple stops, such as a bus station"""

    id = models.CharField(max_length=16, primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)

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

    parent = models.ForeignKey('StopArea', models.SET_NULL, null=True, editable=False)
    latlong = models.PointField(null=True)
    active = models.BooleanField()

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class LiveSource(models.Model):
    """A source of live departure information for a stop point"""
    name = models.CharField(max_length=4, primary_key=True)

    def __str__(self):
        if self.name == 'Y':
            return 'Yorkshire'
        if self.name == 'TfL':
            return 'Transport for London'
        return self.name


@python_2_unicode_compatible
class StopPoint(models.Model):
    """The smallest type of geographical point.
    A point at which vehicles stop"""
    atco_code = models.CharField(max_length=16, primary_key=True)
    naptan_code = models.CharField(max_length=16, db_index=True)

    common_name = models.CharField(max_length=48)
    landmark = models.CharField(max_length=48, blank=True)
    street = models.CharField(max_length=48, blank=True)
    crossing = models.CharField(max_length=48, blank=True)
    indicator = models.CharField(max_length=48, blank=True)

    latlong = models.PointField(null=True)

    stop_area = models.ForeignKey(StopArea, models.SET_NULL, null=True, editable=False)
    locality = models.ForeignKey('Locality', models.SET_NULL, null=True, editable=False)
    suburb = models.CharField(max_length=48, blank=True)
    town = models.CharField(max_length=48, blank=True)
    locality_centre = models.BooleanField()

    live_sources = models.ManyToManyField(LiveSource, blank=True)

    heading = models.PositiveIntegerField(null=True, blank=True)

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
    bearing = models.CharField(max_length=2, choices=BEARING_CHOICES, blank=True)

    STOP_TYPE_CHOICES = (
        ('AIR', 'Airport entrance'),
        ('GAT', 'Air airside area'),
        ('FTD', 'Ferry terminal/dock entrance'),
        ('FER', 'Ferry/dock berth area'),
        ('FBT', 'Ferry berth'),  # ?
        ('RSE', 'Rail station entrance'),
        ('RLY', 'Rail platform access area'),
        ('RPL', 'Rail platform'),  # ?
        ('TMU', 'Tram/metro/underground entrance'),
        ('MET', 'MET'),  # ?
        ('PLT', 'Metro and underground platform access area'),
        ('BCE', 'Bus/coach station entrance'),
        ('BCS', 'Bus/coach bay/stand/stance within bus/coach station'),
        ('BCQ', 'Bus/coach bay'),  # ?
        ('BCT', 'On street bus/coach/tram stop'),
        ('TXR', 'Taxi rank (head of)'),
        ('STR', 'Shared taxi rank (head of)'),
    )
    stop_type = models.CharField(max_length=3, choices=STOP_TYPE_CHOICES)

    BUS_STOP_TYPE_CHOICES = (
        ('MKD', 'Marked (pole, shelter etc)'),
        ('HAR', 'Hail and ride'),
        ('CUS', 'Custom (unmarked, or only marked on road)'),
        ('FLX', 'Flexible zone'),
    )
    bus_stop_type = models.CharField(max_length=3, choices=BUS_STOP_TYPE_CHOICES, blank=True)

    timing_status = models.CharField(max_length=3, choices=TIMING_STATUS_CHOICES, blank=True)

    admin_area = models.ForeignKey('AdminArea', models.SET_NULL, null=True)
    active = models.BooleanField(db_index=True)

    osm = JSONField(null=True)

    def __str__(self):
        if self.indicator:
            return '%s (%s)' % (self.common_name, self.indicator)
        return self.common_name

    def get_heading(self):
        """Return the stop's bearing converted to degrees, for use with Google Street View."""
        if self.heading:
            return self.heading
        headings = {
            'N': 0,
            'NE': 45,
            'E': 90,
            'SE': 135,
            'S': 180,
            'SW': 225,
            'W': 270,
            'NW': 315,
        }
        return headings.get(self.bearing)

    def get_qualified_name(self):
        if self.locality:
            locality_name = str(self.locality).replace(' Town Centre', '').replace(' City Centre', '')
            if self.common_name in locality_name:
                return str(self.locality)  # Cardiff Airport
            if locality_name.replace('\'', '').replace('\u2019', '') not in self.common_name.replace('\'', ''):
                if self.indicator in ('opp', 'adj', 'at', 'o/s', 'nr', 'before', 'after', 'by', 'on', 'in'):
                    return '%s, %s %s' % (locality_name, self.indicator, self.common_name)
                else:
                    return '%s %s' % (locality_name, self)
        elif self.town not in self.common_name:
            return '{} {}'.format(self.town, self)
        return str(self)

    def get_streetview_url(self):
        if self.latlong:
            url = 'https://maps.googleapis.com/maps/api/streetview?%s' % urlencode(
                (
                    ('size', '480x360'),
                    ('location', '%s,%s' % (self.latlong.y, self.latlong.x)),
                    ('heading', self.get_heading()),
                    ('key', settings.STREETVIEW_KEY)
                )
            )
            if settings.STREETVIEW_SECRET:
                return sign_url(url, settings.STREETVIEW_SECRET)
            return url

    def get_region(self):
        if self.admin_area_id:
            return self.admin_area.region
        return Region.objects.filter(service__stops=self).first()

    def get_absolute_url(self):
        return reverse('stoppoint-detail', args=(self.atco_code,))


@python_2_unicode_compatible
class Operator(ValidateOnSaveMixin, models.Model):
    """An entity that operates public transport services"""

    id = models.CharField(max_length=10, primary_key=True)  # e.g. 'YCST'
    name = models.CharField(max_length=100, db_index=True)
    slug = AutoSlugField(populate_from='name', unique=True, editable=True)
    vehicle_mode = models.CharField(max_length=48, blank=True)
    parent = models.CharField(max_length=48, blank=True)
    region = models.ForeignKey(Region, models.CASCADE)

    address = models.CharField(max_length=128, blank=True)
    url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=128, blank=True)
    twitter = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('operator-detail', args=(self.slug or self.id,))

    def mode(self):
        return self.vehicle_mode

    def get_a_mode(self):
        """Return the the name of the operator's vehicle mode,
        with the correct indefinite article
        depending on whether it begins with a vowel sound.

        'Airline' becomes 'An airline', 'Bus' becomes 'A bus'.
        """
        mode = str(self.vehicle_mode).lower()
        if not mode or mode[0].lower() in 'aeiou':
            return 'An ' + mode  # 'An airline operating company' or 'An  operating company'
        return 'A ' + mode  # 'A hovercraft operating company'


class StopUsage(models.Model):
    """A link between a StopPoint and a Service,
    with an order placing it in a direction (e.g. the first outbound stop)"""
    service = models.ForeignKey('Service', models.CASCADE)
    stop = models.ForeignKey(StopPoint, models.CASCADE)
    direction = models.CharField(max_length=8)
    order = models.PositiveIntegerField()
    timing_status = models.CharField(max_length=3,
                                     choices=TIMING_STATUS_CHOICES)


@python_2_unicode_compatible
class Journey(models.Model):
    service = models.ForeignKey('Service', models.CASCADE)
    datetime = models.DateTimeField()
    destination = models.ForeignKey(StopPoint, models.CASCADE)

    def __str__(self):
        return '{} {}'.format(self.service, self.datetime)


@python_2_unicode_compatible
class StopUsageUsage(models.Model):
    id = models.BigAutoField(primary_key=True)
    journey = models.ForeignKey(Journey, models.CASCADE)
    stop = models.ForeignKey(StopPoint, models.CASCADE)
    datetime = models.DateTimeField()
    order = models.PositiveIntegerField()

    class Meta():
        index_together = (
            ('journey', 'datetime'),
            ('stop', 'datetime')
        )

    def __str__(self):
        return '{} {}'.format(self.stop, self.datetime)


@python_2_unicode_compatible
class Service(models.Model):
    """A bus service"""
    service_code = models.CharField(max_length=24, primary_key=True)
    line_name = models.CharField(max_length=64, blank=True)
    line_brand = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True)
    outbound_description = models.CharField(max_length=255, blank=True)
    inbound_description = models.CharField(max_length=255, blank=True)
    slug = AutoSlugField(populate_from='description', editable=True, blank=True)
    mode = models.CharField(max_length=11)
    operator = models.ManyToManyField(Operator, blank=True)
    net = models.CharField(max_length=3, blank=True)
    line_ver = models.PositiveIntegerField(null=True, blank=True)
    region = models.ForeignKey(Region, models.CASCADE)
    stops = models.ManyToManyField(StopPoint, editable=False,
                                   through=StopUsage)
    date = models.DateField()
    current = models.BooleanField(default=True, db_index=True)
    show_timetable = models.BooleanField(default=False)
    geometry = models.MultiLineStringField(null=True, editable=False)

    wheelchair = models.NullBooleanField()
    low_floor = models.NullBooleanField()
    assistance_service = models.NullBooleanField()
    mobility_scooter = models.NullBooleanField()

    def __str__(self):
        if self.line_name or self.line_brand or self.description:
            parts = (self.line_name, self.line_brand, self.description)
            return ' - '.join(part for part in parts if part != '')
        return self.service_code

    def has_long_line_name(self):
        "Is this service's line_name more than 4 characters long?"
        return len(self.line_name) > 4

    def get_a_mode(self):
        if self.mode and self.mode[0].lower() in 'aeiou':
            return 'An %s' % self.mode  # 'An underground service'
        return 'A %s' % self.mode  # 'A bus service' or 'A service'

    def get_absolute_url(self):
        return reverse('service-detail', args=(self.service_code,))

    def get_order(self):
        groups = SERVICE_ORDER_REGEX.match(self.line_name).groups()
        return (groups[0], int(groups[1]) if groups[1] else 0, groups[2])

    @staticmethod
    def get_operator_number(code):
        if code in {'MEGA', 'MBGD'}:
            return '11'
        if code in {'NATX', 'NXSH', 'NXAP'}:
            return '12'
        return {
            'BHAT': '41',
            'ESYB': '53',
            'WAIR': '20',
            'TVSN': '18'
        }.get(code)

    def get_tfl_url(self):
        if self.mode == 'bus' and len(self.line_name) <= 4:
            return 'https://tfl.gov.uk/bus/timetable/%s/' % self.line_name

    def get_trapeze_link(self):
        if self.region_id == 'Y':
            domain = 'yorkshiretravel.net'
            name = 'Yorkshire Travel'
        else:
            domain = 'travelinescotland.com'
            name = 'Traveline Scotland'
        query = (
            ('timetableId', self.service_code),
            ('direction', 'OUTBOUND'),
            ('queryDate', ''),
            ('queryTime', '')
        )
        return 'http://www.{}/lts/#/timetables?{}'.format(domain, urlencode(query)), name

    def get_megabus_url(self):
        query = (
            ('mid', 2678),
            ('id', 242611),
            ('clickref', 'links'),
            ('clickref2', self.service_code),
            ('p', 'https://uk.megabus.com'),
        )
        return 'https://www.awin1.com/awclick.php?' + urlencode(query)

    def get_traveline_link(self):
        if self.region_id in ('Y', 'S'):
            return self.get_trapeze_link()

        query = None

        if self.net != '':
            if self.net == 'tfl':
                return self.get_tfl_url(), 'Transport for London'

            parts = self.service_code.split('-')
            query = [('line', parts[0].split('_')[-1].zfill(2) + parts[1].zfill(3)),
                     ('lineVer', self.line_ver or parts[4]),
                     ('net', self.net),
                     ('project', parts[3])]
            if parts[2] != '_':
                query.append(('sup', parts[2]))

        elif self.region_id == 'GB':
            parts = self.service_code.split('_')
            operator_number = self.get_operator_number(parts[1])
            if operator_number is not None:
                query = [('line', operator_number + parts[0][:3].zfill(3)),
                         ('sup', parts[0][3:]),
                         ('net', 'nrc'),
                         ('project', 'y08')]

        if query is not None:
            query.extend([('command', 'direct'),
                          ('outputFormat', 0)])
            base_url = 'http://www.travelinesoutheast.org.uk/se'
            return '%s/XSLT_TTB_REQUEST?%s' % (base_url, urlencode(query)), 'Traveline'

        return None, None

    def is_megabus(self):
        return (self.line_name in ('FALCON', 'Oxford Tube')
                or self.pk in ('bed_1-X5-Z-y08', 'YWAX062', 'HIAG010', 'FSAM009', 'FSAG009', 'EDAO900', 'EDAAIR0')
                or any(o.pk in ('MEGA', 'MBGD', 'SCMG') for o in self.operator.all()))


class ServiceDate(models.Model):
    service = models.ForeignKey('Service', models.CASCADE)
    date = models.DateField()

    class Meta():
        unique_together = ('service', 'date')


@python_2_unicode_compatible
class Note(models.Model):
    """A note about an error in the timetable, the operator going bust, or something"""
    operators = models.ManyToManyField(Operator, blank=True)
    services = models.ManyToManyField(Service, blank=True)
    text = models.CharField(max_length=255)

    def __str__(self):
        return self.text

    def get_absolute_url(self):
        return (self.operators.first() or self.services.first()).get_absolute_url()
