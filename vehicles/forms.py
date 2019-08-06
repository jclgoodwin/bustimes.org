from django import forms


class EditVehicleForm(forms.Form):
    fleet_number = forms.IntegerField(label='Fleet number', required=False, localize=True, min_value=0)
    reg = forms.CharField(label='Registration', required=False)
    vehicle_type = forms.CharField(label='Type', required=False)
    colours = forms.ChoiceField(widget=forms.RadioSelect, required=False)
    notes = forms.CharField(label='Notes', required=False)

    def __init__(self, *args, **kwargs):
        self.vehicle = kwargs.pop('vehicle', None)
        super().__init__(*args, **kwargs)
        self.fields['colours'].choices = self.vehicle.get_livery_choices()
