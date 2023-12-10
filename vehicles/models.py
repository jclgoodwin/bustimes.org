import datetime
import re
import struct
import uuid
from collections import Counter
from math import ceil
from urllib.parse import quote

from autoslug import AutoSlugField
from django.conf import settings
from django.contrib.gis.db import models
from django.core.exceptions import ValidationError
from django.db.models.functions import TruncDate, Upper
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape, format_html
from simple_history.models import HistoricalRecords
from webcolors import html5_parse_simple_color

from busstops.models import DataSource, Operator, Service
from bustimes.utils import get_trip


def format_reg(reg):
    if "-" not in reg:
        if reg[-3:].isalpha():
            return reg[:-3] + " " + reg[-3:]
        if reg[:3].isalpha():
            return reg[:3] + " " + reg[3:]
        if reg[-2:].isalpha():
            return reg[:-2] + " " + reg[-2:]
    return reg


def get_css(colours, direction=None, horizontal=False, angle=None):
    if len(colours) == 1:
        return colours[0]
    if direction is None:
        direction = 180
    else:
        direction = int(direction)
    background = "linear-gradient("
    if horizontal:
        background += "to top"
    elif direction < 180:
        if angle:
            background += f"{360-angle}deg"
        else:
            background += "to left"
    elif angle:
        background += f"{angle}deg"
    else:
        background += "to right"
    percentage = 100 / len(colours)
    for i, colour in enumerate(colours):
        if i != 0 and colour != colours[i - 1]:
            background += ",{} {}%".format(colour, ceil(percentage * i))
        if i != len(colours) - 1 and colour != colours[i + 1]:
            background += ",{} {}%".format(colour, ceil(percentage * (i + 1)))
    background += ")"

    return background


def get_brightness(colour):
    return (0.299 * colour.red + 0.587 * colour.green + 0.114 * colour.blue) / 255


def get_text_colour(colours):
    if not colours or colours == "Other":
        return
    colours = colours.split()
    colours = [html5_parse_simple_color(colour) for colour in colours]
    brightnesses = [get_brightness(colour) for colour in colours]
    colours_length = len(colours)
    if colours_length > 2:
        middle_brightness = sum(brightnesses[1:-1])
        outer_brightness = brightnesses[0] + brightnesses[-1]
        brightness = (middle_brightness * 2 + outer_brightness) / (
            (colours_length - 2) * 2 + 2
        )
    else:
        brightness = sum(brightnesses) / colours_length
    if brightness < 0.5:
        return "#fff"


class VehicleTypeType(models.TextChoices):
    DOUBLE_DECKER = "double decker", "double decker"
    MINIBUS = "minibus", "minibus"
    COACH = "coach", "coach"
    ARTICULATED = "articulated", "articulated"
    TRAIN = "train", "train"
    TRAM = "tram", "tram"


class FuelType(models.TextChoices):
    DIESEL = "diesel", "diesel"
    ELECTRIC = "electric", "electric"
    HYBRID = "hybrid", "hybrid"
    HYDROGEN = "hydrogen", "hydrogen"
    GAS = "gas", "gas"  # (compressed natural)


