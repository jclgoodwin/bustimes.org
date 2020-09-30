"Model definitions"

import re
import time
import logging
import yaml
from urllib.parse import urlencode, quote
from autoslug import AutoSlugField
from django.contrib.gis.db import models
from django.contrib.gis.geos import LineString, MultiLineString
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.indexes import GinIndex
from django.core.cache import cache
from django.db.models import Q
from django.urls import reverse
from django.utils.text import slugify
from django.utils.html import format_html, escape
from django.utils.safestring import mark_safe
from bustimes.models import Route, Trip
from bustimes.timetables import Timetable
from buses.utils import varnish_ban


logger = logging.getLogger(__name__)


TIMING_STATUS_CHOICES = (
    ('PPT', 'Principal point'),
    ('TIP', 'Time info point'),
    ('PTP', 'Principal and time info point'),
    ('OTH', 'Other bus stop'),
)
SERVICE_ORDER_REGEX = re.compile(r'(\D*)(\d*)(\D*)')


class SearchMixin:
    def update_search_vector(self):
        instance = self._meta.default_manager.with_documents().get(pk=self.pk)
        instance.search_vector = instance.document
        instance.save(update_fields=['search_vector'])

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if 'update_fields' in kwargs:
            if 'search_vector' in kwargs['update_fields']:
                return
        self.update_search_vector()


class Region(models.Model):
    """The largest type of geographical area"""
    id = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=48)

    class Meta:
        ordering = ['name']

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
        return reverse('region_detail', args=(self.id,))


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

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('adminarea_detail', args=(self.id,))


class District(models.Model):
    """A district within an administrative area.
    Note: some administrative areas *do not* have districts.
    """
    id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=48)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('district_detail', args=(self.id,))


class LocalityManager(models.Manager):
    def with_documents(self):
        vector = SearchVector('name', weight='A', config='english')
        vector += SearchVector('qualifier_name', weight='B', config='english')
        return self.get_queryset().annotate(document=vector)


