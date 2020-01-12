from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q
from django.db.utils import ConnectionDoesNotExist
from busstops.models import Operator
from .models import VehicleType, VehicleFeature, Vehicle, VehicleEdit, VehicleJourney, Livery, JourneyCode


class VehicleTypeAdmin(admin.ModelAdmin):
    search_fields = ('name',)
    list_display = ('name', 'double_decker', 'coach')
    list_editable = list_display[1:]


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


class VehicleAdmin(admin.ModelAdmin):
    list_display = ('code', 'fleet_number', 'fleet_code', 'reg', 'operator', 'vehicle_type',
                    'get_flickr_link', 'last_seen', 'livery', 'colours', 'branding', 'name', 'notes', 'data')
    list_filter = (
        'withdrawn',
        ('source', admin.RelatedOnlyFieldListFilter),
        ('operator', admin.RelatedOnlyFieldListFilter),
        'livery',
        'vehicle_type',
    )
    list_select_related = ['operator', 'livery', 'vehicle_type', 'latest_location']
    list_editable = ('fleet_number', 'fleet_code', 'reg', 'operator', 'vehicle_type',
                     'livery', 'colours', 'branding', 'name', 'notes')
    autocomplete_fields = ('vehicle_type', 'livery')
    raw_id_fields = ('operator', 'source')
    search_fields = ('code', 'fleet_number', 'reg', 'notes')
    ordering = ('-id',)
    actions = ('copy_livery', 'copy_type')

    def copy_livery(self, request, queryset):
        livery = Livery.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(livery=livery)
        self.message_user(request, f'Copied {livery} to {count} vehicles.')

    def copy_type(self, request, queryset):
        vehicle_type = VehicleType.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(vehicle_type=vehicle_type)
        self.message_user(request, f'Copied {vehicle_type} to {count} vehicles.')

    def last_seen(self, obj):
        if obj.latest_location:
            return obj.latest_location.datetime
    last_seen.admin_order_field = 'latest_location__datetime'

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault('form', VehicleAdminForm)
        return super().get_changelist_form(request, **kwargs)


def vehicle(obj):
    url = reverse('admin:vehicles_vehicle_change', args=(obj.vehicle_id,))
    return mark_safe(f'<a href="{url}">{obj.vehicle}</a>')


def fleet_number(obj):
    return obj.get_diff('fleet_number')


def reg(obj):
    return obj.get_diff('reg')


def vehicle_type(obj):
    return obj.get_diff('vehicle_type')


def branding(obj):
    return obj.get_diff('branding')


def name(obj):
    return obj.get_diff('name')


def notes(obj):
    return obj.get_diff('notes')


def features(obj):
    features = []
    if obj.features.all():
        for feature in obj.features.all():
            if feature in obj.vehicle.features.all():
                features.append(str(feature))
            else:
                features.append(f'<ins>{feature}</ins>')
        for feature in obj.vehicle.features.all():
            if feature not in obj.features.all():
                features.append(f'<del>{feature}</del>')
        return mark_safe(', '.join(features))


def changes(obj):
    changes = []
    if obj.changes:
        for key, value in obj.changes.items():
            if not obj.vehicle.data or key not in obj.vehicle.data:
                changes.append(f'{key}: <ins>{value}</ins>')
            elif value != obj.vehicle.data[key]:
                changes.append(f'{key}: <del>{obj.vehicle.data[key]}</del> <ins>{value}</ins>')
        return mark_safe('<br>'.join(changes))


def url(obj):
    if obj.url:
        return mark_safe(f'<a href="{obj.url}" target="_blank" rel="noopener">{obj.url}</a>')


vehicle.admin_order_field = 'vehicle'
reg.admin_order_field = 'reg'
vehicle_type.admin_order_field = 'vehicle_type'
branding.admin_order_field = 'branding'
name.admin_order_field = 'name'
notes.admin_order_field = 'notes'
changes.admin_order_field = 'changes'