class VehicleType(models.Model):
    name = models.CharField(max_length=255, unique=True)
    # double_decker = models.BooleanField(null=True)
    # coach = models.BooleanField(null=True)
    # electric = models.BooleanField(null=True)
    style = models.CharField(choices=VehicleTypeType.choices, max_length=13, blank=True)
    fuel = models.CharField(choices=FuelType.choices, max_length=8, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class Livery(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    colour = models.CharField(
        max_length=7, help_text="For the most simplified version of the livery"
    )
    colours = models.CharField(
        max_length=512,
        blank=True,
        help_text="""Keep it simple.
Simplicity (and being able to read the route number on the map) is much more important than 'accuracy'.""",
    )
    css = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name="CSS",
        help_text="""Leave this blank.
A livery can be adequately represented with a list of colours and an angle.""",
    )
    left_css = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name="Left CSS",
        help_text="Automatically generated from colours and angle",
    )
    right_css = models.CharField(
        max_length=1024,
        blank=True,
        verbose_name="Right CSS",
        help_text="Automatically generated from colours and angle",
    )
    white_text = models.BooleanField(default=False)
    text_colour = models.CharField(max_length=7, blank=True)
    stroke_colour = models.CharField(
        max_length=7, blank=True, help_text="Use sparingly, often looks shit"
    )
    horizontal = models.BooleanField(
        default=False, help_text="Equivalent to setting the angle to 90"
    )
    angle = models.PositiveSmallIntegerField(null=True, blank=True)
    operators = models.ManyToManyField(
        "busstops.Operator", blank=True, related_name="liveries"
    )
    locked = models.BooleanField(default=False)
    updated_at = models.DateTimeField(null=True, blank=True)
    published = models.BooleanField(
        help_text="Tick to include in the CSS and be able to apply this livery to vehicles"
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "liveries"

    def __str__(self):
        return self.name

    def set_css(self):
        if self.css:
            css = self.css
            self.left_css = css
            for angle in re.findall(r"\((\d+)deg,", css):
                replacement = 360 - int(angle)
                css = css.replace(f"({angle}deg,", f"({replacement}deg,", 1)
                # doesn't work with e.g. angles {a, b} where a = 360 - b
            self.right_css = css.replace("left", "right")

        elif self.colours and self.colours != "Other":
            self.left_css = get_css(
                self.colours.split(), None, self.horizontal, self.angle
            )
            self.right_css = get_css(
                self.colours.split(), 90, self.horizontal, self.angle
            )

    def preview(self, name=False):
        if self.left_css:
            background = escape(self.left_css)
        elif self.colours:
            background = get_css(self.colours.split())
        elif name:
            background = ""
        else:
            return

        div = f'<div style="height:1.5em;width:2.25em;background:{background}"'
        if name:
            return format_html(div + "></div> {}", self.name)
        else:
            return format_html(div + ' title="{}"></div>', self.name)

    def clean(self):
        Vehicle.clean(self)  # validate colours field

        for attr in ("colour", "stroke_colour", "text_colour"):
            value = getattr(self, attr)
            if value:
                try:
                    html5_parse_simple_color(value)
                except ValueError as e:
                    raise ValidationError({attr: str(e)})

        for attr in ("css", "left_css", "right_css"):
            value = getattr(self, attr)
            if value.count("(") != value.count(")"):
                raise ValidationError({attr: "Must contain equal numbers of ( and )"})
            if "{" in value or "}" in value:
                raise ValidationError({attr: "Must not contain { or }"})

    def save(self, *args, update_fields=None, **kwargs):
        self.updated_at = timezone.now()
        if update_fields is None and (self.css or self.colours):
            self.set_css()
            if self.colours and not self.id:
                self.white_text = get_text_colour(self.colours) == "#fff"
        super().save(*args, update_fields=update_fields, **kwargs)

    def get_styles(self):
        if not self.left_css:
            return []
        selector = f".livery-{self.id}"
        css = f"background: {self.left_css}"
        if self.text_colour:
            css = f"{css};\n  color:{self.text_colour};fill:{self.text_colour}"
        elif self.white_text:
            css = f"{css};\n  color:#fff;fill:#fff"
        if self.stroke_colour:
            css = f"{css};stroke:{self.stroke_colour}"
        styles = [f"{selector} {{\n  {css}\n}}\n"]
        if self.right_css != self.left_css:
            styles.append(f"{selector}.right {{\n  background: {self.right_css}\n}}\n")
        return styles


class VehicleFeature(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)


def vehicle_slug(vehicle):
    return f"{vehicle.operator_id} {vehicle.code.replace('_', ' ')}"


class Vehicle(models.Model):
    slug = AutoSlugField(populate_from=vehicle_slug, editable=True, unique=True)
    code = models.CharField(max_length=255)
    fleet_number = models.PositiveIntegerField(null=True, blank=True)
    fleet_code = models.CharField(max_length=24, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    source = models.ForeignKey(DataSource, models.SET_NULL, null=True, blank=True)
    operator = models.ForeignKey(Operator, models.SET_NULL, null=True, blank=True)
    vehicle_type = models.ForeignKey(
        VehicleType, models.SET_NULL, null=True, blank=True
    )
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    branding = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    latest_journey = models.OneToOneField(
        "VehicleJourney",
        models.SET_NULL,
        null=True,
        blank=True,
        related_name="latest_vehicle",
    )
    latest_journey_data = models.JSONField(null=True, blank=True)
    features = models.ManyToManyField(VehicleFeature, blank=True)
    withdrawn = models.BooleanField(default=False)
    data = models.JSONField(null=True, blank=True)
    garage = models.ForeignKey(
        "bustimes.Garage", models.SET_NULL, null=True, blank=True
    )
    locked = models.BooleanField(default=False)

    def is_spare_ticket_machine(self) -> bool:
        return self.notes == "Spare ticket machine"

    def has_uk_reg(self):
        return " " in self.get_reg()

    def is_editable(self) -> bool:
        if self.locked or (
            self.is_spare_ticket_machine()
            and not self.livery_id
            and not self.vehicle_type_id
        ):
            return False
        return True

    def save(self, *args, update_fields=None, **kwargs):
        if (
            update_fields is None or "fleet_number" in update_fields
        ) and self.fleet_number:
            if not self.fleet_code or (
                self.fleet_code.isdigit() and self.fleet_number != int(self.fleet_code)
            ):
                self.fleet_code = str(self.fleet_number)
                if update_fields is not None and "fleet_code" not in update_fields:
                    update_fields.append("fleet_code")

        if (update_fields is None or "fleet_code" in update_fields) and self.fleet_code:
            if not self.fleet_number and self.fleet_code.isdigit():
                self.fleet_number = int(self.fleet_code)
                if update_fields is not None and "fleet_number" not in update_fields:
                    update_fields.append("fleet_number")

        if update_fields is None and not self.reg:
            reg = re.match(r"^[A-Z]\w_?\d\d?[ _-]?[A-Z]{3}$", self.code)
            if reg:
                self.reg = re.sub("[-_ ]", "", self.code)
        elif update_fields is None or "reg" in update_fields:
            self.reg = self.reg.upper().replace(" ", "")

        super().save(*args, update_fields=update_fields, **kwargs)

    class Meta:
        indexes = [
            models.Index(Upper("fleet_code"), name="fleet_code"),
            models.Index(Upper("reg"), name="reg"),
            models.Index(fields=["operator", "withdrawn"], name="operator_withdrawn"),
        ]
        constraints = [
            models.UniqueConstraint(
                Upper("code"), "operator", name="vehicle_operator_and_code"
            ),
        ]

    def __str__(self):
        fleet_code = self.fleet_code or self.fleet_number
        if self.reg:
            if fleet_code:
                return f"{fleet_code} - {self.get_reg()}"
            return self.get_reg()
        if fleet_code:
            return str(fleet_code)
        return self.code.replace("_", " ")

    def get_previous(self):
        if self.fleet_number and self.operator:
            vehicles = self.operator.vehicle_set.filter(
                withdrawn=False, fleet_number__lt=self.fleet_number
            )
            return vehicles.order_by("-fleet_number").first()

    def get_next(self):
        if self.fleet_number and self.operator:
            vehicles = self.operator.vehicle_set.filter(
                withdrawn=False, fleet_number__gt=self.fleet_number
            )
            return vehicles.order_by("fleet_number").first()

    def get_reg(self):
        return format_reg(self.reg)

    def data_get(self, key=None):
        if not key:
            if self.data:
                return [(key, self.data_get(key)) for key in self.data]
            return ()
        if self.data:
            value = self.data.get(key)
            if value:
                if key == "Previous reg":
                    return ", ".join(format_reg(reg) for reg in value.split(","))
                return value
        return ""

    def get_text_colour(self):
        if self.livery:
            if self.livery.white_text:
                return "#fff"
        elif self.colours:
            return get_text_colour(self.colours)

    def get_livery(self, direction=None):
        if self.livery:
            if direction is not None and direction < 180:
                return escape(self.livery.right_css)
            return escape(self.livery.left_css)

        colours = self.colours
        if colours and colours != "Other":
            colours = colours.split()
            if len(colours) > 1:
                self.colour = Counter(colours).most_common()[0][0]
            return get_css(colours, direction, self.livery and self.livery.horizontal)

    def get_absolute_url(self):
        return reverse("vehicle_detail", args=(self.slug or self.id,))

    def get_edit_url(self):
        return reverse("vehicle_edit", args=(self.slug or self.id,))

    def get_history_url(self):
        return reverse("vehicle_history", args=(self.slug or self.id,))

    def get_flickr_url(self):
        if self.reg:
            reg = self.get_reg()
            search = f'{self.reg} or "{reg}"'
            if self.fleet_number and self.operator and self.operator.parent:
                number = str(self.fleet_number)
                if len(number) >= 5:
                    search = f"{search} or {self.operator.parent} {number}"
        else:
            if self.fleet_code or self.fleet_number:
                search = self.fleet_code or str(self.fleet_number)
            else:
                search = str(self).replace("/", " ")
            if self.operator:
                name = str(self.operator).split(" (", 1)[0]
                if "Yellow" not in name:
                    name = (
                        str(self.operator)
                        .replace(" Buses", "", 1)
                        .replace(" Coaches", "", 1)
                    )
                if (
                    name.startswith("First ")
                    or name.startswith("Stagecoach ")
                    or name.startswith("Arriva ")
                ):
                    name = name.split()[0]
                search = f"{name} {search}"
        return (
            f"https://www.flickr.com/search/?text={quote(search)}&sort=date-taken-desc"
        )

    def get_flickr_link(self):
        if self.is_spare_ticket_machine():
            return ""
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Flickr</a>',
            self.get_flickr_url(),
        )

    get_flickr_link.short_description = "Flickr"

    def clean(self):
        try:
            get_text_colour(self.colours)
        except ValueError as e:
            raise ValidationError({"colours": str(e)})

    def get_json(self):
        json = {
            "url": self.get_absolute_url(),
            "name": str(self),
        }

        features = self.feature_names
        if self.vehicle_type:
            vehicle_type = self.vehicle_type.style.capitalize()
            if vehicle_type:
                if features:
                    features = f"{vehicle_type}<br>{features}"
                else:
                    features = vehicle_type
        if features:
            json["features"] = features

        if self.livery_id:
            json["livery"] = self.livery_id
        elif self.colours:
            json["css"] = self.get_livery()
            json["right_css"] = self.get_livery(90)
            json["text_colour"] = self.get_text_colour()
        if colour := getattr(self, "colour", None):
            json["colour"] = colour
        return json


class VehicleCode(models.Model):
    code = models.CharField(max_length=100)
    scheme = models.CharField(max_length=24)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)

    def __str__(self):
        return f"{self.scheme} {self.code}"

    class Meta:
        indexes = [models.Index(fields=("code", "scheme"))]


