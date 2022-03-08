import re
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Count, Q, Exists, OuterRef
from django.utils.html import format_html
from django.urls import reverse

from busstops.models import Operator, Service
from .models import VehicleType, VehicleFeature, Livery, Vehicle, get_text_colour
from . import fields


def get_livery_choices(operator, vehicle, user):
    choices = {}

    q = Q(withdrawn=False)
    if vehicle:
        q |= Q(id=vehicle.id)
    vehicles = operator.vehicle_set.filter(q)

    liveries = Livery.objects.filter(Q(vehicle__in=vehicles) | Q(operator=operator))
    liveries = liveries.annotate(popularity=Count('vehicle')).order_by('-popularity')

    for livery in liveries.distinct():
        choices[livery.id] = livery.preview(name=True)

    if user.has_perm('vehicles.change_livery'):
        for livery_id in choices:
            url = reverse('admin:vehicles_livery_change', args=(livery_id,))
            choices[livery_id] += format_html(' <a href="{}">(edit)</a>', url)

    # add ad hoc vehicle colours
    for vehicle in vehicles.filter(~Q(colours=""), ~Q(colours="Other"), livery=None).distinct("colours"):
        choices[vehicle.colours] = Livery(colours=vehicle.colours, name=f'{vehicle.colours}').preview(name=True)

    # replace the dictionary with a list of key, label pairs
    choices = list(choices.items())

    if choices:
        choices.append(('Other', 'Other'))

    return choices


class EditVehiclesForm(forms.Form):
    withdrawn = forms.BooleanField(
        label='Permanently withdrawn', required=False,
        help_text="""Do not tick this box"""
    )
    spare_ticket_machine = forms.BooleanField(
        required=False,
        help_text="Only tick this box if the ticket machine code is something like SPARE"
    )
    other_vehicle_type = forms.CharField(required=False)
    vehicle_type = forms.ModelChoiceField(queryset=VehicleType.objects, label='Type', required=False, empty_label='')
    colours = forms.ChoiceField(label='Livery', widget=forms.RadioSelect, required=False)
    other_colour = forms.CharField(
        label='Other colours',
        help_text="E.g. '#c0c0c0 #ff0000 #ff0000' (red with a silver front)", required=False)
    features = forms.ModelMultipleChoiceField(queryset=VehicleFeature.objects, label='Features',
                                              widget=forms.CheckboxSelectMultiple, required=False)
    summary = fields.SummaryField(
        required=False,
        max_length=255,
        help_text="""Briefly explain your changes,
if they need explaining.
E.g. how you know a vehicle has definitely been withdrawn or repainted,
link to a picture to prove it. Be polite.""")

    def clean_other_colour(self):
        if self.cleaned_data['other_colour']:
            if self.cleaned_data.get('colours') != 'Other':
                return
            try:
                get_text_colour(self.cleaned_data['other_colour'])
            except ValueError as e:
                raise ValidationError(str(e))

        return self.cleaned_data['other_colour']

    def has_really_changed(self):
        if not self.has_changed():
            return False
        for key in self.changed_data:
            if all(key == 'summary' or key == 'other_colour' for key in self.changed_data):
                if not ('other_colour' in self.changed_data and self.data.get('other_colour')):
                    return False
        return True

    def __init__(self, *args, operator=None, user, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)

        colours = None

        if operator:
            colours = get_livery_choices(operator, vehicle, user)

        if colours:
            if vehicle:
                colours = [('', 'None/mostly white/other')] + colours
            else:
                colours = [('', 'No change')] + colours
            self.fields['colours'].choices = colours
        else:
            del self.fields['colours']
            del self.fields['other_colour']

        if user.id == 124:
            self.fields['withdrawn'].disabled = True


