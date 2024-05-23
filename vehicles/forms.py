import re

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

from busstops.models import Operator

from . import fields
from .models import Livery, VehicleFeature, VehicleType, get_text_colour


class EditVehicleForm(forms.Form):
    @property
    def media(self):
        return forms.Media(
            js=(
                "admin/js/vendor/jquery/jquery.min.js",
                "admin/js/vendor/select2/select2.full.min.js",
                "js/edit-vehicle.js",
            ),
            css={
                "screen": ("admin/css/vendor/select2/select2.min.css",),
            },
        )

    field_order = [
        "spare_ticket_machine",
        "withdrawn",
        "fleet_number",
        "reg",
        "operator",
        "vehicle_type",
        "colours",
        "other_colour",
        "branding",
        "name",
        "previous_reg",
        "features",
        "notes",
    ]
    spare_ticket_machine = forms.BooleanField(
        required=False,
        help_text="Only to be used if the ticket machine code is something like SPARE",
    )
    withdrawn = forms.BooleanField(
        label="Remove from list",
        required=False,
        help_text="""Don't feel you need to "tidy up" by removing vehicles you only *think* have been withdrawn""",
    )

    fleet_number = forms.CharField(required=False, max_length=24)
    reg = fields.RegField(label="Number plate", required=False, max_length=24)

    operator = forms.ModelChoiceField(
        queryset=Operator.objects,
        required=False,
        empty_label="",
        widget=forms.TextInput(),
    )

    vehicle_type = forms.ModelChoiceField(
        queryset=VehicleType.objects, required=False, empty_label=""
    )

    colours = forms.ModelChoiceField(
        label="Current livery",
        queryset=Livery.objects,
        required=False,
        help_text="""To avoid arguments, please wait until the bus has *finished being repainted*
(<em>not</em> "in the paint shop" or "awaiting repaint")""",
    )
    other_colour = forms.CharField(
        label="Other colours",
        help_text="E.g. '#c0c0c0 #ff0000 #ff0000' (red with a silver front)",
        required=False,
        max_length=255,
    )

    branding = forms.CharField(
        label="Other branding",
        required=False,
        max_length=40,
    )
    name = forms.CharField(
        label="Vehicle name",
        required=False,
        max_length=40,
    )
    previous_reg = fields.RegField(
        required=False,
        max_length=24,
        help_text="Separate multiple regs with a comma (,)",
    )

    features = forms.ModelMultipleChoiceField(
        queryset=VehicleFeature.objects,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    notes = forms.CharField(required=False, max_length=255)
    summary = fields.SummaryField(
        required=False,
        max_length=255,
        help_text="""Briefly explain your changes,
if they need explaining.
E.g. how you know a vehicle has definitely been withdrawn or repainted,
link to a picture to prove it. Be polite.""",
    )

    def clean_other_colour(self):
        if self.cleaned_data["other_colour"]:
            try:
                get_text_colour(self.cleaned_data["other_colour"])
            except ValueError as e:
                raise ValidationError(str(e))

        return self.cleaned_data["other_colour"]

    def has_really_changed(self):
        if not self.has_changed():
            return False
        for key in self.changed_data:
            if all(
                key == "summary" or key == "other_colour" for key in self.changed_data
            ):
                if not (
                    "other_colour" in self.changed_data
                    and self.data.get("other_colour")
                ):
                    return False
        return True

    def clean_operator(self):
        old = self.initial["operator"]
        new = self.cleaned_data["operator"]
        if old and new and old != new and old.parent == new.parent == "Go South West":
            raise ValidationError("No")
        return new

    def clean_reg(self):
        reg = self.cleaned_data["reg"].replace(".", "")
        if self.cleaned_data["spare_ticket_machine"] and reg:
            raise ValidationError("A spare ticket machine can’t have a number plate")
        return reg

    def __init__(self, *args, user, vehicle, **kwargs):
        super().__init__(*args, **kwargs)

        if vehicle.vehicle_type_id:
            self.fields["vehicle_type"].choices = (
                (vehicle.vehicle_type_id, vehicle.vehicle_type),
            )
        else:
            self.fields["vehicle_type"].choices = ()

        if vehicle.livery_id:
            self.fields["colours"].choices = ((vehicle.livery_id, vehicle.livery),)
        else:
            self.fields["colours"].choices = ()

        if vehicle.vehicle_type_id and not vehicle.is_spare_ticket_machine():
            self.fields["spare_ticket_machine"].disabled = True

        if not user.is_staff and vehicle.fleet_code:
            if vehicle.fleet_code in re.split(r"\W+", vehicle.code):
                self.fields["fleet_number"].disabled = True
                self.fields[
                    "fleet_number"
                ].help_text = f"""The ticket machine code ({vehicle.code})
can’t be contradicted"""
            elif vehicle.latest_journey_data:
                try:
                    vehicle_unique_id = vehicle.latest_journey_data["Extensions"][
                        "VehicleJourney"
                    ]["VehicleUniqueId"]
                except (KeyError, TypeError):
                    pass
                else:
                    if vehicle_unique_id == vehicle.fleet_code:
                        if (
                            not vehicle.code.isdigit()
                            or vehicle.code == vehicle.fleet_code
                        ):
                            self.fields["fleet_number"].disabled = True
                            self.fields[
                                "fleet_number"
                            ].help_text = f"""The ticket machine code ({vehicle_unique_id})
can’t be contradicted"""

        if not user.is_superuser:
            if vehicle.reg and vehicle.reg in re.sub(r"\W+", "", vehicle.code):
                self.fields["reg"].disabled = True
                self.fields[
                    "reg"
                ].help_text = (
                    f"The ticket machine code ({vehicle.code}) can’t be contradicted"
                )

            if not (
                vehicle.notes
                or vehicle.operator_id in settings.ALLOW_VEHICLE_NOTES_OPERATORS
            ):
                del self.fields["notes"]

        if vehicle.is_spare_ticket_machine():
            del self.fields["notes"]
            if not vehicle.fleet_code:
                del self.fields["fleet_number"]
            if not vehicle.reg:
                del self.fields["reg"]
            if not vehicle.vehicle_type_id:
                del self.fields["vehicle_type"]
            if not vehicle.name:
                del self.fields["name"]
            if not vehicle.data:
                del self.fields["previous_reg"]
            if (
                not vehicle.colours
                and not vehicle.livery_id
                and "colours" in self.fields
            ):
                del self.fields["colours"]
                del self.fields["other_colour"]


class DebuggerForm(forms.Form):
    data = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}))


class DateForm(forms.Form):
    date = forms.DateField()