class VehicleEditFeature(models.Model):
    feature = models.ForeignKey(VehicleFeature, models.CASCADE)
    edit = models.ForeignKey("VehicleEdit", models.CASCADE)
    add = models.BooleanField(default=True)

    def __str__(self):
        if self.add:
            fmt = "<ins>{}</ins>"
        else:
            fmt = "<del>{}</del>"
        return format_html(fmt, self.feature)


class VehicleEdit(models.Model):
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    fleet_number = models.CharField(max_length=24, blank=True)
    reg = models.CharField(max_length=24, blank=True)
    vehicle_type = models.CharField(max_length=255, blank=True)
    colours = models.CharField(max_length=255, blank=True)
    livery = models.ForeignKey(Livery, models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    branding = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    features = models.ManyToManyField(
        VehicleFeature, blank=True, through=VehicleEditFeature
    )
    withdrawn = models.BooleanField(null=True)
    changes = models.JSONField(null=True, blank=True)
    url = models.URLField(blank=True, max_length=255)
    approved = models.BooleanField(null=True, db_index=True)
    arbiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        null=True,
        blank=True,
        related_name="arbited",
    )
    score = models.SmallIntegerField(default=0)
    datetime = models.DateTimeField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.SET_NULL, null=True, blank=True
    )

    def get_css(self):
        if self.colours and self.colours != "Other":
            return get_css(self.colours.split())

    def get_changes(self):
        changes = {}
        for field in (
            "fleet_number",
            "reg",
            "vehicle_type",
            "branding",
            "name",
            "notes",
            "colours",
            "livery_id",
        ):
            edit = str(getattr(self, field) or "")
            if edit:
                if field == "reg":
                    edit = edit.upper().replace(" ", "")
                if field == "fleet_number" and self.vehicle.fleet_code:
                    vehicle = self.vehicle.fleet_code
                else:
                    vehicle = str(getattr(self.vehicle, field) or "")

                if field == "vehicle_type":
                    field = "type"

                if edit.startswith("-"):
                    if edit == f"-{vehicle}":
                        edit = format_html("<del>{}</del>", vehicle)
                    else:
                        edit = ""
                if edit != vehicle:
                    changes[field] = edit
        changed_features = self.vehicleeditfeature_set.all()
        if changed_features:
            features = []
            for feature in changed_features:
                if feature.add:
                    if feature.feature not in self.vehicle.features.all():
                        features.append(feature)
                elif feature.feature in self.vehicle.features.all():
                    features.append(feature)
            if features:
                changes["features"] = features
        if self.withdrawn is not None:
            changes["withdrawn"] = self.withdrawn
        if self.changes:
            for key in self.changes:
                if not self.vehicle.data or self.changes[key] != self.vehicle.data.get(
                    key
                ):
                    changes[key.lower()] = self.changes[key]
        return changes

    def apply(self, save=True, user=None):
        vehicle = self.vehicle
        revision = None
        if save:
            revision = self.make_revision()
        update_fields = []
        if self.withdrawn is not None:
            if revision:
                if self.withdrawn:
                    revision.changes["withdrawn"] = "-No\n+Yes"
                else:
                    revision.changes["withdrawn"] = "-Yes\n+No"
            vehicle.withdrawn = self.withdrawn
            update_fields.append("withdrawn")
        if self.fleet_number:
            if self.fleet_number.startswith("-"):
                if (
                    self.fleet_number
                    == f"-{vehicle.fleet_code or vehicle.fleet_number}"
                ):
                    vehicle.fleet_code = ""
                    vehicle.fleet_number = None
            else:
                vehicle.fleet_code = self.fleet_number
                if self.fleet_number.isdigit():
                    vehicle.fleet_number = self.fleet_number
                else:
                    vehicle.fleet_number = None
            update_fields.append("fleet_code")
            update_fields.append("fleet_number")
        if self.changes:
            if vehicle.data:
                vehicle.data = {**vehicle.data, **self.changes}
                for field in self.changes:
                    if not self.changes[field]:
                        del vehicle.data[field]
            else:
                vehicle.data = self.changes
            update_fields.append("data")
        for field in ("branding", "name", "notes", "reg"):
            new_value = getattr(self, field)
            if new_value:
                if new_value.startswith("-"):
                    if new_value == f"-{getattr(vehicle, field)}":
                        setattr(vehicle, field, "")
                    else:
                        continue
                else:
                    setattr(vehicle, field, new_value)
                update_fields.append(field)
        if self.vehicle_type:
            if self.vehicle_type.startswith("-"):
                vehicle.vehicle_type = None
            else:
                vehicle.vehicle_type = VehicleType.objects.get(
                    name__iexact=self.vehicle_type
                )
            update_fields.append("vehicle_type")
        if self.livery_id:
            vehicle.livery_id = self.livery_id
            vehicle.colours = ""
            update_fields.append("livery")
            update_fields.append("colours")
        elif self.colours and self.colours != "Other":
            vehicle.livery = None
            vehicle.colours = self.colours
            update_fields.append("livery")
            update_fields.append("colours")
        if save:
            vehicle.save(update_fields=update_fields)
            if revision.has_changes():
                revision.save()
            for feature in self.vehicleeditfeature_set.all():
                if feature.add:
                    vehicle.features.add(feature.feature)
                else:
                    vehicle.features.remove(feature.feature)
                if not revision.id:
                    revision.save()
                VehicleRevisionFeature.objects.create(
                    add=feature.add, feature=feature.feature, revision=revision
                )

            self.approved = True
            self.arbiter = user
            self.save(update_fields=["approved", "arbiter"])

    def make_revision(self):
        revision = VehicleRevision(
            user_id=self.user_id,
            vehicle_id=self.vehicle_id,
            datetime=self.datetime,
            message=self.url,
            to_livery_id=self.livery_id,
            changes={},
        )
        if self.vehicle_type:
            revision.to_type = VehicleType.objects.get_or_create(
                {"name": self.vehicle_type}, name__iexact=self.vehicle_type
            )[0]
            if revision.to_type.id != self.vehicle.vehicle_type_id:
                revision.from_type_id = self.vehicle.vehicle_type_id
        for field in ("reg", "name", "branding", "notes", "fleet_number", "colours"):
            to_value = getattr(self, field)
            if to_value:
                from_value = getattr(self.vehicle, field)
                if field == "fleet_number":
                    from_value = self.vehicle.fleet_code
                    field = "fleet number"
                if to_value.startswith("-") and (
                    to_value == f"-{from_value}" or from_value == ""
                ):
                    to_value = ""
                elif from_value == to_value:
                    from_value = ""
                revision.changes[field] = f"-{from_value}\n+{to_value}"
        return revision

    def get_absolute_url(self):
        return self.vehicle.get_absolute_url()

    def __str__(self):
        return str(self.id)


