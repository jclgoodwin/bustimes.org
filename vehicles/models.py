import re
import json

from math import ceil
from urllib.parse import quote
from datetime import timedelta
from webcolors import html5_parse_simple_color

from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from django.db.models.functions import TruncDate, Upper
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils import timezone
from busstops.models import Operator, Service, DataSource, SIRISource
from bustimes.models import get_calendars, get_routes, Trip, RouteLink


def format_reg(reg):
    if '-' not in reg:
        if reg[-3:].isalpha():
            return reg[:-3] + ' ' + reg[-3:]
        if reg[:3].isalpha():
            return reg[:3] + ' ' + reg[3:]
        if reg[-2:].isalpha():
            return reg[:-2] + ' ' + reg[-2:]
    return reg


def get_css(colours, direction=None, horizontal=False, angle=None):
    if len(colours) == 1:
        return colours[0]
    if direction is None:
        direction = 180
    else:
        direction = int(direction)
    background = 'linear-gradient('
    if horizontal:
        background += 'to top'
    elif direction < 180:
        if angle:
            background += f'{360-angle}deg'
        else:
            background += 'to left'
    elif angle:
        background += f'{angle}deg'
    else:
        background += 'to right'
    percentage = 100 / len(colours)
    for i, colour in enumerate(colours):
        if i != 0 and colour != colours[i - 1]:
            background += ',{} {}%'.format(colour, ceil(percentage * i))
        if i != len(colours) - 1 and colour != colours[i + 1]:
            background += ',{} {}%'.format(colour, ceil(percentage * (i + 1)))
    background += ')'

    return background


def get_brightness(colour):
    return (0.299 * colour.red + 0.587 * colour.green + 0.114 * colour.blue) / 255


def get_text_colour(colours):
    if not colours or colours == 'Other':
        return
    colours = colours.split()
    colours = [html5_parse_simple_color(colour) for colour in colours]
    brightnesses = [get_brightness(colour) for colour in colours]
    colours_length = len(colours)
    if colours_length > 2:
        middle_brightness = sum(brightnesses[1:-1])
        outer_brightness = (brightnesses[0] + brightnesses[-1])
        brightness = (middle_brightness * 2 + outer_brightness) / ((colours_length - 2) * 2 + 2)
    else:
        brightness = sum(brightnesses) / colours_length
    if brightness < .5:
        return '#fff'


