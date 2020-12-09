from django.db.models import Q, Exists, OuterRef
from .models import FareZone, DistanceMatrixElement
from django import forms


class FaresForm(forms.Form):
    origin = forms.ModelChoiceField(FareZone.objects, label="From")
    destination = forms.ModelChoiceField(FareZone.objects, label="To")

    def __init__(self, tariffs, *args, **kwargs):
        self.tariffs = tariffs

        zones = FareZone.objects.filter(
            Exists(
                DistanceMatrixElement.objects.filter(
                    Q(start_zone=OuterRef('pk')) | Q(end_zone=OuterRef('pk')),
                    tariff__in=tariffs
                )
            )
        )

        super().__init__(*args, **kwargs)

        self.fields['origin'].queryset = zones
        self.fields['destination'].queryset = zones

    def get_results(self):
        return DistanceMatrixElement.objects.filter(
            Q(start_zone=self.cleaned_data['origin'], end_zone=self.cleaned_data['destination']) |
            Q(start_zone=self.cleaned_data['destination'], end_zone=self.cleaned_data['origin']),
            tariff__in=self.tariffs
        )
