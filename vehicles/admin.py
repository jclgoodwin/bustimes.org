from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin
from sql_util.utils import SubqueryCount

from . import models

UserModel = get_user_model()


@admin.register(models.VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("id", "name", "vehicles", "double_decker", "coach")
    list_editable = ("name", "double_decker", "coach")
    actions = ["merge"]

    @admin.display(ordering="vehicles")
    def vehicles(self, obj):
        return obj.vehicles

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(vehicles=SubqueryCount("vehicle"))
        return queryset

    def merge(self, request, queryset):
        first = queryset[0]
        models.Vehicle.objects.filter(vehicle_type__in=queryset).update(
            vehicle_type=first
        )
        models.VehicleRevision.objects.filter(from_type__in=queryset).update(
            from_type=first
        )
        models.VehicleRevision.objects.filter(to_type__in=queryset).update(
            to_type=first
        )


class VehicleAdminForm(forms.ModelForm):
    class Meta:
        widgets = {
            "fleet_number": forms.TextInput(attrs={"style": "width: 4em"}),
            "fleet_code": forms.TextInput(attrs={"style": "width: 4em"}),
            "reg": forms.TextInput(attrs={"style": "width: 8em"}),
            "operator": forms.TextInput(attrs={"style": "width: 4em"}),
            "branding": forms.TextInput(attrs={"style": "width: 8em"}),
            "name": forms.TextInput(attrs={"style": "width: 8em"}),
        }


def user(obj):
    return format_html(
        '<a href="{}">{}</a>',
        reverse("admin:accounts_user_change", args=(obj.user_id,)),
        obj.user,
    )


class VehicleEditInline(admin.TabularInline):
    model = models.VehicleEdit
    fields = [
        "approved",
        "datetime",
        "fleet_number",
        "reg",
        "vehicle_type",
        "livery_id",
        "colours",
        "branding",
        "notes",
        "changes",
        user,
    ]
    readonly_fields = fields[1:]
    show_change_link = True


class DuplicateVehicleFilter(admin.SimpleListFilter):
    title = "duplicate"
    parameter_name = "duplicate"

    def lookups(self, request, model_admin):
        return (
            ("reg", "same reg"),
            ("operator", "same reg and operator"),
        )

    def queryset(self, request, queryset):
        if self.value():
            vehicles = models.Vehicle.objects.filter(
                ~Q(id=OuterRef("id")), reg__iexact=OuterRef("reg")
            )
            if self.value() == "operator":
                vehicles = vehicles.filter(operator=OuterRef("operator"))
            queryset = queryset.filter(~Q(reg__iexact=""), Exists(vehicles))

        return queryset


@admin.register(models.Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "fleet_number",
        "fleet_code",
        "reg",
        "operator",
        "vehicle_type",
        "get_flickr_link",
        "withdrawn",
        "last_seen",
        "livery",
        "colours",
        "branding",
        "name",
        "notes",
        "data",
    )
    list_filter = (
        DuplicateVehicleFilter,
        "withdrawn",
        "features",
        "vehicle_type",
        ("source", admin.RelatedOnlyFieldListFilter),
        ("operator", admin.RelatedOnlyFieldListFilter),
    )
    list_select_related = ["operator", "livery", "vehicle_type", "latest_journey"]
    list_editable = (
        "fleet_number",
        "fleet_code",
        "reg",
        "operator",
        "branding",
        "name",
        "notes",
    )
    autocomplete_fields = ("vehicle_type", "livery")
    raw_id_fields = ("operator", "source", "latest_journey")
    search_fields = ("code", "fleet_code", "reg")
    ordering = ("-id",)
    actions = (
        "copy_livery",
        "copy_type",
        "make_livery",
        "deduplicate",
        "spare_ticket_machine",
    )
    inlines = [VehicleEditInline]
    readonly_fields = ["latest_journey_data"]

    def copy_livery(self, request, queryset):
        livery = models.Livery.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(livery=livery)
        self.message_user(request, f"Copied {livery} to {count} vehicles.")

    def copy_type(self, request, queryset):
        vehicle_type = models.VehicleType.objects.filter(vehicle__in=queryset).first()
        count = queryset.update(vehicle_type=vehicle_type)
        self.message_user(request, f"Copied {vehicle_type} to {count} vehicles.")

    def make_livery(self, request, queryset):
        vehicle = queryset.first()
        if vehicle.colours and vehicle.branding:
            livery = models.Livery.objects.create(
                name=vehicle.branding, colours=vehicle.colours, published=True
            )
            vehicles = models.Vehicle.objects.filter(
                colours=vehicle.colours, branding=vehicle.branding
            )
            count = vehicles.update(colours="", branding="", livery=livery)
            self.message_user(request, f"Updated {count} vehicles.")
        else:
            self.message_user(request, "Select a vehicle with colours and branding.")

    def deduplicate(self, request, queryset):
        for vehicle in queryset.order_by("id"):
            if not vehicle.reg:
                self.message_user(request, f"{vehicle} has no reg")
                continue
            try:
                duplicate = models.Vehicle.objects.get(
                    id__lt=vehicle.id, reg__iexact=vehicle.reg
                )  # vehicle with lower id number we will keep
            except (
                models.Vehicle.DoesNotExist,
                models.Vehicle.MultipleObjectsReturned,
            ) as e:
                self.message_user(request, f"{vehicle} {e}")
                continue
            try:
                vehicle.vehiclejourney_set.update(vehicle=duplicate)
            except IntegrityError:
                pass
            if (
                not duplicate.latest_journey_id
                or vehicle.latest_journey_id
                and vehicle.latest_journey_id > duplicate.latest_journey_id
            ):
                duplicate.code = vehicle.code
                duplicate.latest_journey = vehicle.latest_journey
            vehicle.latest_journey = None
            vehicle.save(update_fields=["latest_journey"])
            duplicate.save(update_fields=["latest_journey"])
            duplicate.fleet_code = vehicle.fleet_code
            duplicate.fleet_number = vehicle.fleet_number
            if duplicate.withdrawn and not vehicle.withdrawn:
                duplicate.withdrawn = False
            vehicle.delete()
            duplicate.save(
                update_fields=["code", "fleet_code", "fleet_number", "reg", "withdrawn"]
            )
            self.message_user(request, f"{vehicle} deleted, merged with {duplicate}")

    def spare_ticket_machine(self, request, queryset):
        queryset.update(
            reg="",
            fleet_code="",
            fleet_number=None,
            name="",
            colours="",
            livery=None,
            branding="",
            vehicle_type=None,
            notes="Spare ticket machine",
        )

    @admin.display(ordering="latest_journey__datetime")
    def last_seen(self, obj):
        if obj.latest_journey:
            return obj.latest_journey.datetime

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault("form", VehicleAdminForm)
        return super().get_changelist_form(request, **kwargs)


class UserFilter(admin.SimpleListFilter):
    title = "user"
    parameter_name = "user"

    def lookups(self, request, model_admin):
        lookups = {
            "Trusted": "Trusted",
            "Banned": "Banned",
            "None": "None",
        }
        if self.value() and self.value() not in lookups:
            lookups[self.value()] = self.value()
        return lookups.items()

    def queryset(self, request, queryset):
        match self.value():
            case "Trusted":
                return queryset.filter(user__trusted=True)
            case "Banned":
                return queryset.filter(user__trusted=False)
            case "None":
                return queryset.filter(user=None)
            case None:
                return queryset
        return queryset.filter(user=self.value())


@admin.register(models.VehicleEdit)
class VehicleEditAdmin(admin.ModelAdmin):
    list_display = ["datetime", "vehicle", "user", "changes", "notes", "url"]
    list_select_related = ["vehicle", "user"]
    list_filter = [
        "approved",
        "vehicle__withdrawn",
        UserFilter,
    ]
    raw_id_fields = ["vehicle", "livery", "user", "arbiter"]


@admin.register(models.VehicleJourney)
class VehicleJourneyAdmin(admin.ModelAdmin):
    list_display = (
        "datetime",
        "code",
        "vehicle",
        "route_name",
        "service",
        "destination",
    )
    list_select_related = ("vehicle", "service")
    raw_id_fields = ("vehicle", "service", "source", "trip")
    list_filter = (
        ("service", admin.EmptyFieldListFilter),
        ("trip", admin.EmptyFieldListFilter),
        "source",
        "vehicle__operator",
    )
    show_full_result_count = False
    ordering = ("-id",)


class LiveryAdminForm(forms.ModelForm):
    save_as = True

    class Meta:
        widgets = {
            "colours": forms.Textarea,
            "css": forms.Textarea,
            "left_css": forms.Textarea,
            "right_css": forms.Textarea,
        }


@admin.register(models.Livery)
class LiveryAdmin(SimpleHistoryAdmin):
    form = LiveryAdminForm
    search_fields = ["name"]
    actions = ["merge"]
    list_display = [
        "id",
        "name",
        "vehicles",
        "left",
        "right",
        "published",
        "updated_at",
    ]
    list_filter = [
        "published",
        "updated_at",
        ("operators", admin.RelatedOnlyFieldListFilter),
    ]
    autocomplete_fields = ["operators"]
    readonly_fields = ["left", "right", "updated_at"]
    ordering = ["-id"]

    def merge(self, request, queryset):
        queryset = queryset.order_by("id")
        if not all(
            queryset[0].colours == livery.colours
            and queryset[0].left_css == livery.left_css
            and queryset[0].right_css == livery.right_css
            for livery in queryset
        ):
            self.message_user(
                request, "You can only merge liveries that are the same", messages.ERROR
            )
        else:
            for livery in queryset[1:]:
                livery.vehicle_set.update(livery=queryset[0])
                livery.revision_from.update(from_livery=queryset[0])
                livery.revision_to.update(to_livery=queryset[0])
                livery.vehicleedit_set.update(livery=queryset[0])
            self.message_user(request, "Merged")

    @admin.display(ordering="right_css")
    def right(self, obj):
        if obj.text_colour:
            text_colour = obj.text_colour
        elif obj.white_text:
            text_colour = "#fff"
        else:
            text_colour = "#222"
        if obj.stroke_colour:
            stroke = f"stroke:{obj.stroke_colour};stroke-width:3px;paint-order:stroke"
        else:
            stroke = ""
        return format_html(
            """<svg style="height:24px;width:36px;line-height:24px;font-size:24px;background:{}">
                <text x="50%" y="80%" style="fill:{};text-anchor:middle;{}">42</text>
            </svg>""",
            obj.right_css,
            text_colour,
            stroke,
        )

    @admin.display(ordering="left_css")
    def left(self, obj):
        if obj.text_colour:
            text_colour = obj.text_colour
        elif obj.white_text:
            text_colour = "#fff"
        else:
            text_colour = "#222"
        if obj.stroke_colour:
            stroke = f"stroke:{obj.stroke_colour};stroke-width:3px;paint-order:stroke"
        else:
            stroke = ""
        return format_html(
            """<svg style="height:24px;width:36px;line-height:24px;font-size:24px;background:{}">
                <text x="50%" y="80%" style="fill:{};text-anchor:middle;{}">24</text>
            </svg>""",
            obj.left_css,
            text_colour,
            stroke,
        )

    vehicles = VehicleTypeAdmin.vehicles

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if "changelist" in request.resolver_match.view_name:
            return queryset.annotate(vehicles=SubqueryCount("vehicle"))
        return queryset


class RevisionChangeFilter(admin.SimpleListFilter):
    title = "changed field"
    parameter_name = "change"

    def lookups(self, request, model_admin):
        return (
            ("changes__reg", "reg"),
            ("changes__name", "name"),
            ("changes__branding", "branding"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value and value.startswith("changes__"):
            return queryset.filter(**{f"{value}__isnull": False})
        return queryset


@admin.register(models.VehicleRevision)
class VehicleRevisionAdmin(admin.ModelAdmin):
    raw_id_fields = [
        "from_operator",
        "to_operator",
        "from_livery",
        "to_livery",
        "vehicle",
        "user",
    ]
    list_display = ["datetime", "vehicle", "__str__", user, "message"]
    actions = ["revert"]
    list_filter = [
        RevisionChangeFilter,
        UserFilter,
        ("vehicle__operator", admin.RelatedOnlyFieldListFilter),
    ]
    list_select_related = ["from_operator", "to_operator", "vehicle", "user"]

    def revert(self, request, queryset):
        for revision in queryset.prefetch_related("vehicle"):
            for message in revision.revert():
                self.message_user(request, message)


@admin.register(models.VehicleCode)
class VehicleCodeAdmin(admin.ModelAdmin):
    raw_id_fields = ["vehicle"]
    list_display = ["code", "vehicle"]


admin.site.register(models.VehicleFeature)
