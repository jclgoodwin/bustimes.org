from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import format_html
from django.db.models import Q, Exists, OuterRef
from django.db.utils import ConnectionDoesNotExist
from django.contrib.auth import get_user_model

from sql_util.utils import SubqueryCount

from busstops.models import Operator
from . import models

UserModel = get_user_model()


@admin.register(models.VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('id', 'name', 'vehicles', 'double_decker', 'coach')
    list_editable = ('name', 'double_decker', 'coach')
    actions = ['merge']

    def vehicles(self, obj):
        return obj.vehicles
    vehicles.admin_order_field = 'vehicles'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if 'changelist' in request.resolver_match.view_name:
            return queryset.annotate(vehicles=SubqueryCount('vehicle'))
        return queryset

    def merge(self, request, queryset):
        first = queryset[0]
        models.Vehicle.objects.filter(vehicle_type__in=queryset).update(vehicle_type=first)
        models.VehicleRevision.objects.filter(from_type__in=queryset).update(from_type=first)
        models.VehicleRevision.objects.filter(to_type__in=queryset).update(to_type=first)


class VehicleAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            'fleet_number': forms.TextInput(attrs={'style': 'width: 4em'}),
            'fleet_code': forms.TextInput(attrs={'style': 'width: 4em'}),
            'reg': forms.TextInput(attrs={'style': 'width: 8em'}),
            'operator': forms.TextInput(attrs={'style': 'width: 4em'}),
            'branding': forms.TextInput(attrs={'style': 'width: 8em'}),
            'name': forms.TextInput(attrs={'style': 'width: 8em'}),
        }


def user(obj):
    return format_html(
        '<a href="{}">{}</a>',
        reverse('admin:accounts_user_change', args=(obj.user_id,)),
        obj.user
    )


class VehicleEditInline(admin.TabularInline):
    model = models.VehicleEdit
    fields = ['approved', 'datetime', 'fleet_number', 'reg', 'vehicle_type', 'livery_id', 'colours', 'branding',
              'notes', 'changes', user]
    readonly_fields = fields[1:]
    show_change_link = True


class DuplicateVehicleFilter(admin.SimpleListFilter):
    title = 'duplicate'
    parameter_name = 'duplicate'

    def lookups(self, request, model_admin):
        return (
            ('reg', 'same reg'),
            ('operator', 'same reg and operator'),
        )

    def queryset(self, request, queryset):
        if self.value():
            vehicles = models.Vehicle.objects.filter(~Q(id=OuterRef('id')), reg=OuterRef('reg'))
            if self.value() == 'operator':
                vehicles = vehicles.filter(operator=OuterRef('operator'))
            queryset = queryset.filter(~Q(reg=''), Exists(vehicles))

        return queryset


