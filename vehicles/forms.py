from django import forms
from .models import VehicleType


class EditVehiclesForm(forms.Form):
    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects, label='Type', required=False)
    colours = forms.ChoiceField(widget=forms.RadioSelect, required=False)
    branding = forms.CharField(label='Branding', required=False)
    notes = forms.CharField(label='Notes', required=False)

    def __init__(self, *args, **kwargs):
        self.vehicle = kwargs.pop('vehicle', None)
        super().__init__(*args, **kwargs)
        self.fields['colours'].choices = self.vehicle.get_livery_choices()


class EditVehicleForm(EditVehiclesForm):
    fleet_number = forms.IntegerField(label='Fleet number', required=False, min_value=0)
    reg = forms.CharField(label='Registration', required=False)
    name = forms.CharField(label='Name', required=False)

    field_order = ['fleet_number', 'reg', 'vehicle_type', 'colours', 'branding', 'name', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.vehicle.code == str(self.vehicle.fleet_number):
            self.fields['fleet_number'].disabled = True
