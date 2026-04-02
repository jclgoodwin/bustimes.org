from django.db.models import Q, Exists, OuterRef
from django.db.utils import OperationalError
from django.forms import Form, ChoiceField

from .models import FareZone, DistanceMatrixElement


class FaresForm(Form):
    origin = ChoiceField(label="From")
    destination = ChoiceField(label="To")

    def __init__(self, tariffs, *args, **kwargs):
        self.tariffs = tariffs

        if len(tariffs) == 1:
            distance_matrix_elements = tariffs[0].distancematrixelement_set
        else:
            distance_matrix_elements = DistanceMatrixElement.objects.filter(
                tariff__in=tariffs
            )

        start_zones = FareZone.objects.filter(
            Exists(distance_matrix_elements.filter(start_zone=OuterRef("pk")))
        )
        end_zones = FareZone.objects.filter(
            Exists(distance_matrix_elements.filter(end_zone=OuterRef("pk")))
        )

        super().__init__(*args, **kwargs)

        try:
            if start_zones:
                start_zones = [("", "")] + [
                    (zone.id, str(zone)) for zone in start_zones
                ]
            if end_zones:
                end_zones = [("", "")] + [(zone.id, str(zone)) for zone in end_zones]

            self.fields["origin"].choices = start_zones
            self.fields["destination"].choices = end_zones
        except OperationalError:
            return

    def get_results(self):
        return (
            DistanceMatrixElement.objects.filter(
                Q(
                    start_zone=self.cleaned_data["origin"],
                    end_zone=self.cleaned_data["destination"],
                )
                | Q(
                    start_zone=self.cleaned_data["destination"],
                    end_zone=self.cleaned_data["origin"],
                ),
                tariff__in=self.tariffs,
            )
            .select_related("price", "tariff", "start_zone", "end_zone")
            .order_by("start_zone", "tariff")
        )