@admin.register(models.Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('code', 'fleet_number', 'fleet_code', 'reg', 'operator', 'vehicle_type',
                    'get_flickr_link', 'withdrawn', 'last_seen', 'livery', 'colours', 'branding', 'name', 'notes', 'data')
    list_filter = (
        DuplicateVehicleFilter,
        'withdrawn',
        'features',
        'vehicle_type',
        ('source', admin.RelatedOnlyFieldListFilter),
        ('operator', admin.RelatedOnlyFieldListFilter),
    )
    list_select_related = ['operator', 'livery', 'vehicle_type', 'latest_journey']
    list_editable = ('fleet_number', 'fleet_code', 'reg', 'operator',
                     'branding', 'name', 'notes')
    autocomplete_fields = ('vehicle_type', 'livery')
    raw_id_fields = ('operator', 'source')
    search_fields = ('code', 'fleet_code', 'reg')
    ordering = ('-id',)
    actions = ('copy_livery', 'copy_type', 'make_livery', 'merge', 'spare_ticket_machine')
    inlines = [VehicleEditInline]
    readonly_fields = ['latest_journey_data']

    def latest_journey_data(self, obj):
        if obj.latest_journey:
            return obj.latest_journey.data

    def copy_livery(self, request, queryset):
        livery = models.Livery.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(livery=livery)
        self.message_user(request, f'Copied {livery} to {count} vehicles.')

    def copy_type(self, request, queryset):
        vehicle_type = models.VehicleType.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(vehicle_type=vehicle_type)
        self.message_user(request, f'Copied {vehicle_type} to {count} vehicles.')

    def make_livery(self, request, queryset):
        vehicle = queryset.first()
        if vehicle.colours and vehicle.branding:
            livery = models.Livery.objects.create(name=vehicle.branding, colours=vehicle.colours)
            vehicles = models.Vehicle.objects.filter(colours=vehicle.colours, branding=vehicle.branding)
            count = vehicles.update(colours='', branding='', livery=livery)
            self.message_user(request, f'Updated {count} vehicles.')
        else:
            self.message_user(request, 'Select a vehicle with colours and branding.')

    def merge(self, request, queryset):
        first = None
        for vehicle in queryset.order_by('id'):
            if not first:
                first = vehicle
            else:
                vehicle.vehiclejourney_set.update(vehicle=first)
                first.latest_location = vehicle.latest_location
                first.latest_journey = vehicle.latest_journey
                vehicle.latest_location = None
                vehicle.latest_journey = None
                vehicle.save(update_fields=['latest_location', 'latest_journey'])
                first.save(update_fields=['latest_location', 'latest_journey'])
                first.code = vehicle.code
                first.fleet_code = vehicle.fleet_code
                first.fleet_number = vehicle.fleet_number
                first.reg = vehicle.reg
                vehicle.delete()
                first.save(update_fields=['code', 'fleet_code', 'fleet_number', 'reg'])

    def spare_ticket_machine(self, request, queryset):
        queryset.update(
            reg='', fleet_code='', fleet_number=None, name='', colours='',
            livery=None, branding='', vehicle_type=None, notes='Spare ticket machine',
        )

    def last_seen(self, obj):
        if obj.latest_journey:
            return obj.latest_journey.datetime
    last_seen.admin_order_field = 'latest_journey__datetime'

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', VehicleAdminForm)
        return super().get_changelist_form(request, **kwargs)


def vehicle(obj):
    url = reverse('admin:vehicles_vehicle_change', args=(obj.vehicle_id,))
    return format_html('<a href="{}">{}</a>', url, obj.vehicle)


def fleet_number(obj):
    return obj.get_diff('fleet_number')


fleet_number.short_description = 'no'


def reg(obj):
    return obj.get_diff('reg')


def vehicle_type(obj):
    return obj.get_diff('vehicle_type')


vehicle_type.short_description = 'type'


def branding(obj):
    return obj.get_diff('branding')


branding.short_description = 'brand'


def name(obj):
    return obj.get_diff('name')


def notes(obj):
    return obj.get_diff('notes')


def features(edit):
    features = []
    vehicle = edit.vehicle
    changed_features = edit.vehicleeditfeature_set.all()
    for feature in changed_features:
        if feature.add:
            if feature.feature in vehicle.features.all():
                features.append(str(feature.feature))  # vehicle already has feature
            else:
                features.append(str(feature))
        elif feature.feature in vehicle.features.all():
            features.append(str(feature))
    for feature in vehicle.features.all():
        if not any(feature.id == edit_feature.feature_id for edit_feature in changed_features):
            features.append(str(feature))

    return mark_safe(', '.join(features))


def changes(obj):
    changes = []
    if obj.changes:
        for key, value in obj.changes.items():
            if not obj.vehicle.data or key not in obj.vehicle.data:
                changes.append(f'{key}: <ins>{value}</ins>')
            elif value != obj.vehicle.data[key]:
                changes.append(f'{key}: <del>{obj.vehicle.data[key]}</del> <ins>{value}</ins>')
    if obj.vehicle.data:
        for key, value in obj.vehicle.data.items():
            if not obj.changes or key not in obj.changes:
                changes.append(f'{key}: {value}')
    return mark_safe('<br>'.join(changes))


def url(obj):
    if obj.url:
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.url, obj.url)


vehicle.admin_order_field = 'vehicle'
reg.admin_order_field = 'vehicle__reg'
vehicle_type.admin_order_field = 'vehicle_type'
branding.admin_order_field = 'branding'
name.admin_order_field = 'name'
notes.admin_order_field = 'notes'
changes.admin_order_field = 'changes'
user.admin_order_field = 'user'
url.admin_order_field = 'url'


