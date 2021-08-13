import re
from math import ceil
from urllib.parse import quote
from datetime import timedelta
from webcolors import html5_parse_simple_color
from django.conf import settings
from django.contrib.gis.db import models
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import escape, format_html
from busstops.models import Operator, Service, DataSource, SIRISource
from bustimes.models import get_calendars, Trip
import json


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
    fleet_code = models.CharField(max_length=24, blank=True, db_index=True)
    reg = models.CharField(max_length=24, blank=True, db_index=True)
    source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey(VehicleType, models.SET_NULL, null=True, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    branding = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    latest_location = models.OneToOneField('VehicleLocation', models.SET_NULL, null=True, blank=True, editable=False)
    latest_journey = models.OneToOneField(
        'VehicleJourney', models.SET_NULL, null=True, blank=True, editable=False, related_name='latest_vehicle'
    )
    features = models.ManyToManyField(VehicleFeature, blank=True)
    withdrawn = models.BooleanField(default=False)
    data = models.JSONField(null=True, blank=True)
    garage = models.ForeignKey('bustimes.Garage', models.SET_NULL, null=True, blank=True)

    def save(self, *args, update_fields=None, **kwargs):
        if update_fields is None or 'fleet_number' in update_fields:
            if self.fleet_number and (not self.fleet_code or self.fleet_code.isdigit()):
                self.fleet_code = str(self.fleet_number)
                if update_fields and 'fleet_code' not in update_fields:
                    update_fields.append('fleet_code')

        if update_fields is None and not self.reg:
            reg = re.match(r"^[A-Z]\w_?\d\d?[ _-]?[A-Z]{3}$", self.code)
            if reg:
                self.reg = self.code.replace(' ', '').replace('_', '').replace('-', '')
        elif update_fields is None or 'reg' in update_fields:
            self.reg = self.reg.upper().replace(' ', '')

        super().save(*args, update_fields=update_fields, **kwargs)

    class Meta:
        unique_together = ('code', 'operator')

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
        if self.source_id == 7:  # London
            return reverse('tfl_vehicle', args=(self.reg,))
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

    def editable(self):
        if self.notes == 'Spare ticket machine':
            return False
        return True

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
    datetime = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, null=True, blank=True)

    def get_changes(self):
        changes = {}
        for field in ('fleet_number', 'reg', 'vehicle_type', 'branding', 'name', 'notes', 'colours', 'livery'):
            edit = str(getattr(self, field) or '')
            if edit:
                if field == 'reg':
                    edit = edit.upper().replace(' ', '')
                if edit.startswith('-'):
                    edit = ''
                if field == 'fleet_number' and self.vehicle.fleet_code:
                    vehicle = self.vehicle.fleet_code
                else:
                    vehicle = str(getattr(self.vehicle, field) or '')
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
        if self.withdrawn and not self.vehicle.withdrawn:
            changes['withdrawn'] = True
        if self.changes:
            for key in self.changes:
                if not self.vehicle.data or self.changes[key] != self.vehicle.data.get(key):
                    changes[key] = self.changes[key]
        return changes

    def get_diff(self, field):
        original = str(getattr(self.vehicle, field) or '')
        edit = str(getattr(self, field) or '')
        if field == 'reg':
            edit = edit.upper().replace(' ', '')
        elif field == 'fleet_number':
            original = self.vehicle.fleet_code or original
        if original != edit:
            if edit:
                if original:
                    if edit.startswith('-'):
                        if edit == f'-{original}':
                            return format_html('<del>{}</del>', original)
                    else:
                        return format_html('<del>{}</del><br><ins>{}</ins>', original, edit)
                else:
                    return format_html('<ins>{}</ins>', edit)
        return original

    def apply(self, save=True):
        ok = True
        vehicle = self.vehicle
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
            for feature in self.vehicleeditfeature_set.all():
                if feature.add:
                    vehicle.features.add(feature.feature)
                else:
                    vehicle.features.remove(feature.feature)
            if ok:
                self.approved = True
                self.save(update_fields=['approved'])

    def get_absolute_url(self):
        return self.vehicle.get_absolute_url()

    def __str__(self):
        return str(self.id)


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

    def __str__(self):
        return ', '.join(
            f'{key}: {before} → {after}' for key, before, after in self.list_changes()
        )

    def list_changes(self):
        for field in ('operator', 'type', 'livery'):
            if getattr(self, f'from_{field}_id') or getattr(self, f'to_{field}_id'):
                if getattr(__class__, f'from_{field}').is_cached(self):
                    yield (field, getattr(self, f'from_{field}'), getattr(self, f'to_{field}'))
                else:
                    yield (field, getattr(self, f'from_{field}_id'), getattr(self, f'to_{field}_id'))
        if self.changes:
            for key in self.changes:
                before, after = self.changes[key].split('\n+')
                before = before[1:]
                yield (key, before, after)

    def revert(self, message_user=None, request=None):
        vehicle = self.vehicle
        fields = []

        if self.from_operator_id or self.to_operator_id:
            if vehicle.operator_id == self.to_operator_id:
                vehicle.operator_id = self.from_operator_id
                fields.append('operator')

        if self.from_type_id or self.to_type_id:
            if vehicle.vehicle_type_id == self.to_type_id:
                vehicle.vehicle_type_id = self.from_type_id
                fields.append('vehicle_type')

        if self.from_livery_id or self.to_livery_id:
            if vehicle.livery_id == self.to_livery_id:
                vehicle.livery_id = self.from_livery_id
                fields.append('livery')

        if self.changes:
            for key in self.changes:
                before, after = self.changes[key].split('\n+')
                before = before[1:]
                if key == 'reg':
                    if vehicle.reg == after:
                        vehicle.reg = before
                        fields.append('reg')
                elif key == 'name':
                    if vehicle.name == after:
                        vehicle.name = before
                        fields.append('name')
                elif key == 'withdrawn':
                    if vehicle.withdrawn and after == 'Yes':
                        vehicle.withdrawn = False
                        fields.append('withdrawn')
                else:
                    if message_user and request:
                        message_user(request, f'vehicle {vehicle.id} {key} not reverted')
                    else:
                        print(f'vehicle {vehicle.id} {key} not reverted')

        if fields:
            self.vehicle.save(update_fields=fields)
            if message_user and request:
                message_user(request, f'vehicle {vehicle.id} reverted {fields}')
            else:
                print(f'vehicle {vehicle.id} reverted {fields}')


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
    trip = models.ForeignKey('bustimes.Trip', models.DO_NOTHING, db_constraint=False, null=True, blank=True)

    def get_absolute_url(self):
        return f"/vehicles/{self.vehicle_id}?date={self.datetime.date()}#journeys/{self.id}"

    def __str__(self):
        when = self.datetime.strftime('%-d %b %y %H:%M')
        when = f"{when} {self.route_name} {self.code} {self.direction}"
        if self.destination:
            when = f'{when} to {self.destination}'
        return when

    class Meta:
        ordering = ('id',)
        indexes = [
            models.Index('service', TruncDate('datetime').asc(), name='service_datetime_date')
        ]
        unique_together = (
            ('vehicle', 'datetime'),
        )

    @cached_property
    def block(self):
        if not self.data:
            return
        try:
            block_ref = self.data['MonitoredVehicleJourney']['BlockRef']
        except KeyError:
            return
        try:
            driver_ref = self.data['Extensions']['VehicleJourney']['DriverRef']
            if block_ref == driver_ref:
                return
        except KeyError:
            pass
        if block_ref == self.route_name:
            return
        return block_ref

    def get_trip(self, datetime=None, destination_ref=None):
        if not datetime:
            datetime = self.datetime
        trips = Trip.objects.filter(
            Q(route__start_date__lte=datetime) | Q(route__start_date=None),
            Q(route__end_date__gte=datetime) | Q(route__end_date=None),
            route__service=self.service_id
        ).distinct('start', 'end')

        if destination_ref and ' ' not in destination_ref and destination_ref[:3].isdigit():
            destination = Q(destination=destination_ref)
        else:
            destination = None

        if len(self.code) == 4 and self.code.isdigit() and int(self.code) < 2400:
            hours = int(self.code[:-2])
            minutes = int(self.code[-2:])
            start = timedelta(hours=hours, minutes=minutes)
            start = Q(start=start)

            if destination:
                try:
                    return trips.get(start, destination)
                except Trip.MultipleObjectsReturned:
                    try:
                        return trips.get(start, destination, calendar__in=get_calendars(datetime))
                    except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                        return
                except Trip.DoesNotExist:
                    pass
            try:
                return trips.get(start, calendar__in=get_calendars(datetime))
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                return

        try:
            return trips.get(ticket_machine_code=self.code)
        except Trip.MultipleObjectsReturned:
            trips = trips.filter(calendar__in=get_calendars(datetime))
            try:
                return trips.get(ticket_machine_code=self.code)
            except (Trip.DoesNotExist, Trip.MultipleObjectsReturned):
                pass
        except Trip.DoesNotExist:
            pass


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


