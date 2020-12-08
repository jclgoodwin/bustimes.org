from django.db.models import Q, Exists, OuterRef
from .models import FareZone
from django import forms


class FaresForm(forms.Form):
    origin = forms.ModelChoiceField(FareZone.objects, label="From")
    destination = forms.ModelChoiceField(FareZone.objects, label="To")

    def __init__(self, tariff, *args, **kwargs):
        super().__init__(*args, **kwargs)

        zones = FareZone.objects.filter(
            Exists(
                tariff.distancematrixelement_set.filter(Q(start_zone=OuterRef('pk')) | Q(end_zone=OuterRef('pk')))
            )
        )

        self.fields['origin'].queryset = zones
        self.fields['destination'].queryset = zones