class EditVehicleForm(EditVehiclesForm):
    """With some extra fields, only applicable to editing a single vehicle
    """
    fleet_number = forms.CharField(required=False, max_length=24)
    reg = fields.RegField(label='Number plate', required=False, max_length=24)
    operator = forms.ModelChoiceField(queryset=None, label='Operator', empty_label='')
    branding = forms.CharField(label="Other branding", required=False, max_length=255)
    name = forms.CharField(label='Vehicle name', required=False, max_length=70, help_text="Leave this blank")
    previous_reg = fields.RegField(required=False, max_length=24, help_text="Separate multiple regs with a comma (,)")
    notes = forms.CharField(required=False, max_length=255)
    field_order = ['withdrawn', 'spare_ticket_machine',
                   'fleet_number', 'reg',
                   'operator', 'vehicle_type',
                   'colours', 'other_colour', 'branding', 'name',
                   'previous_reg', 'features', 'notes']

    def clean_reg(self):
        reg = self.cleaned_data['reg']
        if self.cleaned_data['spare_ticket_machine'] and reg:
            raise ValidationError("A spare ticket machine can’t have a number plate")
        return reg

    def __init__(self, *args, user, vehicle, **kwargs):
        super().__init__(*args, **kwargs, user=user, vehicle=vehicle)

        if not user.is_staff and vehicle.fleet_code:
            if vehicle.fleet_code in re.split(r'\W+', vehicle.code):
                self.fields['fleet_number'].disabled = True
                self.fields['fleet_number'].help_text = f"""The ticket machine code ({vehicle.code})
can’t be contradicted"""
            elif vehicle.latest_journey and vehicle.latest_journey.data:
                try:
                    vehicle_unique_id = vehicle.latest_journey.data['Extensions']['VehicleJourney']['VehicleUniqueId']
                except (KeyError, TypeError):
                    pass
                else:
                    if vehicle_unique_id == vehicle.fleet_code:
                        if not vehicle.code.isdigit() or vehicle.code == vehicle.fleet_code:
                            self.fields['fleet_number'].disabled = True
                            self.fields['fleet_number'].help_text = f"""The ticket machine code ({vehicle_unique_id})
can’t be contradicted"""

        if not user.is_staff:
            if vehicle.reg and vehicle.reg in re.sub(r'\W+', '', vehicle.code):
                self.fields['reg'].disabled = True
                self.fields['reg'].help_text = f"The ticket machine code ({vehicle.code}) can’t be contradicted"

            if not vehicle.notes and vehicle.operator_id != 'NATX':
                del self.fields['notes']
            if not vehicle.branding:
                del self.fields['branding']

        if vehicle.notes == 'Spare ticket machine':
            del self.fields['notes']
            if not vehicle.fleet_code:
                del self.fields['fleet_number']
            if not vehicle.reg:
                del self.fields['reg']
            if not vehicle.vehicle_type_id:
                del self.fields['vehicle_type']
            if not vehicle.name:
                del self.fields['name']
            if not vehicle.data:
                del self.fields['previous_reg']
            if not vehicle.colours and not vehicle.livery_id and 'colours' in self.fields:
                del self.fields['colours']
                del self.fields['other_colour']

        if not vehicle.withdrawn and vehicle.latest_journey:
            if timezone.now() - vehicle.latest_journey.datetime < timedelta(days=3):
                self.fields['withdrawn'].disabled = True
                self.fields['withdrawn'].help_text = """Can’t be ticked yet,
 as this vehicle (or ticket machine) has tracked in the last 3 days"""

        if not vehicle.operator or vehicle.operator.parent:
            operators = Operator.objects
            if user.trusted and vehicle.operator:
                # any sibling operator
                operators = operators.filter(parent=vehicle.operator.parent)
                condition = Exists(Service.objects.filter(current=True, operator=OuterRef('pk')).only('id'))
                condition |= Exists(Vehicle.objects.filter(operator=OuterRef('pk')).only('id'))
            elif vehicle.latest_journey:
                # only operators whose services the vehicle has operated
                condition = Exists(
                    Service.objects.filter(
                        operator=OuterRef('pk'),
                        id=vehicle.latest_journey.service_id
                    )
                )
            else:
                del self.fields['operator']
                return
            if vehicle.operator:
                condition |= Q(pk=vehicle.operator_id)
            self.fields['operator'].queryset = operators.filter(condition)
        else:
            del self.fields['operator']


class DebuggerForm(forms.Form):
    data = forms.CharField(widget=forms.Textarea(attrs={'rows': 6}))