class Channel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    bounds = models.PolygonField()
    datetime = models.DateTimeField(null=True, blank=True)


class Occupancy(models.TextChoices):
    SEATS_AVAILABLE = 'seatsAvailable', 'Seats available'
    STANDING_AVAILABLE = 'standingAvailable', 'Standing available'
    FULL = 'full', 'Full'


class VehicleLocation(models.Model):
    datetime = models.DateTimeField()
    latlong = models.PointField()
    journey = models.ForeignKey(VehicleJourney, models.CASCADE)
    heading = models.PositiveSmallIntegerField(null=True, blank=True)
    early = models.SmallIntegerField(null=True, blank=True)
    delay = models.SmallIntegerField(null=True, blank=True)
    current = models.BooleanField(default=False)
    occupancy = models.CharField(
        max_length=17,
        choices=Occupancy.choices,
        blank=True
    )
    seated_occupancy = models.PositiveSmallIntegerField(null=True, blank=True)
    seated_capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    wheelchair_occupancy = models.PositiveSmallIntegerField(null=True, blank=True)
    wheelchair_capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    occupancy_thresholds = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.datetime.strftime('%-d %b %Y %H:%M:%S')

    class Meta:
        ordering = ('id',)

    def get_appendage(self):
        appendage = [self.datetime, self.latlong.coords, self.heading, self.early]
        return (f'journey{self.journey_id}', json.dumps(appendage, cls=DjangoJSONEncoder))

    def get_redis_json(self, vehicle):
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
            json['seats'] = f'{self.seated_capacity - self.seated_occupancy} free'
        if self.wheelchair_occupancy is not None and self.wheelchair_capacity is not None:
            if self.wheelchair_occupancy < self.wheelchair_capacity:
                json['wheelchair'] = 'free'

        return json