class OperatorFilter(admin.SimpleListFilter):
    title = 'operator'
    parameter_name = 'operator'

    def lookups(self, request, model_admin):
        operators = Operator.objects.annotate(
            count=SubqueryCount('vehicle__vehicleedit', filter=Q(approved=None))
        ).filter(count__gt=0).order_by('-count')
        try:
            operators = list(operators.using('read-only-0'))
        except ConnectionDoesNotExist:
            pass
        for operator in operators:
            yield (operator.pk, f'{operator} ({operator.count})')

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(vehicle__operator=self.value())
        return queryset


class ChangeFilter(admin.SimpleListFilter):
    title = 'changed field'
    parameter_name = 'change'
    vehicle_features = None

    def lookups(self, request, model_admin):
        self.vehicle_features = [
            feature.name for feature in models.VehicleFeature.objects.all()
        ]
        return [
            ('fleet_number', 'fleet number'),
            ('reg', 'reg'),
            ('vehicle_type', 'type'),
            ('colours', 'colours'),
            ('branding', 'branding'),
            ('name', 'name'),
            ('notes', 'notes'),
            ('withdrawn', 'withdrawn'),
            ('changes__Previous reg', 'previous reg'),
        ] + [
            (feature, feature) for feature in self.vehicle_features
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            if value == 'colours':
                return queryset.filter(~Q(colours='') | Q(livery__isnull=False))
            if value in self.vehicle_features:
                return queryset.filter(vehicleeditfeature__feature__name=value)
            if value.startswith('changes__'):
                return queryset.filter(**{f'{value}__isnull': False})
            return queryset.filter(~Q(**{value: ''}))
        return queryset


class UrlFilter(admin.SimpleListFilter):
    title = 'URL'
    parameter_name = 'url'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.exclude(url='')
        return queryset


class UserFilter(admin.SimpleListFilter):
    title = 'user'
    parameter_name = 'user'

    def lookups(self, request, model_admin):
        lookups = [
            ('Trusted', 'Trusted')
        ]
        if self.value() and self.value() != 'Trusted':
            lookups.append((self.value(), self.value()))
        return lookups

    def queryset(self, request, queryset):
        if self.value():
            if self.value() == 'Trusted':
                return queryset.filter(user__trusted=True)
            return queryset.filter(user=self.value())
        return queryset


@admin.register(models.VehicleEdit)
class VehicleEditAdmin(admin.ModelAdmin):
    list_display = ['datetime', vehicle, 'edit_count', 'last_seen', fleet_number, reg, vehicle_type, branding, name,
                    'current', 'suggested', notes, 'withdrawn', features, changes, 'flickr', user, url]
    list_select_related = ['vehicle__vehicle_type', 'vehicle__livery', 'vehicle__operator', 'vehicle__latest_journey',
                           'livery', 'user']
    list_filter = [
        'approved',
        UrlFilter,
        'vehicle__withdrawn',
        ChangeFilter,
        OperatorFilter,
        UserFilter,
    ]
    raw_id_fields = ['vehicle', 'livery', 'user']
    actions = ['apply_edits', 'approve', 'disapprove', 'delete_vehicles', 'spare_ticket_machine']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if 'changelist' in request.resolver_match.view_name:
            edit_count = SubqueryCount('vehicle__vehicleedit', filter=Q(approved=None))
            queryset = queryset.annotate(edit_count=edit_count)
            return queryset.prefetch_related('vehicleeditfeature_set__feature', 'vehicle__features')
        return queryset

    def apply_edits(self, request, queryset):
        for edit in queryset.prefetch_related('vehicleeditfeature_set__feature', 'vehicle__features'):
            edit.apply()
        self.message_user(request, 'Applied edits.')

    def approve(self, request, queryset):
        count = queryset.order_by().update(approved=True)
        self.message_user(request, f'Approved {count} edits.')

    def disapprove(self, request, queryset):
        count = queryset.order_by().update(approved=False)
        self.message_user(request, f'Disapproved {count} edits.')

    def delete_vehicles(self, request, queryset):
        models.Vehicle.objects.filter(vehicleedit__in=queryset).delete()

    def spare_ticket_machine(self, request, queryset):
        queryset = models.Vehicle.objects.filter(vehicleedit__in=queryset)
        VehicleAdmin.spare_ticket_machine(self, request, queryset)

    def current(self, obj):
        return self.suggested(obj.vehicle)
    current.admin_order_field = 'vehicle__livery'

    def suggested(self, obj):
        if obj.livery:
            return obj.livery.preview()
        if obj.colours:
            return models.Livery(colours=obj.colours).preview()
    suggested.admin_order_field = 'livery'

    def flickr(self, obj):
        return obj.vehicle.get_flickr_link()

    def edit_count(self, obj):
        return obj.edit_count
    edit_count.admin_order_field = 'edit_count'
    edit_count.short_description = 'edits'

    def last_seen(self, obj):
        if obj.vehicle.latest_journey:
            return obj.vehicle.latest_journey.datetime
    last_seen.admin_order_field = 'vehicle__latest_journey__datetime'
    last_seen.short_description = 'seen'


@admin.register(models.VehicleJourney)
class VehicleJourneyAdmin(admin.ModelAdmin):
    list_display = ('datetime', 'code', 'vehicle', 'route_name', 'service', 'destination')
    list_select_related = ('vehicle', 'service')
    raw_id_fields = ('vehicle', 'service', 'source', 'trip')
    list_filter = (
        ('service', admin.EmptyFieldListFilter),
        ('trip', admin.EmptyFieldListFilter),
        'source',
        'vehicle__operator',
    )
    show_full_result_count = False
    ordering = ('-id',)


@admin.register(models.VehicleLocation)
class VehicleLocationAdmin(admin.ModelAdmin):
    raw_id_fields = ['journey']
    list_display = ['datetime', '__str__']
    list_select_related = ['journey']
    list_filter = [
        'occupancy',
        ('journey__source', admin.RelatedOnlyFieldListFilter),
    ]


@admin.register(models.JourneyCode)
class JourneyCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'service', 'destination']
    list_select_related = ['service']
    list_filter = [
        ('data_source', admin.RelatedOnlyFieldListFilter),
        ('siri_source', admin.RelatedOnlyFieldListFilter),
    ]
    raw_id_fields = ['service', 'data_source']


