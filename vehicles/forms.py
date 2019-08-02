from django import forms


class EditVehicleForm(forms.Form):
    fleet_number = forms.CharField(label='Fleet number', required=False)
    reg = forms.CharField(label='Registration', required=False)
    vehicle_type = forms.CharField(label='Type', required=False)
    colours = forms.CharField(label='Colours', required=False)
    notes = forms.CharField(label='Notes', required=False)