class VehicleEditVote(models.Model):
    by_user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)
    for_edit = models.ForeignKey(VehicleEdit, models.CASCADE, null=True, blank=True)
    for_revision = models.ForeignKey(
        "VehicleRevision", models.CASCADE, null=True, blank=True
    )
    positive = models.BooleanField()

    class Meta:
        unique_together = ("by_user", "for_edit")


class VehicleRevisionFeature(models.Model):
    feature = models.ForeignKey(VehicleFeature, models.CASCADE)
    revision = models.ForeignKey("VehicleRevision", models.CASCADE)
    add = models.BooleanField(default=True)

    __str__ = VehicleEditFeature.__str__


class VehicleRevision(models.Model):
    datetime = models.DateTimeField()
    vehicle = models.ForeignKey(Vehicle, models.CASCADE)
    from_operator = models.ForeignKey(
        Operator, models.SET_NULL, null=True, blank=True, related_name="revision_from"
    )
    to_operator = models.ForeignKey(
        Operator, models.SET_NULL, null=True, blank=True, related_name="revision_to"
    )
    from_type = models.ForeignKey(
        VehicleType,
        models.SET_NULL,
        null=True,
        blank=True,
        related_name="revision_from",
    )
    to_type = models.ForeignKey(
        VehicleType, models.SET_NULL, null=True, blank=True, related_name="revision_to"
    )
    from_livery = models.ForeignKey(
        Livery, models.SET_NULL, null=True, blank=True, related_name="revision_from"
    )
    to_livery = models.ForeignKey(
        Livery, models.SET_NULL, null=True, blank=True, related_name="revision_to"
    )
    changes = models.JSONField(null=True, blank=True)
    message = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, models.SET_NULL, null=True, blank=True
    )
    features = models.ManyToManyField(
        VehicleFeature, blank=True, through=VehicleRevisionFeature
    )

    def __str__(self):
        return ", ".join(
            f"{key}: {before} → {after}"
            for key, before, after in self.list_changes(html=False)
        )

    def has_changes(self):
        for field in self.list_changes(html=False):
            return True
        return False

    def list_changes(self, html=True):
        for field in ("operator", "type", "livery"):
            if getattr(self, f"from_{field}_id") or getattr(self, f"to_{field}_id"):
                if getattr(__class__, f"from_{field}").is_cached(self):
                    before = getattr(self, f"from_{field}")
                    after = getattr(self, f"to_{field}")

                    if field == "livery":
                        if before:
                            before = format_html(
                                '<span class="livery" style="background:{}"></span>',
                                before.left_css,
                            )
                        if after:
                            after = format_html(
                                '<span class="livery" style="background:{}"></span>',
                                after.left_css,
                            )
                else:
                    before = getattr(self, f"from_{field}_id")
                    after = getattr(self, f"to_{field}_id")
                yield (field, before, after)
        if self.changes:
            for key in self.changes:
                before, after = self.changes[key].split("\n+")
                before = before[1:]
                if key == "colours" and html:
                    if before and before != "Other":
                        before = format_html(
                            '<span class="livery" style="background:{}"></span>',
                            get_css(before.split()),
                        )
                    if after and after != "Other":
                        after = format_html(
                            '<span class="livery" style="background:{}"></span>',
                            get_css(after.split()),
                        )
                if key == "withdrawn":
                    if after == "Yes":
                        yield ("removed from list", "", "")
                    else:
                        yield ("added to list", "", "")
                else:
                    yield (key, before, after)

    def revert(self):
        """Revert various values to how they were before the revision"""
        vehicle = self.vehicle
        fields = []

        for key, vehicle_key in (
            ("operator", "operator"),
            ("type", "vehicle_type"),
            ("livery", "livery"),
        ):
            before = getattr(self, f"from_{key}_id")
            after = getattr(self, f"to_{key}_id")
            if before or after:
                if getattr(vehicle, f"{vehicle_key}_id") == after:
                    setattr(vehicle, f"{vehicle_key}_id", before)
                    fields.append(vehicle_key)

        if self.changes:
            for key in self.changes:
                before, after = self.changes[key].split("\n+")
                before = before[1:]
                if key == "reg" or key == "name":
                    if getattr(vehicle, key) == after:
                        setattr(vehicle, key, before)
                        fields.append("reg")
                elif key == "withdrawn":
                    if vehicle.withdrawn and after == "Yes":
                        vehicle.withdrawn = False
                        fields.append("withdrawn")
                else:
                    yield f"vehicle {vehicle.id} {key} not reverted"

        if fields:
            self.vehicle.save(update_fields=fields)
            yield f"vehicle {vehicle.id} reverted {fields}"


