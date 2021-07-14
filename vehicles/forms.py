import requests
from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Count, Q, Exists, OuterRef
from busstops.models import Operator, Service
from .models import VehicleType, VehicleFeature, Livery, Vehicle, get_text_colour
from .fields import RegField


def get_livery_choices(operator):
    choices = {}
    vehicles = operator.vehicle_set.filter(withdrawn=False)
    liveries = Livery.objects.filter(vehicle__in=vehicles).annotate(popularity=Count('vehicle'))
    for livery in liveries.order_by('-popularity').distinct():
        choices[livery.id] = livery
    for vehicle in vehicles.distinct('colours'):
        if not vehicle.livery_id and vehicle.colours and vehicle.colours != 'Other':
            choices[vehicle.colours] = Livery(colours=vehicle.colours, name=f'Like {vehicle}')
    choices = [(key, livery.preview(name=True)) for key, livery in choices.items()]
    if choices:
        choices.append(('Other', 'Other'))
    return choices


class EditVehiclesForm(forms.Form):
    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects, label='Type', required=False, empty_label='')
    colours = forms.ChoiceField(label='Livery', widget=forms.RadioSelect, required=False)
    other_colour = forms.CharField(widget=forms.TextInput(attrs={"type": "color"}), required=False, initial='#ffffff')
    features = forms.ModelMultipleChoiceField(queryset=VehicleFeature.objects, label='Features',
                                              widget=forms.CheckboxSelectMultiple, required=False)
    withdrawn = forms.BooleanField(label='Permanently withdrawn', required=False, help_text="Will be automatically "
                                   "unticked the next time this vehicle (or a ticket machine purportedly in it) tracks")

    def clean_url(self):
        if self.cleaned_data['url']:
            try:
                response = requests.get(self.cleaned_data['url'], timeout=5)
                if response.ok:
                    return self.cleaned_data['url']
            except requests.RequestException:
                pass
            raise ValidationError('That URL doesn’t work for me. Maybe it’s too long, or Facebook')

    def clean_other_colour(self):
        if self.cleaned_data['other_colour']:
            if self.cleaned_data.get('colours') != 'Other':
                return
            try:
                get_text_colour(self.cleaned_data['other_colour'])
            except ValueError as e:
                raise ValidationError(str(e))

        return self.cleaned_data['other_colour']

    def has_really_changed(self):
        if not self.has_changed():
            return False
        for key in self.changed_data:
            if all(key == 'url' or key == 'other_colour' for key in self.changed_data):
                if not self.data.get('other_colour'):
                    return False
        return True

    def __init__(self, *args, operator=None, user, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)

        colours = None

        if operator:
            colours = get_livery_choices(operator)

        if colours:
            if vehicle:
                colours = [('', 'None/mostly white/other')] + colours
            else:
                colours = [('', 'No change')] + colours
            self.fields['colours'].choices = colours
        else:
            del self.fields['colours']
            del self.fields['other_colour']


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle
    """
    fleet_number = forms.CharField(required=False, max_length=24)
    reg = RegField(label='Number plate', required=False, max_length=24)
    operator = forms.ModelChoiceField(queryset=None, label='Operator', empty_label='')
    branding = forms.CharField(label="Other branding", required=False, max_length=255)
    name = forms.CharField(label='Vehicle name', required=False, max_length=70)
    previous_reg = RegField(required=False, max_length=24)
    notes = forms.CharField(required=False, max_length=255)
    url = forms.URLField(label='URL', help_text="Optional link to a public web page (not a private Facebook group)"
                         " or picture confirming changes", required=False, max_length=255)
    field_order = ['fleet_number', 'reg', 'operator', 'vehicle_type', 'colours', 'other_colour', 'branding', 'name',
                   'previous_reg', 'features', 'notes']

    def __init__(self, *args, user, vehicle, **kwargs):
        super().__init__(*args, **kwargs, user=user, vehicle=vehicle)

        if vehicle.fleet_code and vehicle.fleet_code in vehicle.code or str(vehicle.fleet_number) in vehicle.code:
            self.fields['fleet_number'].disabled = True
        elif vehicle.fleet_code and vehicle.latest_journey and vehicle.latest_journey.data:
            try:
                if vehicle.latest_journey.data['Extensions']['VehicleJourney']['VehicleUniqueId'] == vehicle.fleet_code:
                    if not vehicle.code.isdigit() or vehicle.code == vehicle.fleet_code:
                        self.fields['fleet_number'].disabled = True
            except KeyError:
                pass

        if not vehicle.withdrawn and vehicle.latest_journey:
            if timezone.now() - vehicle.latest_journey.datetime < timedelta(days=3):
                self.fields['withdrawn'].disabled = True
                self.fields['withdrawn'].help_text = """Can't be ticked yet, as this vehicle (or ticket machine) has 
tracked in the last 3 days"""

        if vehicle.reg and vehicle.reg in vehicle.code.replace('_', '').replace(' ', '').replace('-', ''):
            self.fields['reg'].disabled = True

        if not user.is_staff:
            if not vehicle.notes:
                del self.fields['notes']
            if not vehicle.branding:
                del self.fields['branding']

        if not vehicle.operator or vehicle.operator.parent:
            operators = Operator.objects
            if user.trusted and vehicle.operator:
                # any sibling operator
                operators = operators.filter(parent=vehicle.operator.parent)
                condition = Exists(Service.objects.filter(current=True, operator=OuterRef('pk')).only('id'))
                condition |= Exists(Vehicle.objects.filter(operator=OuterRef('pk')).only('id'))
            elif vehicle.latest_journey:
                # only operators whose services the vehicle has operated
                condition = Exists(
                    Service.objects.filter(
                        operator=OuterRef('pk'),
                        id=vehicle.latest_journey.service_id
                    )
                )
            else:
                del self.fields['operator']
                return
            if vehicle.operator:
                condition |= Q(pk=vehicle.operator_id)
            self.fields['operator'].queryset = operators.filter(condition)
        else:
            del self.fields['operator']