class Locality(SearchMixin, models.Model):
    """A locality within an administrative area,
    and possibly within a district.

    Localities may be children of other localities...
    """
    id = models.CharField(max_length=48, primary_key=True)
    name = models.CharField(max_length=48)
    # short_name?
    qualifier_name = models.CharField(max_length=48, blank=True)
    slug = AutoSlugField(always_update=True, populate_from='get_qualified_name', editable=True, unique=True)
    admin_area = models.ForeignKey(AdminArea, models.CASCADE)
    district = models.ForeignKey(District, models.SET_NULL, null=True, blank=True)
    parent = models.ForeignKey('Locality', models.SET_NULL, null=True, editable=False)
    latlong = models.PointField(null=True, blank=True)
    adjacent = models.ManyToManyField('self', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    objects = LocalityManager()

    class Meta:
        ordering = ('name',)
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        return self.name or self.id

    def get_qualified_name(self):
        """Return the name and qualifier (e.g. 'Reepham, Lincs')"""
        if self.qualifier_name:
            return f'{self.name}, {self.qualifier_name}'
        return str(self)

    def get_absolute_url(self):
        return reverse('locality_detail', args=(self.slug,))


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


class DataSource(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField(blank=True)
    datetime = models.DateTimeField(null=True, blank=True)
    settings = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

    def credit(self):
        url = None
        text = None
        date = None

        if 'tnds' in self.url:
            url = 'https://www.travelinedata.org.uk/'
            text = 'the Traveline National Dataset'
        elif 'transportforireland' in self.url:
            url = 'https://www.transportforireland.ie/transitData/PT_Data.html'
            text = 'Transport for Ireland'
        elif 'open-data' in self.url or 'data.discover' in self.url:
            url = self.url
            text = self.name
            date = self.datetime
        elif self.url.startswith('https://data.bus-data.dft.gov.uk'):
            url = self.url.replace('download/', '')
            text = self.name.split('_')[0]
            date = self.datetime
        elif self.url.startswith('http://travelinedatahosting.basemap.co.uk/'):
            text = self.name
            date = self.datetime
        elif self.url.startswith('https://opendata.ticketer.com/uk/'):
            text = self.name
            date = self.datetime
        elif 'stagecoach' in self.url:
            url = 'https://www.stagecoachbus.com/open-data'
            text = self.name
            date = self.datetime
        elif self.name == 'MET' or self.name == 'ULB':
            url = self.url
            text = 'Translink open data'

        if not url and self.settings and 'url' in self.settings:
            url = self.settings['url']

        if url and 'bus-data.dft.gov.uk' in url:
            text = f'{text}/Bus Open Data Service'

        if text:
            if url:
                text = format_html('<a href="{}">{}</a>', url, text)
            else:
                text = escape(text)
            if date:
                date = date.strftime('%-d %B %Y')
                text = f'{text}, {date}'
            return mark_safe(f'<p class="credit">Timetable data from {text}</p>')

        return ''


class Place(models.Model):
    source = models.ForeignKey(DataSource, models.CASCADE)
    code = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    latlong = models.PointField(null=True, blank=True)
    polygon = models.PolygonField(null=True, blank=True)
    parent = models.ForeignKey('Place', models.SET_NULL, null=True, editable=False)
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        unique_together = ('source', 'code')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('place_detail', args=(self.pk,))


class StopPoint(models.Model):
    """The smallest type of geographical point.
    A point at which vehicles stop"""
    atco_code = models.CharField(max_length=16, primary_key=True)
    naptan_code = models.CharField(max_length=16, db_index=True, blank=True)

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
    locality_centre = models.BooleanField(null=True)

    places = models.ManyToManyField(Place, blank=True)

    heading = models.PositiveIntegerField(null=True, blank=True)

    BEARING_CHOICES = (
        ('N', 'north ↑'),
        ('NE', 'north-east ↗'),
        ('E', 'east →'),
        ('SE', 'south-east ↘'),
        ('S', 'south ↓'),
        ('SW', 'south-west ↙'),
        ('W', 'west ←'),
        ('NW', 'north-west ↖')
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
    stop_type = models.CharField(max_length=3, choices=STOP_TYPE_CHOICES, blank=True)

    BUS_STOP_TYPE_CHOICES = (
        ('MKD', 'Marked (pole, shelter etc)'),
        ('HAR', 'Hail and ride'),
        ('CUS', 'Custom (unmarked, or only marked on road)'),
        ('FLX', 'Flexible zone'),
    )
    bus_stop_type = models.CharField(max_length=3, choices=BUS_STOP_TYPE_CHOICES, blank=True)

    timing_status = models.CharField(max_length=3, choices=TIMING_STATUS_CHOICES, blank=True)

    admin_area = models.ForeignKey('AdminArea', models.SET_NULL, null=True, blank=True)
    active = models.BooleanField(db_index=True)

    osm = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ('common_name', 'atco_code')

    def __str__(self):
        name = self.get_unqualified_name()
        if self.bearing:
            name = f'{name} {self.get_arrow()}'
        return name

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

    prepositions = {
        'opp': 'opposite',
        'adj': 'adjacent to',
        'at': 'at',
        'o/s': 'outside',
        'nr': 'near',
        'before': 'before',
        'after': 'after',
        'by': 'by',
        'on': 'on',
        'in': 'in',
        'opposite': 'opposite',
        'outside': 'outside',
    }

    def get_unqualified_name(self):
        if self.indicator:
            return f'{self.common_name} ({self.indicator})'
        if self.atco_code[:3] == '940':
            return self.common_name.replace(' Underground Station', '')
        return self.common_name

    def get_arrow(self):
        if self.bearing:
            return self.get_bearing_display()[-1]
        return ''

    def get_qualified_name(self, short=True):
        name = self.get_unqualified_name()
        if self.locality:
            locality_name = self.locality.name.replace(' Town Centre', '') \
                                                .replace(' City Centre', '')
            if short:
                locality_name = locality_name.replace('-next-the-Sea', '') \
                                                .replace(' Next The Sea', '') \
                                                .replace('North ', 'N ') \
                                                .replace('East ', 'E ') \
                                                .replace('South ', 'S ') \
                                                .replace('West ', 'W ')
            if self.common_name in locality_name:
                return locality_name.replace(self.common_name, name)  # Cardiff Airport
            if slugify(locality_name) not in slugify(self.common_name):
                if self.indicator in self.prepositions:
                    indicator = self.indicator
                    if not short:
                        indicator = self.prepositions[indicator]
                    return '%s, %s %s' % (locality_name, indicator, self.common_name)
                return '%s %s' % (locality_name, name)
        elif self.town not in self.common_name:
            return f'{self.town} {name}'
        return name

    def get_long_name(self):
        return self.get_qualified_name(short=False)

    def get_region(self):
        if self.admin_area_id:
            return self.admin_area.region
        return Region.objects.filter(service__stops=self).first()

    def get_absolute_url(self):
        return reverse('stoppoint_detail', args=(self.atco_code,))

    def get_line_names(self):
        return [service.line_name for service in sorted(self.current_services, key=Service.get_order)]


class OperatorManager(models.Manager):
    def with_documents(self):
        vector = SearchVector('name', weight='A', config='english')
        vector += SearchVector('aka', weight='B', config='english')
        return self.get_queryset().annotate(document=vector)


class Operator(SearchMixin, models.Model):
    """An entity that operates public transport services"""

    id = models.CharField(max_length=10, primary_key=True)  # e.g. 'YCST'
    name = models.CharField(max_length=100, db_index=True)
    aka = models.CharField(max_length=100, blank=True)
    slug = AutoSlugField(populate_from=str, unique=True, editable=True)
    vehicle_mode = models.CharField(max_length=48, blank=True)
    parent = models.CharField(max_length=48, blank=True)
    region = models.ForeignKey(Region, models.CASCADE)

    address = models.CharField(max_length=128, blank=True)
    url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=128, blank=True)
    twitter = models.CharField(max_length=255, blank=True)

    licences = models.ManyToManyField('vosa.Licence', blank=True)
    payment_methods = models.ManyToManyField('PaymentMethod', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    objects = OperatorManager()

    class Meta:
        ordering = ('name',)
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        return str(self.name or self.id)

    national_expresses = {
        'Hotel Hoppa': '24233768',
        'National Express Airport': '24233764',
        'National Express': '21039402',
    }
    national_expresses['National Express Shuttle'] = national_expresses['National Express']
    national_expresses['Woking RailAir'] = national_expresses['National Express Airport']

    def is_national_express(self):
        return self.name in self.national_expresses

    def get_national_express_url(self):
        return (
            'https://clkuk.pvnsolutions.com/brand/contactsnetwork/click?p=230590&a=3022528&g='
            + {
                **self.national_expresses,
                'Xplore Dundee': self.national_expresses['National Express Airport']
            }[self.name]
        )

    def get_absolute_url(self):
        return reverse('operator_detail', args=(self.slug or self.id,))

    def mode(self):
        return self.vehicle_mode

    def get_a_mode(self):
        """Return the the name of the operator's vehicle mode,
        with the correct indefinite article
        depending on whether it begins with a vowel.

        'Airline' becomes 'An airline', 'Bus' becomes 'A bus'.
        """
        mode = str(self.vehicle_mode).lower()
        if not mode or mode[0].lower() in 'aeiou':
            return 'An ' + mode  # 'An airline' or 'An '
        return 'A ' + mode  # 'A hovercraft'


class StopCode(models.Model):
    stop = models.ForeignKey(StopPoint, models.CASCADE)
    source = models.ForeignKey(DataSource, models.CASCADE)
    code = models.CharField(max_length=100)

    class Meta:
        unique_together = ('code', 'source')

    def __str__(self):
        return self.code


class OperatorCode(models.Model):
    operator = models.ForeignKey(Operator, models.CASCADE)
    source = models.ForeignKey(DataSource, models.CASCADE)
    code = models.CharField(max_length=100, db_index=True)

    class Meta:
        unique_together = ('operator', 'code', 'source')

    def __str__(self):
        return self.code


class StopUsage(models.Model):
    """A link between a StopPoint and a Service,
    with an order placing it in a direction (e.g. the first outbound stop)"""
    service = models.ForeignKey('Service', models.CASCADE)
    stop = models.ForeignKey(StopPoint, models.CASCADE)
    direction = models.CharField(max_length=8)
    order = models.PositiveIntegerField()
    timing_status = models.CharField(max_length=3,
                                     choices=TIMING_STATUS_CHOICES)

    class Meta:
        ordering = ('direction', 'order')

    def is_minor(self):
        return self.timing_status == 'OTH' or self.timing_status == 'TIP'


class ServiceColour(models.Model):
    name = models.CharField(max_length=64)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    foreground = models.CharField(max_length=20, blank=True)
    background = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name

    def preview(self, name=False):
        return format_html('<div style="background:{};color:{}">{}</div>',
                           self.background, self.foreground, self.name or self.operator_id or '\u00A0')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.operator_id and self.name:
            Service.objects.filter(operator=self.operator_id, current=True, line_brand=self.name).update(colour=self)


class ServiceManager(models.Manager):
    def with_documents(self):
        vector = SearchVector('line_name', weight='A', config='english')
        vector += SearchVector('line_brand', weight='A', config='english')
        vector += SearchVector('description', weight='B', config='english')
        vector += SearchVector(StringAgg('operator__name', delimiter=' '), weight='B', config='english')
        vector += SearchVector(StringAgg('stops__locality__name', delimiter=' '), weight='C', config='english')
        vector += SearchVector(StringAgg('stops__common_name', delimiter=' '), weight='D', config='english')
        return self.get_queryset().annotate(document=vector)


class Service(models.Model):
    """A bus service"""
    service_code = models.CharField(max_length=64, unique=True)
    line_name = models.CharField(max_length=64, blank=True)
    line_brand = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True, db_index=True)
    outbound_description = models.CharField(max_length=255, blank=True)
    inbound_description = models.CharField(max_length=255, blank=True)
    slug = AutoSlugField(populate_from=str, editable=True, unique=True)
    mode = models.CharField(max_length=11, blank=True)
    operator = models.ManyToManyField(Operator, blank=True)
    region = models.ForeignKey(Region, models.CASCADE, null=True, blank=True)
    stops = models.ManyToManyField(StopPoint, editable=False,
                                   through=StopUsage)
    date = models.DateField()
    current = models.BooleanField(default=True, db_index=True)
    show_timetable = models.BooleanField(default=False)
    timetable_wrong = models.BooleanField(default=False)
    geometry = models.MultiLineStringField(null=True, editable=False)

    source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    tracking = models.BooleanField(default=False)
    payment_methods = models.ManyToManyField('PaymentMethod', blank=True)
    search_vector = SearchVectorField(null=True, blank=True)

    colour = models.ForeignKey(ServiceColour, models.SET_NULL, null=True, blank=True)

    objects = ServiceManager()
    update_search_vector = SearchMixin.update_search_vector

    class Meta:
        ordering = ['service_code']
        indexes = [
            GinIndex(fields=['search_vector'])
        ]

    def __str__(self):
        line_name = self.line_name
        description = None
        if hasattr(self, 'direction') and hasattr(self, f'{self.direction}_description'):
            description = getattr(self, f'{self.direction}_description')
        if not description or description.lower() == self.direction:
            description = self.description
        if description == line_name:
            description = None
        elif ' ' in line_name and line_name in description:
            line_name = None
        if line_name or self.line_brand or description:
            parts = (line_name, self.line_brand, description)
            return ' - '.join(part for part in parts if part)
        return self.service_code

    def yaml(self):
        return yaml.dump({
            self.service_code: {
                'line_name': self.line_name,
                'line_brand': self.line_brand,
                'description': self.description,
                'outbound_description': self.outbound_description,
                'inbound_description': self.inbound_description,
                'current': self.current,
                'show_timetable': self.show_timetable,
            }
        })

    def get_line_name_and_brand(self):
        if self.line_brand:
            return f'{self.line_name} - {self.line_brand}'
        return self.line_name

    def has_long_line_name(self):
        "Is this service's line_name more than 4 characters long?"
        return len(self.line_name) > 4

    def get_a_mode(self):
        if self.mode and self.mode[0].lower() in 'aeiou':
            return f'An {self.mode}'  # 'An underground service'
        return f'A {self.mode}'  # 'A bus service' or 'A service'

    def get_absolute_url(self):
        return reverse('service_detail', args=(self.slug,))

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
        return f'https://tfl.gov.uk/bus/timetable/{self.line_name}/'

    def get_trapeze_link(self, date):
        domain = 'travelinescotland.com'
        name = 'Timetable on the Traveline Scotland website'
        if date:
            date = int(time.mktime(date.timetuple()) * 1000)
        else:
            date = ''
        query = (
            ('timetableId', self.service_code),
            ('direction', 'OUTBOUND'),
            ('queryDate', date),
            ('queryTime', date)
        )
        return f'http://www.{domain}/lts/#/timetables?{urlencode(query)}', name

    def is_megabus(self):
        return (
            self.line_name in {'FLCN', 'TUBE'}
            or self.service_code.startswith('460-X5_STB_PF_X5')
            or any(o.pk in {'MEGA', 'SCMG'} for o in self.operator.all())
        )

    def get_megabus_url(self):
        # Using a tuple of tuples, instead of a dict, because the order is important for tests
        query = (
            ('mid', 2678),
            ('id', 242611),
            ('clickref', 'links'),
            ('clickref2', self.service_code),
            ('p', 'https://uk.megabus.com'),
        )
        return 'https://www.awin1.com/awclick.php?' + urlencode(query)

    def get_traveline_links(self, date=None):
        if not self.source:
            return

        if self.source.name == 'S':
            yield self.get_trapeze_link(date)
            return

        if self.source.name == 'W' or self.region_id == 'W':
            for service_code in self.servicecode_set.filter(scheme='Traveline Cymru'):
                query = (
                    ('routeNum', self.line_name),
                    ('direction_id', 0),
                    ('timetable_key', service_code.code)
                )
                url = 'https://www.traveline.cymru/timetables/?' + urlencode(query)
                yield (url, 'Timetable on the Traveline Cymru website')
            return

        base_url = 'http://nationaljourneyplanner.travelinesw.com/swe-ttb/XSLT_TTB_REQUEST?'

        base_query = [('command', 'direct'), ('outputFormat', 0)]

        if self.source.name == 'NCSD':
            parts = self.service_code.split('_')
            operator_number = self.get_operator_number(parts[1])
            if operator_number is not None:
                query = [('line', operator_number + parts[0][:3].zfill(3)),
                         ('sup', parts[0][3:]),
                         ('net', 'nrc'),
                         ('project', 'y08')]
                yield (
                    f'{base_url}{urlencode(query + base_query)}',
                    'Timetable on the Traveline South West website'
                )

        elif self.source.name in {'SE', 'SW', 'EM', 'WM', 'EA', 'L'}:
            if self.servicecode_set.filter(scheme='TfL').exists():
                yield (self.get_tfl_url(), 'Timetable on the Transport for London website')
                return

            if self.service_code.startswith('tfl_'):
                return

            try:
                for i, route in enumerate(self.route_set.order_by('start_date')):

                    parts = route.code.split('-')
                    net, line = parts[0].split('_')
                    line_ver = parts[4][:-4]
                    line = line.zfill(2) + parts[1].zfill(3)

                    query = [('line', line),
                             ('lineVer', line_ver),
                             ('net', net),
                             ('project', parts[3])]
                    if parts[2] != '_':
                        query.append(('sup', parts[2]))

                    text = 'Timetable'
                    if i:
                        date = route.start_date.strftime('%-d %B')
                        text = f'{text} from {date}'
                    text = f'{text} on the Traveline South West website'

                    yield (
                        f'{base_url}{urlencode(query + base_query)}',
                        text
                    )
            except (ValueError, IndexError):
                pass

    def get_linked_services_cache_key(self):
        return f'{quote(self.service_code)}linked_services{self.date}'

    def get_similar_services_cache_key(self):
        return f'{quote(self.service_code)}similar_services{self.date}'

    def get_linked_services(self):
        key = self.get_linked_services_cache_key()
        services = cache.get(key)
        if services is None:
            services = list(Service.objects.filter(
                Q(link_from__to_service=self, link_from__how='parallel')
                | Q(link_to__from_service=self, link_to__how='parallel')
            ).order_by().defer('geometry'))
            cache.set(key, services)
        return services

    def get_similar_services(self):
        key = self.get_similar_services_cache_key()
        services = cache.get(key)
        if services is None:
            q = Q(link_from__to_service=self) | Q(link_to__from_service=self)
            if self.description and self.line_name:
                q |= Q(description=self.description)
                q |= Q(line_name=self.line_name, operator__in=self.operator.all())
            services = Service.objects.filter(~Q(pk=self.pk), q, current=True).order_by().defer('geometry')
            services = sorted(services.distinct().prefetch_related('operator'), key=Service.get_order)
            cache.set(key, services)
        return services

    def get_timetable(self, day=None, related=()):
        """Given a Service, return a Timetable"""

        if self.region_id == 'NI' or self.source and self.source.name.endswith(' GTFS'):
            return Timetable(self.route_set.all(), day)

        if related:
            routes = Route.objects.filter(service__in=[self] + related).order_by('start_date')
        else:
            routes = self.route_set.order_by('start_date')
        try:
            timetable = Timetable(routes, day)
        except (IndexError, UnboundLocalError) as e:
            logger.error(e, exc_info=True)
            return
        if timetable.date and self.source and not self.source.url.endswith('/open-data'):
            for route in routes:
                if route.start_date > timetable.date:
                    self.timetable_change = route.start_date
                    break

        return timetable

    def varnish_ban(self):
        varnish_ban(self.get_absolute_url())

    def update_geometry(self):
        patterns = []
        linestrings = []
        for trip in Trip.objects.filter(route__service=self).prefetch_related('stoptime_set__stop'):
            stops = [stoptime.stop for stoptime in trip.stoptime_set.all() if stoptime.stop and stoptime.stop.latlong]
            pattern = [stop.pk for stop in stops]
            if pattern in patterns:
                continue
            patterns.append(pattern)
            points = [stop.latlong for stop in stops]
            if points:
                linestrings.append(LineString(points))
        if linestrings:
            self.geometry = MultiLineString(*linestrings)
            self.save(update_fields=['geometry'])


class ServiceCode(models.Model):
    service = models.ForeignKey(Service, models.CASCADE)
    scheme = models.CharField(max_length=255)
    code = models.CharField(max_length=255)

    class Meta:
        unique_together = ('service', 'scheme', 'code')

    def __str__(self):
        return f'{self.scheme} {self.code}'


class ServiceLink(models.Model):
    from_service = models.ForeignKey(Service, models.CASCADE, 'link_from')
    to_service = models.ForeignKey(Service, models.CASCADE, 'link_to')
    how = models.CharField(max_length=10, choices=(
        ('parallel', 'Combine timetables'),
        ('also', 'Just list'),
    ))

    def get_absolute_url(self):
        return self.from_service.get_absolute_url()


class PaymentMethod(models.Model):
    name = models.CharField(max_length=48)
    url = models.URLField(blank=True)

    def __str__(self):
        return self.name


class Contact(models.Model):
    from_name = models.CharField(max_length=255)
    from_email = models.EmailField()
    message = models.TextField()
    spam_score = models.PositiveIntegerField()
    ip_address = models.GenericIPAddressField()
    referrer = models.URLField(blank=True)


class SIRISource(models.Model):
    name = models.CharField(max_length=255)
    url = models.URLField()
    requestor_ref = models.CharField(max_length=255, blank=True)
    admin_areas = models.ManyToManyField(AdminArea, blank=True)

    def __str__(self):
        return self.name

    def get_poorly_key(self):
        return f'{self.url}:{self.requestor_ref}:poorly'

    def get_poorly(self):
        return cache.get(self.get_poorly_key())

    get_poorly.short_description = 'Poorly'
