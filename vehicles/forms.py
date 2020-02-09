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
    for vehicle in operator.vehicle_set.exclude(colours='').distinct('colours'):
        choices[vehicle.colours] = Livery(colours=vehicle.colours, name=f'Like {vehicle}')
    choices = [(key, livery.preview(name=True)) for key, livery in choices.items()]
    choices.append(('Other', 'Other'))
    return choices


class EditVehiclesForm(forms.Form):
    operator = forms.ModelChoiceField(queryset=None, label='Operator', empty_label='')
    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects, label='Type', required=False, empty_label='')
    colours = forms.ChoiceField(label='Livery', widget=forms.RadioSelect, required=False)
    branding = forms.CharField(required=False, max_length=255)
    notes = forms.CharField(required=False, max_length=255)
    features = forms.ModelMultipleChoiceField(queryset=VehicleFeature.objects, label='Features',
                                              widget=forms.CheckboxSelectMultiple, required=False)
    depot = forms.CharField(help_text="""Probably best left blank, especially if there\'s only one depot, or buses regularly move
                                         between depots""", required=False, max_length=255)
    withdrawn = forms.BooleanField(label='Permanently withdrawn', required=False)
    user = forms.CharField(label='Your name', help_text='If left blank, your IP address will be logged instead',
                           required=False, max_length=255)

    def clean_url(self):
        if self.cleaned_data['url']:
            response = requests.get(self.cleaned_data['url'])
            if not response.ok:
                raise ValidationError('That URL doesn’t work for me. Maybe it’s too long, or Facebook')

    def __init__(self, *args, **kwargs):
        features_column = kwargs.pop('features_column', None)
        columns = kwargs.pop('columns', None)
        operator = kwargs.pop('operator', None)

        super().__init__(*args, **kwargs)

        if not features_column:
            del self.fields['features']

        if 'Depot' not in columns:
            del self.fields['depot']

        if operator:
            self.fields['colours'].choices = get_livery_choices(operator)

        operators = None
        if operator and operator.parent:
            operators = Operator.objects.filter(parent=operator.parent)
            self.fields['operator'].queryset = operators.order_by('name').distinct()
        else:
            del(self.fields['operator'])


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle
    """
    fleet_number = forms.CharField(required=False, max_length=14)
    reg = forms.CharField(label='Registration', required=False, max_length=14)
    name = forms.CharField(label='Name', required=False, max_length=255)
    previous_reg = forms.CharField(required=False, max_length=14)
    url = forms.URLField(label='URL', help_text='E.g. a photo (helpful for verifying recent repaints)',
                         required=False, max_length=200)
    field_order = ['operator', 'fleet_number', 'reg', 'vehicle_type',
                   'colours', 'branding', 'name', 'previous_reg', 'depot',
                   'notes', 'url']

    def __init__(self, *args, **kwargs):
        vehicle = kwargs.pop('vehicle', None)

        super().__init__(*args, **kwargs, features_column=vehicle.features.all(),
                         columns=vehicle.data and vehicle.data.keys() or ())

        if str(vehicle.fleet_number) in vehicle.code:
            self.fields['fleet_number'].disabled = True