class VehicleJourney(models.Model):
    datetime = models.DateTimeField()
    service = models.ForeignKey(Service, models.SET_NULL, null=True, blank=True)
    route_name = models.CharField(max_length=64, blank=True)
    source = models.ForeignKey(DataSource, models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, models.CASCADE, null=True, blank=True)
    code = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255, blank=True)
    direction = models.CharField(max_length=8, blank=True)
    trip = models.ForeignKey("bustimes.Trip", models.SET_NULL, null=True, blank=True)
    # block = models.ForeignKey("bustimes.Block", models.SET_NULL, null=True, blank=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    def get_absolute_url(self):
        return f"/vehicles/{self.vehicle_id}?date={self.datetime.date()}#journeys/{self.id}"

    def __str__(self):
        when = f"{self.datetime:%-d %b %y %H:%M} {self.route_name} {self.code} {self.direction}"
        if self.destination:
            when = f"{when} to {self.destination}"
        return when

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(
                "service", TruncDate("datetime").asc(), name="service_datetime_date"
            ),
            models.Index(
                "vehicle", TruncDate("datetime").asc(), name="vehicle_datetime_date"
            ),
        ]
        unique_together = (("vehicle", "datetime"),)

    get_trip = get_trip


# class VehiclePosition:
#     journey = models.ForeignKey(VehicleJourney, on_delete)