def apply_edits(queryset):
    for edit in queryset.prefetch_related('features', 'vehicle__features'):
        ok = True
        vehicle = edit.vehicle
        update_fields = []
        if edit.withdrawn:
            vehicle.withdrawn = True
            update_fields.append('withdrawn')
        if edit.fleet_number:
            vehicle.fleet_code = edit.fleet_number
            update_fields.append('fleet_code')
            if edit.fleet_number.isdigit():
                vehicle.fleet_number = edit.fleet_number
                update_fields.append('fleet_number')
        if edit.reg:
            vehicle.reg = edit.reg
            update_fields.append('reg')
        if edit.changes:
            if vehicle.data:
                vehicle.data = {
                    **vehicle.data, **edit.changes
                }
            else:
                vehicle.data = edit.changes
            update_fields.append('data')
        for field in ('branding', 'name', 'notes', 'fleet_number'):
            if getattr(edit, field):
                if getattr(edit, field) == f'-{getattr(vehicle, field)}':
                    setattr(vehicle, field, '')
                else:
                    setattr(vehicle, field, getattr(edit, field))
                update_fields.append(field)
        if edit.vehicle_type:
            try:
                vehicle.vehicle_type = VehicleType.objects.get(name__iexact=edit.vehicle_type)
                update_fields.append('vehicle_type')
            except VehicleType.DoesNotExist:
                ok = False
        if edit.livery_id:
            vehicle.livery_id = edit.livery_id
            vehicle.colours = ''
            update_fields.append('livery')
            update_fields.append('colours')
        elif edit.colours and edit.colours != 'Other':
            vehicle.livery = None
            vehicle.colours = edit.colours
            update_fields.append('livery')
            update_fields.append('colours')
        vehicle.save(update_fields=update_fields)
        if edit.features.all():
            vehicle.features.set(edit.features.all())
        if ok:
            edit.approved = True
            edit.save(update_fields=['approved'])


class OperatorFilter(admin.SimpleListFilter):
    title = 'operator'
    parameter_name = 'operator'

    def lookups(self, request, model_admin):
        operators = Operator.objects.filter(vehicle__vehicleedit__approved=False)
        operators = operators.annotate(count=Count('vehicle__vehicleedit')).order_by('-count')
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
        yield ('1', 'Not blank')
        edits = VehicleEdit.objects.filter(~Q(user=''), approved=False)
        for edit in edits.values('user').annotate(count=Count('user')).order_by('-count'):
            yield (edit['user'], f"{edit['user']} ({edit['count']})")

    def queryset(self, request, queryset):
        if self.value():
            if self.value() == '1':
                return queryset.exclude(user='')
            return queryset.filter(user=self.value())
        return queryset


class VehicleEditAdmin(admin.ModelAdmin):
    list_display = ['id', 'datetime', vehicle, fleet_number, reg, vehicle_type, branding, name, 'current', 'suggested',
                    notes, 'withdrawn', features, changes, 'last_seen', 'flickr', 'user', url]
    list_select_related = ['vehicle__vehicle_type', 'vehicle__livery', 'vehicle__operator', 'vehicle__latest_location',
                           'livery']
    list_filter = [
        'approved',
        UrlFilter,
        UserFilter,
        'withdrawn',
        OperatorFilter
    ]
    raw_id_fields = ['vehicle', 'livery']
    actions = ['apply_edits', 'delete_vehicles']

    def get_queryset(self, _):
        return VehicleEdit.objects.all().prefetch_related('features', 'vehicle__features')

    def apply_edits(self, request, queryset):
        apply_edits(queryset)
        self.message_user(request, 'Applied edits.')

    def delete_vehicles(self, request, queryset):
        Vehicle.objects.filter(vehicleedit__in=queryset).delete()

    def current(self, obj):
        if obj.vehicle.livery:
            return obj.vehicle.livery.preview()
        if obj.vehicle.colours:
            return Livery(colours=obj.vehicle.colours).preview()
    current.admin_order_field = 'vehicle__livery'

    def suggested(self, obj):
        if obj.livery:
            return obj.livery.preview()
        if obj.colours:
            if obj.colours == 'Other':
                return obj.colours
            return Livery(colours=obj.colours).preview()
    suggested.admin_order_field = 'livery'

    def flickr(self, obj):
        return obj.vehicle.get_flickr_link()

    def last_seen(self, obj):
        if obj.vehicle.latest_location:
            return obj.vehicle.latest_location.datetime
    last_seen.admin_order_field = 'vehicle__latest_location__datetime'


class ServiceIsNullFilter(admin.SimpleListFilter):
    title = 'service is null'
    parameter_name = 'service__isnull'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Yes'),
            ('0', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(service__isnull=self.value() == '1')
        return queryset


class VehicleJourneyAdmin(admin.ModelAdmin):
    list_display = ('datetime', 'vehicle', 'service', 'route_name', 'code', 'destination')
    list_select_related = ('vehicle', 'service')
    raw_id_fields = ('vehicle', 'service', 'trip')
    list_filter = (
        ServiceIsNullFilter,
        'source',
        'vehicle__operator',
    )
    ordering = ('-id',)


class JourneyCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'service', 'destination']
    list_select_related = ['service']
    raw_id_fields = ['service']


class LiveryAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['name', 'preview']


admin.site.register(VehicleType, VehicleTypeAdmin)
admin.site.register(VehicleFeature)
admin.site.register(Vehicle, VehicleAdmin)
admin.site.register(VehicleEdit, VehicleEditAdmin)
admin.site.register(VehicleJourney, VehicleJourneyAdmin)
admin.site.register(JourneyCode, JourneyCodeAdmin)
admin.site.register(Livery, LiveryAdmin)
