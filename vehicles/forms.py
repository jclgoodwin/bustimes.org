import requests
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count
from busstops.models import Operator
from .models import VehicleType, VehicleFeature, Livery


def get_livery_choices(operator):
    choices = {}
    liveries = Livery.objects.filter(vehicle__operator=operator).annotate(popularity=Count('vehicle'))
    for livery in liveries.order_by('-popularity').distinct():
        choices[livery.id] = livery
    for vehicle in operator.vehicle_set.distinct('colours'):
        if not vehicle.livery_id and vehicle.colours and vehicle.colours != 'Other':
            choices[vehicle.colours] = Livery(colours=vehicle.colours, name=f'Like {vehicle}')
    choices = [(key, livery.preview(name=True)) for key, livery in choices.items()]
    choices.append(('Other', 'Other'))
    return choices


class EditVehiclesForm(forms.Form):
    operator = forms.ModelChoiceField(queryset=None, label='Operator', empty_label='')
    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects, label='Type', required=False, empty_label='')
    colours = forms.ChoiceField(label='Livery', widget=forms.RadioSelect, required=False)
    other_colour = forms.CharField(widget=forms.TextInput(attrs={"type": "color"}), required=False)
    branding = forms.CharField(required=False, max_length=255)
    notes = forms.CharField(required=False, max_length=255)
    features = forms.ModelMultipleChoiceField(queryset=VehicleFeature.objects, label='Features',
                                              widget=forms.CheckboxSelectMultiple, required=False)
    depot = forms.CharField(help_text="Best left blank if this changes frequently",
                            required=False, max_length=255,
                            widget=forms.TextInput(attrs={"list": "depots"}))
    withdrawn = forms.BooleanField(label='Permanently withdrawn', required=False)
    user = forms.CharField(label='Your name', help_text='If left blank, your IP address will be logged instead',
                           required=False, max_length=255)

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
            if self.cleaned_data['colours'] != 'Other':
                self.cleaned_data['other_colour'] = ''

    def __init__(self, *args, **kwargs):
        operator = kwargs.pop('operator', None)

        super().__init__(*args, **kwargs)

        if operator:
            self.fields['colours'].choices = get_livery_choices(operator)

        operators = None
        if operator and operator.parent:
            operators = Operator.objects.filter(parent=operator.parent, service__current=True)
            self.fields['operator'].queryset = operators.distinct().order_by('name')
        else:
            del(self.fields['operator'])


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle
    """
    fleet_number = forms.CharField(required=False, max_length=14)
    reg = forms.CharField(label='Registration', required=False, max_length=14)
    name = forms.CharField(label='Name', required=False, max_length=255)
    previous_reg = forms.CharField(required=False, max_length=14)
    url = forms.URLField(label='URL', help_text='Link to a web page or photo (helpful for verifying recent repaints)',
                         required=False, max_length=255)
    field_order = ['operator', 'fleet_number', 'reg', 'vehicle_type',
                   'colours', 'other_colour', 'branding', 'name', 'previous_reg', 'depot',
                   'notes', 'url']

    def __init__(self, *args, **kwargs):
        vehicle = kwargs.pop('vehicle', None)

        super().__init__(*args, **kwargs)

        if str(vehicle.fleet_number) in vehicle.code:
            self.fields['fleet_number'].disabled = True