class LiveryAdminForm(forms.ModelForm):
    save_as = True

    class Meta:
        widgets = {
            'colours': forms.Textarea,
            'css': forms.Textarea,
            'left_css': forms.Textarea,
            'right_css': forms.Textarea,
        }


@admin.register(models.Livery)
class LiveryAdmin(admin.ModelAdmin):
    form = LiveryAdminForm
    search_fields = ['name']
    list_display = ['id', 'name', 'vehicles', 'left', 'right', 'white_text']
    actions = ['duplicate']

    def right(self, obj):
        if obj.right_css:
            return format_html('<div style="height:1.5em;width:2.25em;background:{}"></div>', obj.right_css)
    right.admin_order_field = 'right_css'

    def left(self, obj):
        if obj.left_css:
            return format_html('<div style="height:1.5em;width:2.25em;background:{}"></div>', obj.left_css)
    left.admin_order_field = 'left_css'

    vehicles = VehicleTypeAdmin.vehicles

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if 'changelist' in request.resolver_match.view_name:
            return queryset.annotate(vehicles=SubqueryCount('vehicle'))
        return queryset

    def duplicate(self, request, queryset):
        for livery in queryset:
            livery.pk = None
            livery.save()


class RevisionChangeFilter(admin.SimpleListFilter):
    title = 'changed field'
    parameter_name = 'change'

    def lookups(self, request, model_admin):
        return (
            ('changes__reg', 'reg'),
            ('changes__name', 'name'),
            ('changes__branding', 'branding'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value and value.startswith('changes__'):
            return queryset.filter(**{f'{value}__isnull': False})
        return queryset


@admin.register(models.VehicleRevision)
class VehicleRevisionAdmin(admin.ModelAdmin):
    raw_id_fields = ['from_operator', 'to_operator', 'from_livery', 'to_livery', 'vehicle', 'user']
    list_display = ['datetime', 'vehicle', '__str__', user]
    actions = ['revert']
    list_filter = [
        RevisionChangeFilter,
        UserFilter,
        ('vehicle__operator', admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ['from_operator', 'to_operator', 'vehicle', 'user']

    def revert(self, request, queryset):
        for revision in queryset.prefetch_related('vehicle'):
            for message in revision.revert():
                self.message_user(request, message)


admin.site.register(models.VehicleFeature)