class VehicleType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    double_decker = models.BooleanField(null=True)
    coach = models.BooleanField(null=True)
    electric = models.BooleanField(null=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class Livery(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    colours = models.CharField(max_length=255, blank=True)
    css = models.CharField(max_length=255, blank=True)
    left_css = models.CharField(max_length=255, blank=True)
    right_css = models.CharField(max_length=255, blank=True)
    white_text = models.BooleanField(default=False)
    text_colour = models.CharField(max_length=7, blank=True)
    horizontal = models.BooleanField(default=False)
    angle = models.PositiveSmallIntegerField(null=True, blank=True)
    operator = models.ForeignKey('busstops.Operator', models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'liveries'

    def __str__(self):
        return self.name

    def set_css(self):
        if self.css:
            css = self.css
            self.left_css = css
            for angle in re.findall(r'\((\d+)deg,', css):
                replacement = 360 - int(angle)
                css = css.replace(f'({angle}deg,', f'({replacement}deg,', 1)
                # doesn't work with e.g. angles {a, b} where a = 360 - b
            self.right_css = css.replace('left', 'right')

        elif self.colours and self.colours != 'Other':
            self.left_css = get_css(self.colours.split(), None, self.horizontal, self.angle)
            self.right_css = get_css(self.colours.split(), 90, self.horizontal, self.angle)

    def preview(self, name=False):
        if self.left_css:
            background = escape(self.left_css)
        elif self.colours:
            background = get_css(self.colours.split())
        elif name:
            background = ''
        else:
            return

        div = f'<div style="height:1.5em;width:2.25em;background:{background}"'
        if name:
            return format_html(div + '></div> {}', self.name)
        else:
            return format_html(div + ' title="{}"></div>', self.name)

    def clean(self):
        try:
            get_text_colour(self.colours)
        except ValueError as e:
            raise ValidationError({
                'colours': str(e)
            })

    def save(self, *args, update_fields=None, **kwargs):
        if update_fields is None and (self.css or self.colours):
            self.set_css()
            if self.colours and not self.id:
                self.white_text = (get_text_colour(self.colours) == '#fff')
        super().save(*args, update_fields=update_fields, **kwargs)


class VehicleFeature(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    code = models.CharField(max_length=255)
    fleet_number = models.PositiveIntegerField(null=True, blank=True)
    fleet_code = models.CharField(max_length=24, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey(VehicleType, models.SET_NULL, null=True, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    branding = models.CharField(max_length=255, null=True, blank=True)
    notes = models.CharField(max_length=255, null=True, blank=True)
    latest_journey = models.OneToOneField(
        'VehicleJourney', models.SET_NULL, null=True, blank=True, editable=False, related_name='latest_vehicle'
    )
    latest_journey_data = models.JSONField(null=True, blank=True)
    features = models.ManyToManyField(VehicleFeature, blank=True)
    withdrawn = models.BooleanField(default=False)
    data = models.JSONField(null=True, blank=True)
    garage = models.ForeignKey('bustimes.Garage', models.SET_NULL, null=True, blank=True)

    def save(self, *args, update_fields=None, **kwargs):
        if (update_fields is None or 'fleet_number' in update_fields) and self.fleet_number:
            if not self.fleet_code or (self.fleet_code.isdigit() and self.fleet_number != int(self.fleet_code)):
                self.fleet_code = str(self.fleet_number)
                if update_fields is not None and 'fleet_code' not in update_fields:
                    update_fields.append('fleet_code')

        if (update_fields is None or 'fleet_code' in update_fields) and self.fleet_code:
            if not self.fleet_number and self.fleet_code.isdigit():
                self.fleet_number = int(self.fleet_code)
                if update_fields is not None and 'fleet_number' not in update_fields:
                    update_fields.append('fleet_number')

        if update_fields is None and not self.reg:
            reg = re.match(r"^[A-Z]\w_?\d\d?[ _-]?[A-Z]{3}$", self.code)
            if reg:
                self.reg = re.sub("[-_ ]", "", self.code)
        elif update_fields is None or 'reg' in update_fields:
            self.reg = self.reg.upper().replace(' ', '')

        super().save(*args, update_fields=update_fields, **kwargs)

    class Meta:
        unique_together = ('code', 'operator')
        indexes = [
            models.Index(Upper('fleet_code'), name='fleet_code'),
            models.Index(Upper('reg'), name='reg'),
        ]

    def __str__(self):
        fleet_code = self.fleet_code or self.fleet_number
        if self.reg:
            if fleet_code:
                return f'{fleet_code} - {self.get_reg()}'
            return self.get_reg()
        if fleet_code:
            return str(fleet_code)
        return self.code.replace('_', ' ')

    def get_previous(self):
        if self.fleet_number and self.operator:
            vehicles = self.operator.vehicle_set.filter(withdrawn=False, fleet_number__lt=self.fleet_number)
            return vehicles.order_by('-fleet_number').first()

    def get_next(self):
        if self.fleet_number and self.operator:
            vehicles = self.operator.vehicle_set.filter(withdrawn=False, fleet_number__gt=self.fleet_number)
            return vehicles.order_by('fleet_number').first()

    def get_reg(self):
        return format_reg(self.reg)

    def data_get(self, key=None):
        if not key:
            if self.data:
                return [(key, self.data_get(key)) for key in self.data]
            return ()
        if self.data:
            value = self.data.get(key)
            if value:
                if key == 'Previous reg':
                    if ',' in value:
                        return ', '.join(format_reg(reg) for reg in value.split(','))
                    return format_reg(value)
                return value
        return ''

    def get_text_colour(self):
        if self.livery:
            if self.livery.white_text:
                return '#fff'
        elif self.colours:
            return get_text_colour(self.colours)

    def get_livery(self, direction=None):
        if self.livery:
            if direction is not None and direction < 180:
                return escape(self.livery.right_css)
            return escape(self.livery.left_css)

        colours = self.colours
        if colours and colours != 'Other':
            colours = colours.split()
            return get_css(colours, direction, self.livery and self.livery.horizontal)

    def get_absolute_url(self):
        return reverse('vehicle_detail', args=(self.id,))

    def get_edit_url(self):
        return reverse('vehicle_edit', args=(self.id,))

    def get_history_url(self):
        return reverse('vehicle_history', args=(self.id,))

    def fleet_number_mismatch(self):
        if self.code.isdigit():
            if self.fleet_number and self.fleet_number != int(self.code):
                return True
        elif self.reg:
            code = self.code.replace('-', '').replace('_', '').replace(' ', '').upper()
            if self.reg not in code:
                fleet_code = self.fleet_code.replace(' ', '') or self.fleet_number
                if not fleet_code or str(fleet_code) not in code:
                    return True

    def get_flickr_url(self):
        if self.reg:
            reg = self.get_reg()
            search = f'{self.reg} or "{reg}"'
            if self.fleet_number and self.operator and self.operator.parent:
                number = str(self.fleet_number)
                if len(number) >= 5:
                    search = f'{search} or {self.operator.parent} {number}'
        else:
            if self.fleet_code or self.fleet_number:
                search = self.fleet_code or str(self.fleet_number)
            else:
                search = str(self).replace('/', ' ')
            if self.operator:
                name = str(self.operator).split(' (', 1)[0]
                if 'Yellow' not in name:
                    name = str(self.operator).replace(' Buses', '', 1).replace(' Coaches', '', 1)
                if name.startswith('First ') or name.startswith('Stagecoach ') or name.startswith('Arriva '):
                    name = name.split()[0]
                search = f'{name} {search}'
        return f'https://www.flickr.com/search/?text={quote(search)}&sort=date-taken-desc'

    def get_flickr_link(self):
        if self.notes == 'Spare ticket machine':
            return ''
        return format_html('<a href="{}" target="_blank" rel="noopener">Flickr</a>', self.get_flickr_url())

    get_flickr_link.short_description = 'Flickr'

    clean = Livery.clean  # validate colours field

    def get_json(self, heading):
        json = {
            'url': self.get_absolute_url(),
            'name': str(self),
        }

        features = self.feature_names
        if self.vehicle_type:
            if self.vehicle_type.double_decker:
                vehicle_type = 'Double decker'
                if self.vehicle_type.coach:
                    vehicle_type = f'{vehicle_type} coach'
            elif self.vehicle_type.coach:
                vehicle_type = 'Coach'
            else:
                vehicle_type = None
            if vehicle_type:
                if features:
                    features = f'{vehicle_type}<br>{features}'
                else:
                    features = vehicle_type
        if features:
            json['features'] = features

        if self.livery_id:
            json['livery'] = self.livery_id
        elif self.colours:
            json['css'] = self.get_livery(heading)
            json['text_colour'] = self.get_text_colour()
        return json


class VehicleCode(models.Model):
    code = models.CharField(max_length=24)
    scheme = models.CharField(max_length=24)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)

    class Meta:
        index_together = ('code', 'scheme')


class VehicleEditFeature(models.Model):
    feature = models.ForeignKey(VehicleFeature, models.CASCADE)
    edit = models.ForeignKey('VehicleEdit', models.CASCADE)
    add = models.BooleanField(default=True)

    def __str__(self):
        if self.add:
            fmt = '<ins>{}</ins>'
        else:
            fmt = '<del>{}</del>'
        return format_html(fmt, self.feature)


class VehicleEdit(models.Model):
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    fleet_number = models.CharField(max_length=24, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    vehicle_type = models.CharField(max_length=255, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    branding = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    features = models.ManyToManyField(VehicleFeature, blank=True, through=VehicleEditFeature)
    withdrawn = models.BooleanField(null=True)
    changes = models.JSONField(null=True, blank=True)
    url = models.URLField(blank=True, max_length=255)
    approved = models.BooleanField(null=True, db_index=True)
    score = models.SmallIntegerField(default=0)
    datetime = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, blank=True)

    def get_css(self):
        if self.colours and self.colours != 'Other':
            return get_css(self.colours.split())

    def get_changes(self):
        changes = {}
        for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes', 'colours', 'livery_id'):
            edit = str(getattr(self, field) or '')
            if edit:
                if field == 'reg':
                    edit = edit.upper().replace(' ', '')
                if field == 'fleet_number' and self.vehicle.fleet_code:
                    vehicle = self.vehicle.fleet_code
                else:
                    vehicle = str(getattr(self.vehicle, field) or '')

                if edit.startswith('-'):
                    if edit == f'-{vehicle}':
                        edit = format_html('<del>{}</del>', vehicle)
                    else:
                        edit = ''
                if edit != vehicle:
                    changes[field] = edit
        changed_features = self.vehicleeditfeature_set.all()
        if changed_features:
            features = []
            for feature in changed_features:
                if feature.add:
                    if feature.feature not in self.vehicle.features.all():
                        features.append(feature)
                elif feature.feature in self.vehicle.features.all():
                    features.append(feature)
            if features:
                changes['features'] = features
        if self.withdrawn is not None and self.withdrawn != self.vehicle.withdrawn:
            if not self.withdrawn or not self.vehicle.latest_journey or self.datetime > self.vehicle.latest_journey.datetime:
                changes['withdrawn'] = self.withdrawn
        if self.changes:
            for key in self.changes:
                if not self.vehicle.data or self.changes[key] != self.vehicle.data.get(key):
                    changes[key] = self.changes[key]
        return changes

    def apply(self, save=True):
        ok = True
        vehicle = self.vehicle
        if save:
            revision = self.make_revision()
        update_fields = []
        if self.withdrawn is not None:
            vehicle.withdrawn = self.withdrawn
            update_fields.append('withdrawn')
        if self.fleet_number:
            if self.fleet_number.startswith('-'):
                if self.fleet_number == f'-{vehicle.fleet_code or vehicle.fleet_number}':
                    vehicle.fleet_code = ''
                    vehicle.fleet_number = None
            else:
                vehicle.fleet_code = self.fleet_number
                if self.fleet_number.isdigit():
                    vehicle.fleet_number = self.fleet_number
                else:
                    vehicle.fleet_number = None
            update_fields.append('fleet_code')
            update_fields.append('fleet_number')
        if self.changes:
            if vehicle.data:
                vehicle.data = {
                    **vehicle.data, **self.changes
                }
                for field in self.changes:
                    if not self.changes[field]:
                        del vehicle.data[field]
            else:
                vehicle.data = self.changes
            update_fields.append('data')
        for field in ('branding', 'name', 'notes', 'reg'):
            new_value = getattr(self, field)
            if new_value:
                if new_value.startswith('-'):
                    if new_value == f'-{getattr(vehicle, field)}':
                        setattr(vehicle, field, '')
                    else:
                        continue
                else:
                    setattr(vehicle, field, new_value)
                update_fields.append(field)
        if self.vehicle_type:
            try:
                vehicle.vehicle_type = VehicleType.objects.get(name__iexact=self.vehicle_type)
                update_fields.append('vehicle_type')
            except VehicleType.DoesNotExist:
                ok = False
        if self.livery_id:
            vehicle.livery_id = self.livery_id
            vehicle.colours = ''
            update_fields.append('livery')
            update_fields.append('colours')
        elif self.colours and self.colours != 'Other':
            vehicle.livery = None
            vehicle.colours = self.colours
            update_fields.append('livery')
            update_fields.append('colours')
        if save:
            vehicle.save(update_fields=update_fields)
            if revision:
                revision.save()
            for feature in self.vehicleeditfeature_set.all():
                if feature.add:
                    vehicle.features.add(feature.feature)
                else:
                    vehicle.features.remove(feature.feature)
            if ok:
                self.approved = True
                self.save(update_fields=['approved'])

    def make_revision(self):
        revision = VehicleRevision(
            user_id=self.user_id,
            vehicle_id=self.vehicle_id,
            datetime=self.datetime,
            message=self.url,
            to_livery_id=self.livery_id,
            changes={}
        )
        if self.vehicle_type:
            try:
                revision.to_type = VehicleType.objects.get(name=self.vehicle_type)
            except VehicleType.DoesNotExist:
                pass
            else:
                if revision.to_type.id != self.vehicle.vehicle_type_id:
                    revision.from_type_id = self.vehicle.vehicle_type_id
        for field in ('reg', 'name', 'branding', 'notes', 'fleet_number'):
            to_value = getattr(self, field)
            if to_value:
                from_value = getattr(self.vehicle, field)
                if field == 'fleet_number':
                    from_value = self.vehicle.fleet_code
                    field = 'fleet number'
                if to_value.startswith('-') and (to_value == f"-{from_value}" or from_value == ''):
                    to_value = ''
                elif from_value == to_value:
                    from_value = ''
                revision.changes[field] = f"-{from_value}\n+{to_value}"
        if revision.to_livery_id or revision.to_type_id or revision.changes:
            return revision

    def get_absolute_url(self):
        return self.vehicle.get_absolute_url()

    def __str__(self):
        return str(self.id)


class VehicleEditVote(models.Model):
    by_user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)
    for_edit = models.ForeignKey(VehicleEdit, models.CASCADE)
    positive = models.BooleanField()

    class Meta:
        unique_together = ('by_user', 'for_edit')


class VehicleRevisionFeature(models.Model):
    feature = models.ForeignKey(VehicleFeature, models.CASCADE)
    revision = models.ForeignKey('VehicleRevision', models.CASCADE)
    add = models.BooleanField(default=True)

    __str__ = VehicleEditFeature.__str__


class VehicleRevision(models.Model):
    datetime = models.DateTimeField()
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    from_operator = models.ForeignKey(Operator, models.DO_NOTHING, null=True, blank=True, related_name='revision_from')
    to_operator = models.ForeignKey(Operator, models.DO_NOTHING, null=True, blank=True, related_name='revision_to')
    from_type = models.ForeignKey(VehicleType, models.DO_NOTHING, null=True, blank=True, related_name='revision_from')
    to_type = models.ForeignKey(VehicleType, models.DO_NOTHING, null=True, blank=True, related_name='revision_to')
    from_livery = models.ForeignKey(Livery, models.DO_NOTHING, null=True, blank=True, related_name='revision_from')
    to_livery = models.ForeignKey(Livery, models.DO_NOTHING, null=True, blank=True, related_name='revision_to')
    changes = models.JSONField(null=True, blank=True)
    message = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, blank=True)
    features = models.ManyToManyField(VehicleFeature, blank=True, through=VehicleRevisionFeature)

    def __str__(self):
        return ', '.join(
            f'{key}: {before} → {after}' for key, before, after in self.list_changes(html=False)
        )

    def list_changes(self, html=True):
        for field in ('operator', 'type', 'livery'):

            if getattr(self, f'from_{field}_id') or getattr(self, f'to_{field}_id'):

                if getattr(__class__, f'from_{field}').is_cached(self):

                    before = getattr(self, f'from_{field}')
                    after = getattr(self, f'to_{field}')

                    if field == 'livery':
                        if before:
                            before = format_html('<span class="livery" style="background:{}"></span>', before.left_css)
                        if after:
                            after = format_html('<span class="livery" style="background:{}"></span>', after.left_css)
                else:
                    before = getattr(self, f'from_{field}_id')
                    after = getattr(self, f'to_{field}_id')
                yield (field, before, after)
        if self.changes:
            for key in self.changes:
                before, after = self.changes[key].split('\n+')
                before = before[1:]
                if key == 'colours' and html:
                    if before and before != 'Other':
                        before = format_html('<span class="livery" style="background:{}"></span>', before)
                    if after and after != 'Other':
                        after = format_html('<span class="livery" style="background:{}"></span>', after)
                yield (key, before, after)

    def revert(self):
        """Revert various values to how they were before the revision
        """
        vehicle = self.vehicle
        fields = []

        for key, vehicle_key in (
            ('operator', 'operator'),
            ('type',     'vehicle_type'),
            ('livery',   'livery')
        ):
            before = getattr(self, f'from_{key}_id')
            after = getattr(self, f'to_{key}_id')
            if before or after:
                if getattr(vehicle, f'{vehicle_key}_id') == after:
                    setattr(vehicle, f'{vehicle_key}_id', before)
                    fields.append(vehicle_key)

        if self.changes:
            for key in self.changes:
                before, after = self.changes[key].split('\n+')
                before = before[1:]
                if key == 'reg' or key == 'name':
                    if getattr(vehicle, key) == after:
                        setattr(vehicle, key, before)
                        fields.append('reg')
                elif key == 'withdrawn':
                    if vehicle.withdrawn and after == 'Yes':
                        vehicle.withdrawn = False
                        fields.append('withdrawn')
                else:
                    yield f'vehicle {vehicle.id} {key} not reverted'

        if fields:
            self.vehicle.save(update_fields=fields)
            yield f'vehicle {vehicle.id} reverted {fields}'


class VehicleJourney(models.Model):
    datetime = models.DateTimeField()
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    route_name = models.CharField(max_length=64, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE, null=True, blank=True)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, blank=True)
    data = models.JSONField(null=True, blank=True)
    trip = models.ForeignKey('bustimes.Trip', models.SET_NULL, null=True, blank=True)

    def get_absolute_url(self):
        return f"/vehicles/{self.vehicle_id}?date={self.datetime.date()}#journeys/{self.id}"

    def get_path(self):
        return settings.DATA_DIR / 'journeys' / str(self.id)

    def __str__(self):
        when = self.datetime.strftime('%-d %b %y %H:%M')
        when = f"{when} {self.route_name} {self.code} {self.direction}"
        if self.destination:
            when = f'{when} to {self.destination}'
        return when

    class Meta:
        ordering = ('id',)
        indexes = [
            models.Index('service', TruncDate('datetime').asc(), name='service_datetime_date'),
            models.Index('vehicle', TruncDate('datetime').asc(), name='vehicle_datetime_date')
        ]
        unique_together = (
            ('vehicle', 'datetime'),
        )

    def get_trip(self, datetime=None, date=None, destination_ref=None, departure_time=None, journey_ref=None):
        if not self.service:
            return

        if journey_ref == self.code:
            journey_ref = None

        if not datetime:
            datetime = self.datetime
        if not date:
            date = (departure_time or datetime).date()

        routes = get_routes(self.service.route_set.select_related('source'), date)
        if not routes:
            return
        trips = Trip.objects.filter(route__in=routes)

        if destination_ref and ' ' not in destination_ref and destination_ref[:3].isdigit():
            destination = Q(destination=destination_ref)
        else:
            destination = None

        if self.direction == 'outbound':
            direction = Q(inbound=False)
        elif self.direction == 'inbound':
            direction = Q(inbound=True)
        else:
            direction = None

        if departure_time:
            start = timezone.localtime(departure_time)
            start = timedelta(hours=start.hour, minutes=start.minute)
        elif len(self.code) == 4 and self.code.isdigit() and int(self.code) < 2400:
            hours = int(self.code[:-2])
            minutes = int(self.code[-2:])
            start = timedelta(hours=hours, minutes=minutes)
        else:
            start = None

        if start is not None:
            start = Q(start=start)
            trips_at_start = trips.filter(start)

            if destination:
                if direction:
                    destination |= direction
                trips_at_start = trips_at_start.filter(destination)
            elif direction:
                trips_at_start = trips_at_start.filter(direction)

            try:
                return trips_at_start.get()
            except Trip.MultipleObjectsReturned:
                try:
                    return trips_at_start.get(calendar__in=get_calendars(date))
                except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                    if not journey_ref:
                        return
            except Trip.DoesNotExist:
                if destination and departure_time:
                    try:
                        return trips.get(start, calendar__in=get_calendars(date))
                    except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                        pass

        if not journey_ref:
            journey_ref = self.code

        try:
            return trips.get(ticket_machine_code=journey_ref)
        except Trip.MultipleObjectsReturned:
            trips = trips.filter(calendar__in=get_calendars(date))
            try:
                return trips.get(ticket_machine_code=journey_ref)
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass
        except Trip.DoesNotExist:
            pass

    def get_progress(self, location):
        point = Point(location["coordinates"][0], location["coordinates"][1], srid=4326)

        trip = self.trip_id

        return RouteLink.objects.filter(
            geometry__bboverlaps=point.buffer(0.001),
            service=self.service_id,
            from_stop__stoptime__trip=trip,
            to_stop__stoptime__trip=trip,
            to_stop__stoptime__id__gt=F('from_stop__stoptime__id')
        ).annotate(
            distance=models.functions.Distance('geometry', point),
            from_stoptime=F('from_stop__stoptime'),
            to_stoptime=F('to_stop__stoptime')
        ).order_by('distance').first()


class JourneyCode(models.Model):
    code = models.CharField(max_length=64, blank=True)
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    data_source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    siri_source = models.ForeignKey(SIRISource, models.SET_NULL, null=True, blank=True)
    destination = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = (
            ('code', 'service', 'siri_source'),
            ('code', 'service', 'data_source'),
        )


class Occupancy(models.TextChoices):
    SEATS_AVAILABLE = 'seatsAvailable', 'Seats available'
    STANDING_AVAILABLE = 'standingAvailable', 'Standing available'
    FULL = 'full', 'Full'


class VehicleLocation:
    def __init__(self, latlong, heading=None, delay=None, early=None, occupancy=None):
        self.latlong = latlong
        self.heading = heading
        self.delay = delay
        self.early = early
        self.occupancy = occupancy
        self.seated_occupancy = None
        self.seated_capacity = None
        self.wheelchair_occupancy = None
        self.wheelchair_capacity = None
        self.occupancy_thresholds = None

    def get_occupancy_display(self):
        return Occupancy(self.occupancy).label

    def __str__(self):
        return self.datetime.strftime('%-d %b %Y %H:%M:%S')

    class Meta:
        ordering = ('id',)

    def get_appendage(self):
        appendage = [self.datetime, self.latlong.coords, self.heading, self.early]
        return (f'journey{self.journey.id}', json.dumps(appendage, cls=DjangoJSONEncoder))

    def get_redis_json(self):
        journey = self.journey

        json = {
            'id': self.id,
            'coordinates': self.latlong.coords,
            'heading': self.heading,
            'datetime': self.datetime,
            'destination': journey.destination,
        }

        if journey.trip_id:
            json['trip_id'] = journey.trip_id
        if journey.service_id:
            json['service_id'] = journey.service_id
        elif journey.route_name:
            json['service'] = {
                'line_name': journey.route_name
            }

        if self.seated_occupancy is not None and self.seated_capacity is not None:
            if self.occupancy == 'full':
                json['seats'] = self.occupancy
            else:
                json['seats'] = f'{self.seated_capacity - self.seated_occupancy} free'
        elif self.occupancy:
            json['seats'] = self.get_occupancy_display()
        if self.wheelchair_occupancy is not None and self.wheelchair_capacity:
            if self.wheelchair_occupancy < self.wheelchair_capacity:
                json['wheelchair'] = 'free'
            else:
                json['wheelchair'] = 'occupied'

        return json