class Occupancy(models.TextChoices):
    SEATS_AVAILABLE = "seatsAvailable", "Seats available"
    STANDING_AVAILABLE = "standingAvailable", "Standing available"
    FULL = "full", "Full"


class VehicleLocation:
    """This used to be a model,
    is no longer stored in the database
    but this code is still here for historical reasons
    """

    def __init__(self, latlong, heading=None, delay=None, occupancy=None, block=None):
        self.latlong = latlong
        self.heading = heading
        self.delay = delay
        self.occupancy = occupancy
        self.seated_occupancy = None
        self.seated_capacity = None
        self.wheelchair_occupancy = None
        self.wheelchair_capacity = None
        self.occupancy_thresholds = None
        self.block = block
        self.tfl_code = None

    def get_occupancy_display(self):
        return Occupancy(self.occupancy).label

    def __str__(self):
        return f"{self.datetime:%-d %b %Y %H:%M:%S}"

    class Meta:
        ordering = ("id",)

    def get_appendage(self):
        # early = self.early
        # if early is not None:
        #     early = round(early.total_seconds() / 60)

        if self.heading is None or type(self.heading) is int:
            heading = self.heading
        elif type(self.heading) is str:
            if self.heading.isdigit():
                heading = int(self.heading)
            elif self.heading:
                heading = round(float(self.heading))
            else:
                heading = None
        else:
            heading = round(self.heading)

        return f"journey{self.journey.id}", struct.pack(
            "I 2f ?h ?h",
            round(self.datetime.timestamp()),
            self.latlong.x,
            self.latlong.y,
            heading is not None,
            heading or 0,
            False,  # early is not None
            0,  # early or 0
        )

    @staticmethod
    def decode_appendage(location):
        location = struct.unpack("I 2f ?h ?h", location)
        return {
            "coordinates": location[1:3],
            "delta": (location[5] or None) and location[6],
            "direction": (location[3] or None) and location[4],
            "datetime": datetime.datetime.fromtimestamp(
                location[0], datetime.timezone.utc
            ),
        }

    def get_redis_json(self):
        journey = self.journey

        json = {
            "id": self.id,  # (same as vehicle id)
            "journey_id": journey.id,
            "coordinates": self.latlong.coords,
            "heading": self.heading,
            "datetime": self.datetime,
            "destination": journey.destination,
            "block": self.block,
        }

        if self.delay is not None:
            json["delay"] = -self.delay.total_seconds()

        if self.tfl_code:
            json["tfl_code"] = self.tfl_code
        if journey.trip_id:
            json["trip_id"] = journey.trip_id
        if journey.service_id:
            json["service_id"] = journey.service_id
        if journey.route_name:
            json["service"] = {"line_name": journey.route_name}

        if self.seated_occupancy is not None and self.seated_capacity is not None:
            if self.occupancy == "full":
                json["seats"] = self.occupancy
            else:
                json["seats"] = f"{self.seated_capacity - self.seated_occupancy} free"
        elif self.occupancy:
            json["seats"] = self.get_occupancy_display()
        if self.wheelchair_occupancy is not None and self.wheelchair_capacity:
            if self.wheelchair_occupancy < self.wheelchair_capacity:
                json["wheelchair"] = "free"
            else:
                json["wheelchair"] = "occupied"

        return json


class SiriSubscription(models.Model):
    name = models.CharField(max_length=64, blank=True, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    sample = models.TextField(null=True, blank=True)
