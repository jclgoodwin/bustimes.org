import re
from datetime import timedelta
from urllib.parse import quote_plus

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from sql_util.utils import Exists

from busstops.models import Operator, Service

from . import fields
from .models import Livery, VehicleFeature, VehicleType, get_text_colour


def get_livery_choices(operator, vehicle, user):
    choices = {}

    q = Q(withdrawn=False)
    if vehicle:
        q |= Q(id=vehicle.id)
    vehicles = operator.vehicle_set.filter(q)

    liveries = Livery.objects.filter(
        Q(vehicle__in=vehicles) | Q(operator=operator, published=True)
    )
    liveries = liveries.annotate(popularity=Count("vehicle")).order_by("-popularity")

    for livery in liveries.distinct():
        choices[livery.id] = livery.preview(name=True)

        if user.has_perm("vehicles.change_livery"):
            url = reverse("admin:vehicles_livery_change", args=(livery.id,))
            choices[livery.id] += format_html(' <a href="{}">(edit)</a>', url)

    # add ad hoc vehicle colours
    for vehicle in vehicles.filter(
        ~Q(colours=""), ~Q(colours="Other"), livery=None
    ).distinct("colours"):
        choices[vehicle.colours] = Livery(
            colours=vehicle.colours, name=f"{vehicle.colours}"
        ).preview(name=True)

        if user.has_perm("vehicles.change_livery"):
            url = reverse("admin:vehicles_livery_add")
            choices[vehicle.colours] += format_html(
                ' <a href="{}?colours={}&amp;operator={}">(add proper livery)</a>',
                url,
                quote_plus(vehicle.colours),
                vehicle.operator_id,
            )

    # replace the dictionary with a list of key, label pairs
    choices = list(choices.items())

    if choices:
        choices.append(("Other", "Other"))

    return choices


class EditVehiclesForm(forms.Form):
    spare_ticket_machine = forms.BooleanField(
        required=False,
        help_text="Only tick this box if the ticket machine code is something like SPARE",
    )
    withdrawn = forms.BooleanField(
        label="Permanently withdrawn",
        required=False,
        help_text="This removes the vehicle from the fleet list. Wait a few days before ticking",
    )
    operator = forms.ModelChoiceField(queryset=None, label="Operator", empty_label="")
    other_vehicle_type = forms.CharField(required=False)
    vehicle_type = forms.ModelChoiceField(
        queryset=VehicleType.objects, label="Type", required=False, empty_label=""
    )
    colours = forms.ChoiceField(
        label="Livery",
        widget=forms.RadioSelect,
        required=False,
        help_text="Wait until the bus has definitely been repainted before updating it here",
    )
    other_colour = forms.CharField(
        label="Other colours",
        help_text="E.g. '#c0c0c0 #ff0000 #ff0000' (red with a silver front)",
        required=False,
    )
    features = forms.ModelMultipleChoiceField(
        queryset=VehicleFeature.objects,
        label="Features",
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
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
            if self.cleaned_data.get("colours") != "Other":
                return
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

    def __init__(self, *args, operator=None, user, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)

        colours = None

        if operator:
            colours = get_livery_choices(operator, vehicle, user)

        if colours:
            if vehicle:
                colours = [("", "None/mostly white/other")] + colours
            else:
                colours = [("", "No change")] + colours
            self.fields["colours"].choices = colours
        else:
            del self.fields["colours"]
            del self.fields["other_colour"]

        if user.is_staff:
            self.fields["operator"].queryset = Operator.objects.all()
            self.fields["operator"].widget = forms.TextInput()
        elif not vehicle:
            del self.fields["operator"]


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle"""

    fleet_number = forms.CharField(required=False, max_length=24)
    reg = fields.RegField(label="Number plate", required=False, max_length=24)
    branding = forms.CharField(
        label="Other branding",
        required=False,
        max_length=255,
        help_text="Leave this blank",
    )
    name = forms.CharField(
        label="Vehicle name",
        required=False,
        max_length=70,
        help_text="Leave this blank",
    )
    previous_reg = fields.RegField(
        required=False,
        max_length=24,
        help_text="Separate multiple regs with a comma (,)",
    )
    notes = forms.CharField(required=False, max_length=255)
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

    def clean_reg(self):
        reg = self.cleaned_data["reg"]
        if self.cleaned_data["spare_ticket_machine"] and reg:
            raise ValidationError("A spare ticket machine can’t have a number plate")
        return reg

    def __init__(self, *args, user, vehicle, **kwargs):
        super().__init__(*args, **kwargs, user=user, vehicle=vehicle)

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

            if not vehicle.notes and vehicle.operator_id != "NATX":
                del self.fields["notes"]

        if not (
            user.is_staff
            or vehicle.branding
            or vehicle.operator_id == "TNXB"
            or vehicle.operator_id == "TCVW"
        ):
            del self.fields["branding"]

        if vehicle.notes == "Spare ticket machine":
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

        if not vehicle.withdrawn and vehicle.latest_journey:
            if timezone.now() - vehicle.latest_journey.datetime < timedelta(days=3):
                self.fields["withdrawn"].disabled = True
                self.fields[
                    "withdrawn"
                ].help_text = """Can’t be ticked yet,
 as this vehicle (or ticket machine) has tracked in the last 3 days"""

        try:
            operator_ref = vehicle.latest_journey_data["MonitoredVehicleJourney"][
                "OperatorRef"
            ]
        except (TypeError, KeyError):
            pass
        else:
            if vehicle.operator_id == operator_ref:
                del self.fields["operator"]

        if user.is_staff:
            pass
        elif (
            not vehicle.operator or vehicle.operator.parent
        ):  # vehicle has no operator, or operator is part of a group
            operators = Operator.objects
            if user.trusted and vehicle.operator:
                # any sibling operator
                operators = operators.filter(parent=vehicle.operator.parent)
                condition = Exists(
                    Service.objects.filter(current=True, operator=OuterRef("pk")).only(
                        "id"
                    )
                )
                condition |= Exists("vehicle")
            elif vehicle.latest_journey:
                # only operators whose services the vehicle has operated
                condition = Exists(
                    Service.objects.filter(
                        operator=OuterRef("pk"), id=vehicle.latest_journey.service_id
                    )
                )
            else:
                del self.fields["operator"]
                return
            if vehicle.operator:
                condition |= Q(pk=vehicle.operator_id)
            self.fields["operator"].queryset = operators.filter(condition)
        else:
            del self.fields["operator"]


class DebuggerForm(forms.Form):
    data = forms.CharField(widget=forms.Textarea(attrs={"rows": 6}))


class DateForm(forms.Form):
    date = forms.DateField()
