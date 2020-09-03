import requests
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Exists, OuterRef
from busstops.models import Operator, Service
from .models import VehicleType, VehicleFeature, Livery
from .fields import RegField


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
    branding = forms.CharField(label="Other branding", required=False, max_length=255)
    features = forms.ModelMultipleChoiceField(queryset=VehicleFeature.objects, label='Features',
                                              widget=forms.CheckboxSelectMultiple, required=False)
    depot = forms.CharField(help_text="""I’d leave this blank if I were you. There are better places (not this website) for such
minutae""", required=False, max_length=255, widget=forms.TextInput(attrs={"list": "depots"}))
    notes = forms.CharField(help_text="""Again, this should be blank in almost all cases. There’s no need to know a
vehicle’s previous owners""", required=False, max_length=255)
    withdrawn = forms.BooleanField(label='Permanently withdrawn', required=False)
    user = forms.CharField(label='Your name', required=False, max_length=255)

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
        return self.cleaned_data['other_colour']

    def has_really_changed(self):
        if not self.has_changed():
            return False
        if all(key == 'user' or key == 'url' for key in self.changed_data):
            return False
        return True

    def __init__(self, *args, **kwargs):
        operator = kwargs.pop('operator', None)

        super().__init__(*args, **kwargs)

        if operator:
            self.fields['colours'].choices = get_livery_choices(operator)

        operators = None
        if operator and operator.parent:
            services = Service.objects.filter(current=True, operator=OuterRef('pk')).only('id')
            operators = Operator.objects.filter(Exists(services) | Q(pk=operator.pk), parent=operator.parent)
            self.fields['operator'].queryset = operators
        else:
            del(self.fields['operator'])


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle
    """
    fleet_number = forms.CharField(required=False, max_length=14)
    reg = RegField(label='Registration', required=False, max_length=14)
    name = forms.CharField(label='Name', required=False, max_length=255)
    previous_reg = RegField(required=False, max_length=14)
    url = forms.URLField(label='URL', help_text='Link to a web page or photo showing changes',
                         required=False, max_length=255)
    field_order = ['operator', 'fleet_number', 'reg', 'vehicle_type', 'colours', 'other_colour', 'branding', 'name',
                   'previous_reg', 'features', 'depot', 'notes']

    def __init__(self, *args, **kwargs):
        vehicle = kwargs.pop('vehicle', None)

        super().__init__(*args, **kwargs)

        if str(vehicle.fleet_number) in vehicle.code:
            self.fields['fleet_number'].disabled = True
        if vehicle.reg and vehicle.reg in vehicle.code.replace('_', '').replace(' ', '').replace('-', ''):
            self.fields['reg'].disabled = True

        # if not vehicle.notes:
        #     del self.fields['notes']
        #     if not vehicle.data or 'Depot' not in vehicle.data:
        #         del self.fields['depot']
        #     if not vehicle.name:
        #         del self.fields['name']
        #     if not vehicle.branding:
        #         self.fields['branding'].disabled = True
