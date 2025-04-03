import datetime
from http import HTTPStatus
import json
import logging
from itertools import pairwise
from urllib.parse import unquote

import subprocess
import xmltodict
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import GEOSException, Point
from django.contrib.postgres.aggregates import StringAgg
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import Case, F, Max, OuterRef, Q, When
from django.db.models.functions import Coalesce, Now
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.cache import get_conditional_response, set_response_etag
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_safe
from django.views.generic.detail import DetailView
from haversine import Unit, haversine, haversine_vector
from redis.exceptions import ConnectionError
from sql_util.utils import Exists, SubqueryMax, SubqueryMin

from accounts.models import User
from buses.utils import cdn_cache_control
from busstops.models import SERVICE_ORDER_REGEX, Operator, Service
from busstops.utils import get_bounding_box
from bustimes.models import Garage, Route, StopTime
from bustimes.utils import contiguous_stoptimes_only, get_other_trips_in_block

from . import filters, forms
from .management.commands import import_bod_avl
from .models import (
    Livery,
    SiriSubscription,
    Vehicle,
    VehicleJourney,
    VehicleLocation,
    VehicleRevision,
    VehicleRevisionFeature,
)
from .rtpi import add_progress_and_delay
from .tasks import handle_siri_post
from .utils import apply_revision, get_revision, redis_client  # calculate_bearing,


class Vehicles:
    """for linking to an operator's /vehicles page (fleet list) in a breadcrumb list"""

    def __init__(self, vehicle=None, operator=None):
        self.vehicle = vehicle
        self.operator = operator or vehicle.operator

    def __str__(self):
        return "Vehicles"

    def get_absolute_url(self):
        url = reverse("operator_vehicles", args=(self.operator.slug,))
        if self.vehicle:
            url = f"{url}#{self.vehicle.slug}"
        return url


@require_safe
def vehicles(request):
    """index of recently AVL-enabled operators, etc"""

    operators = Operator.objects.filter(
        Exists("vehicle", filter=Q(withdrawn=False))
    ).only("name", "slug")

    new_operators = operators.annotate(
        min=SubqueryMin("vehicle__id"),
    ).order_by("-min")[:36]

    operator_journeys = VehicleJourney.objects.filter(
        latest_vehicle__operator=OuterRef("noc")
    )

    day_ago = timezone.now() - datetime.timedelta(days=1)
    status = (
        operators.filter(
            Exists(operator_journeys),
            ~Exists(operator_journeys.filter(datetime__gte=day_ago)),
        )
        .annotate(
            last_seen=SubqueryMax("vehicle__latest_journey__datetime"),
        )
        .order_by("-last_seen")
    )

    return render(
        request,
        "vehicles.html",
        {
            "status": list(status),
            "new_operators": list(new_operators),
            "operators": list(operators),
        },
    )


@cache_control(max_age=3600)
def liveries_css(request, version=0):
    styles = []
    liveries = Livery.objects.filter(published=True).order_by("id")
    for livery in liveries:
        styles += livery.get_styles()
    styles = "".join(styles)
    completed_process = subprocess.run(
        ["lightningcss", "--minify"], input=styles.encode(), capture_output=True
    )
    styles = completed_process.stdout
    return HttpResponse(styles, content_type="text/css")


features_string_agg = StringAgg(
    "features__name", ", ", ordering=["features__name"], default=""
)


def get_vehicle_order(vehicle) -> tuple[str, int, str]:
    if vehicle.notes == "Spare ticket machine":
        return ("", vehicle.fleet_number or 99999, vehicle.code)

    if vehicle.fleet_number:
        return ("", vehicle.fleet_number)

    # age-based ordering
    if not vehicle.fleet_code and len(reg := vehicle.reg) == 7 and reg[-3:].isalpha():
        if reg[:2].isalpha() and reg[2:4].isdigit():
            year = int(reg[2:4])
            if year > 50:
                return ("Z", (year - 50) * 2 + 1, "")  # year 64 (september 2014) - 29
            return ("Z", year * 2, "")  # year 14 (march 2014) - 28

        if reg[1:4].isdigit():
            return reg[0], int(reg[1:4]), reg[-3:]

    prefix, number, suffix = SERVICE_ORDER_REGEX.match(
        vehicle.fleet_code or vehicle.code
    ).groups()
    number = int(number) if number else 0
    if " " in prefix:  # McGill's
        return (suffix, number, prefix)
    return (prefix, number, suffix)


@require_safe
def operator_vehicles(request, slug=None, parent=None):
    """fleet list"""

    operators = Operator.objects.select_related("region")
    if slug:
        try:
            operator = operators.get(slug=slug.lower())
        except Operator.DoesNotExist:
            operator = get_object_or_404(
                operators, operatorcode__code=slug, operatorcode__source__name="slug"
            )
        vehicles = operator.vehicle_set
    else:
        assert parent
        operators = operators.filter(parent=parent).in_bulk()
        if not operators:
            raise Http404
        vehicles = Vehicle.objects.filter(operator__in=operators)

    if "withdrawn" not in request.GET:
        vehicles = vehicles.filter(withdrawn=False)

    vehicles = vehicles.order_by("fleet_number", "fleet_code", "reg", "code")

    if parent:
        context = {}
    else:
        vehicles = vehicles.annotate(feature_names=features_string_agg)
        vehicles = vehicles.annotate(
            pending_edits=Exists("vehiclerevision", filter=Q(pending=True))
        )
        vehicles = vehicles.select_related("latest_journey")

        context = {"object": operator, "breadcrumb": [operator.region, operator]}

    vehicles = vehicles.annotate(
        livery_name=F("livery__name"),
        vehicle_type_name=F("vehicle_type__name"),
        garage_name=Case(
            When(garage__name="", then="garage__code"),
            default="garage__name",
        ),
    )

    if not vehicles:
        raise Http404

    vehicles = sorted(vehicles, key=get_vehicle_order)
    if not parent and operator.noc in settings.ALLOW_VEHICLE_NOTES_OPERATORS:
        vehicles = sorted(vehicles, key=lambda v: v.notes)

    if parent:
        paginator = Paginator(vehicles, 1000)
        page = request.GET.get("page")
        vehicles = paginator.get_page(page)

        for v in vehicles:
            v.operator = operators[v.operator_id]

        context["paginator"] = paginator
    else:
        paginator = None

        context["features_column"] = any(vehicle.feature_names for vehicle in vehicles)

    columns = set(key for vehicle in vehicles if vehicle.data for key in vehicle.data)
    for vehicle in vehicles:
        vehicle.column_values = [
            vehicle.data and vehicle.data_get(key) or "" for key in columns
        ]
    context["columns"] = columns

    if not parent:
        now = timezone.localtime()

        # midnight or 12 hours ago, whichever happened first
        if now.hour >= 12:
            today = now - datetime.timedelta(hours=now.hour, minutes=now.minute)
            today = today.replace(second=0, microsecond=0)
        else:
            today = now - datetime.timedelta(hours=12)

        context["today"] = today

        for vehicle in vehicles:
            if vehicle.latest_journey:
                when = vehicle.latest_journey.datetime
                vehicle.last_seen = {
                    "service": vehicle.latest_journey.route_name,
                    "when": when,
                    "today": when >= today,
                }

        context["map"] = any(
            hasattr(vehicle, "last_seen") and vehicle.last_seen["today"]
            for vehicle in vehicles
        )

    garage_names = set(
        vehicle.garage_name for vehicle in vehicles if vehicle.garage_name
    )

    context = {
        **context,
        "parent": parent,
        "vehicles": vehicles,
        "branding_column": any(vehicle.branding for vehicle in vehicles),
        "name_column": any(vehicle.name for vehicle in vehicles),
        "notes_column": any(
            vehicle.notes and not vehicle.is_spare_ticket_machine()
            for vehicle in vehicles
        ),
        "garage_column": len(garage_names) > 1,
    }

    return render(request, "operator_vehicles.html", context)


@cdn_cache_control(max_age=300)
@require_safe
def operator_map(request, slug):
    operator = get_object_or_404(Operator.objects.select_related("region"), slug=slug)

    return render(
        request,
        "operator_map.html",
        {
            "object": operator,
            "operator": operator,
            "breadcrumb": [operator.region, operator],
        },
    )


def operator_debug(request, slug):
    operator = get_object_or_404(Operator, slug=slug)

    services = operator.service_set.filter(current=True)

    services = services.annotate(
        current_routes=Exists(
            Route.objects.filter(
                Q(end_date=None) | Q(end_date__gte=Now()), service=OuterRef("id")
            )
        )
    )

    pipe = redis_client.pipeline(transaction=False)
    for service in services:
        pipe.exists(f"service{service.id}vehicles")
    tracking = pipe.execute()

    for service, service_tracking in zip(services, tracking):
        service.last_tracked = service_tracking

    return render(
        request,
        "operator_debug.html",
        {
            "object": operator,
            "breadcrumb": [operator],
            "services": services,
        },
    )


def respond_conditionally(request, response):
    if not response.has_header("ETag"):
        set_response_etag(response)

    etag = response.get("ETag")
    return get_conditional_response(
        request,
        etag=etag,
        response=response,
    )


@require_safe
def vehicles_json(request) -> JsonResponse:
    try:
        bounds = get_bounding_box(request)
    except KeyError:
        bounds = None
    except (GEOSException, ValueError):
        return HttpResponseBadRequest()

    all_vehicles = (
        Vehicle.objects.select_related("vehicle_type")
        .annotate(
            feature_names=features_string_agg,
            service_line_name=F("latest_journey__trip__route__line_name"),
            service_slug=F("latest_journey__service__slug"),
            colour=F("livery__colour"),
        )
        .defer("data", "latest_journey_data")
    )

    vehicle_ids = None
    set_names = None
    service_ids = None
    operator_ids = None

    if bounds is not None:
        # ids of vehicles within box
        xmin, ymin, xmax, ymax = bounds.extent

        try:
            # convert to kilometres (only for Redis to convert back to degrees)
            width = haversine((ymin, xmax), (ymin, xmin))
            height = haversine((ymin, xmax), (ymax, xmax))
        except ValueError as e:
            return HttpResponseBadRequest(e)

        vehicle_ids = redis_client.geosearch(
            "vehicle_location_locations",
            longitude=str((xmax + xmin) / 2),
            latitude=str((ymax + ymin) / 2),
            unit="km",
            width=str(width),
            height=str(height),
        )

    elif "service" in request.GET:
        try:
            service_ids = [
                int(service_id) for service_id in request.GET["service"].split(",")
            ]
        except ValueError:
            return HttpResponseBadRequest()
        set_names = [f"service{service_id}vehicles" for service_id in service_ids]
    elif "operator" in request.GET:
        operator_ids = request.GET["operator"].split(",")
        set_names = [f"operator{operator_id}vehicles" for operator_id in operator_ids]
    elif "id" in request.GET:
        # specified vehicle ids
        vehicle_ids = request.GET["id"].split(",")
    else:
        # ids of all vehicles
        vehicle_ids = redis_client.zrange("vehicle_location_locations", 0, -1)

    if set_names:
        vehicle_ids = list(redis_client.sunion(set_names))

    vehicle_ids = [int(vehicle_id) for vehicle_id in vehicle_ids]

    vehicle_ids.sort()  # for etag stableness

    vehicle_locations = redis_client.mget(
        [f"vehicle{vehicle_id}" for vehicle_id in vehicle_ids]
    )
    vehicle_locations = [
        json.loads(item) if item else item for item in vehicle_locations
    ]

    # remove expired items from 'vehicle_location_locations'
    to_remove = [
        vehicle_id
        for vehicle_id, item in zip(vehicle_ids, vehicle_locations)
        if not item
    ]

    if to_remove:
        redis_client.zrem("vehicle_location_locations", *to_remove)

    journeys = cache.get_many(
        [f"journey{item['journey_id']}" for item in vehicle_locations if item]
    )

    # get vehicles from the database if they have unexpired locations, and weren't in the cache
    try:
        vehicles = all_vehicles.in_bulk(
            [
                vehicle_id
                for vehicle_id, item in zip(vehicle_ids, vehicle_locations)
                if item and f"journey{item['journey_id']}" not in journeys
            ]
        )
    except OperationalError:
        vehicles = {}

    locations = []

    trip = request.GET.get("trip")
    if trip:
        trip = int(trip)

    journeys_to_cache_later = {}

    for vehicle_id, item in zip(vehicle_ids, vehicle_locations):
        if item:
            journey_cache_key = f"journey{item['journey_id']}"

            if journey_cache_key in journeys:
                item.update(journeys[journey_cache_key])
            elif vehicles:
                try:
                    vehicle = vehicles[vehicle_id]
                except KeyError:
                    continue  # vehicle was deleted?
                else:
                    journey = {"vehicle": vehicle.get_json()}
                    if vehicle.service_slug:
                        journey["service"] = {
                            "url": f"/services/{vehicle.service_slug}",
                            "line_name": vehicle.service_line_name
                            or item.get("service")
                            and item["service"]["line_name"],
                        }
                    journeys_to_cache_later[journey_cache_key] = journey
                    item.update(journey)

            if (
                "progress" not in item
                and "trip_id" in item
                and (len(vehicle_ids) == 1 or trip and item["trip_id"] == trip)
            ):
                add_progress_and_delay(item)

        if (
            service_ids
            and (not item or item.get("service_id") not in service_ids)
            or operator_ids
            and not item
        ):
            for set_name in set_names:
                redis_client.srem(set_name, vehicle_id)
        elif item:
            locations.append(item)

    if journeys_to_cache_later:
        cache.set_many(journeys_to_cache_later, 3600)  # an hour

    response = JsonResponse(locations, safe=False)
    if not locations:
        response.status_code = HTTPStatus.NOT_FOUND

    return respond_conditionally(request, response)


def get_dates(vehicle=None, service=None):
    if not vehicle:
        # the database query for a service is too slow
        return

    key = f"vehicle:{vehicle.id}:dates"
    journeys = vehicle.vehiclejourney_set

    dates = cache.get(key)

    if dates and vehicle.latest_journey:
        latest_date = timezone.localdate(vehicle.latest_journey.datetime)
        if dates[-1] < latest_date:
            dates.append(latest_date)
            # we'll update the cache below
        else:
            return dates

    if not dates:
        try:
            dates = list(journeys.dates("datetime", "day"))
        except OperationalError:
            return

    if dates:
        now = timezone.localtime()
        time_to_midnight = datetime.timedelta(days=1) - datetime.timedelta(
            hours=now.hour, minutes=now.minute, seconds=now.second
        )
        if dates[-1] == now.date():  # today
            time_to_midnight += datetime.timedelta(days=1)
        time_to_midnight = time_to_midnight.total_seconds()
        if time_to_midnight > 0:
            cache.set(key, dates, time_to_midnight)

    return dates


def journeys_list(request, journeys, service=None, vehicle=None) -> dict:
    """list of VehicleJourneys (and dates) for a service or vehicle"""

    dates = get_dates(service=service, vehicle=vehicle)

    context = {}

    form = forms.DateForm(request.GET)
    if form.is_valid():
        date = form.cleaned_data["date"]
    else:
        date = None

    if not date and dates is None:
        if vehicle and vehicle.latest_journey:
            date = timezone.localdate(vehicle.latest_journey.datetime)
        else:
            date = journeys.aggregate(max_date=Max("datetime__date"))["max_date"]

    if dates:
        context["dates"] = dates
        if not date:
            date = context["dates"][-1]

    if date:
        context["date"] = date

        journeys = (
            journeys.filter(datetime__date=date).select_related("trip").order_by("id")
        )

        if dates:
            if date not in dates:
                dates.append(date)
                dates.sort()
            elif not journeys:
                cache.delete(f"vehicle:{vehicle.id}:dates")

        context["journeys"] = journeys

    elif service:
        raise Http404

    if not date or not journeys:
        return context

    context["journeys"] = journeys = list(journeys)

    # annotate journeys with whether each one has some location history in redis
    # (in order to show the "Map" link or not)
    if redis_client:
        try:
            pipe = redis_client.pipeline(transaction=False)
            for journey in journeys:
                pipe.exists(journey.get_redis_key())

            locations = pipe.execute()
        except (ConnectionError, AttributeError):
            pass
        else:
            for journey, location in zip(journeys, locations):
                journey.locations = bool(location)

    # "Track this bus" button
    if vehicle and vehicle.latest_journey_id:
        if redis_client and redis_client.get(f"vehicle{vehicle.id}"):
            context["tracking"] = f"#journeys/{vehicle.latest_journey_id}"

        # predict next workings
        if vehicle.latest_journey_id == journeys[-1].pk:
            trips = [journey.trip for journey in journeys if journey.trip]
            if trips:
                last_trip = trips[-1]
                if last_trip.block and all(
                    trip.block == last_trip.block for trip in trips[-3:-1]
                ):
                    context["predictions"] = (
                        get_other_trips_in_block(
                            last_trip,
                            date,
                        )
                        .filter(
                            start__gte=last_trip.end,
                        )
                        .annotate(
                            destination_name=Coalesce(
                                F("destination__locality__name"),
                                "destination__common_name",
                            ),
                            line_name=F("route__line_name"),
                        )
                    )
                    for a, b in pairwise(context["predictions"]):
                        if a.end > b.start:
                            del context["predictions"]
                            break

    return context


@require_safe
def service_vehicles_history(request, slug):
    service: Service = get_object_or_404(Service.objects.with_line_names(), slug=slug)

    context = journeys_list(
        request, service.vehiclejourney_set.select_related("vehicle"), service=service
    )

    operator = service.operator.select_related("region").first()
    return render(
        request,
        "vehicles/vehicle_detail.html",
        {
            **context,
            "garages": Garage.objects.filter(
                Exists("trip__route", filter=Q(route__service=service))
            ),
            "breadcrumb": [operator, service],
            "object": service,
        },
    )


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related(
        "operator", "operator__region", "vehicle_type", "livery", "latest_journey"
    ).prefetch_related("features")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        journeys = self.object.vehiclejourney_set.select_related("service")
        journeys = journeys.annotate(
            line_name=Coalesce("trip__route__line_name", "route_name")
        )

        context = {
            **context,
            **journeys_list(self.request, journeys, vehicle=self.object),
        }
        del journeys

        if self.object.reg:
            # for search engine purposes, use reg without space:
            context["title"] = self.object.reg
            if self.object.fleet_code:
                context["title"] = self.object.fleet_code + " - " + context["title"]
        else:
            context["title"] = str(self.object)

        if "journeys" in context:
            garages = set(
                journey.trip.garage_id
                for journey in context["journeys"]
                if journey.trip and journey.trip.garage_id
            )
            if len(garages) == 1:
                context["garage"] = Garage.objects.get(id=garages.pop())

        if self.object.operator:
            context["breadcrumb"] = [
                self.object.operator,
                Vehicles(vehicle=self.object),
            ]

            context["previous"] = self.object.get_previous()
            context["next"] = self.object.get_next()

        return context


def record_ip_address(request):
    ip_address = request.headers.get("cf-connecting-ip")
    if request.user.ip_address != ip_address:
        request.user.ip_address = ip_address
        request.user.save(update_fields=["ip_address"])


def check_user(request):
    if settings.DISABLE_EDITING and not request.user.has_perm(
        "vehicles.change_vehicle"
    ):
        raise PermissionDenied(
            """This bit of the website is in “read-only” mode.
            Sorry for the inconvenience.
            Don’t worry, you can still enjoy all of the main features of the website."""
        )

    if request.user.trusted is False:
        raise PermissionDenied

    if (
        not request.user.trusted
        and timezone.now() - request.user.date_joined < datetime.timedelta(hours=1)
        and request.user.vehiclerevision_set.count() > 4
    ):
        raise PermissionDenied(
            "As your account is so new, please wait a bit before editing any more vehicles"
        )


revision_display_related_fields = (
    "from_type",
    "to_type",
    "from_operator",
    "to_operator",
    "from_livery",
    "to_livery",
)


@login_required
def edit_vehicle(request, **kwargs):
    record_ip_address(request)
    check_user(request)

    vehicle = get_object_or_404(
        Vehicle.objects.select_related(
            "vehicle_type", "livery", "operator", "latest_journey"
        ),
        **kwargs,
    )

    if not request.user.is_superuser and not vehicle.is_editable():
        raise PermissionDenied()

    form_data = request.POST or None

    if not request.user.has_perm("vehicles.add_vehiclerevision"):
        form = forms.RulesForm(form_data)
        if form.is_valid():
            request.user.user_permissions.add(
                Permission.objects.get(codename="add_vehiclerevision")
            )
            form_data = None
        else:
            return render(
                request, "rules.html", {"breadcrumb": [vehicle], "form": form}
            )

    if (
        vehicle.operator_id
        and (
            User.operators.through.objects.filter(operator=vehicle.operator_id)
            .exclude(user=request.user)
            .exists()
        )
        and not request.user.operators.filter(noc=vehicle.operator_id).exists()
    ):
        raise PermissionDenied(
            f'Editing {vehicle.operator} vehicles is restricted to "local experts"'
        )

    context = {
        "previous": vehicle.get_previous(),
        "next": vehicle.get_next(),
    }

    revision = None

    try:
        context["vehicle_unique_id"] = vehicle.latest_journey_data["Extensions"][
            "VehicleJourney"
        ]["VehicleUniqueId"]
    except (KeyError, TypeError):
        pass

    form = forms.EditVehicleForm(
        form_data,
        vehicle=vehicle,
        user=request.user,
        sibling_vehicles=(context["previous"], context["next"]),
    )

    context["livery"] = vehicle.livery

    if form_data:
        if form.has_changed() is False or form.changed_data == ["summary"]:
            form.add_error(None, "You haven't changed anything")

        if form.is_valid():
            data = {key: form.cleaned_data[key] for key in form.changed_data}

            revision, features = get_revision(vehicle, data)

            revision.user = request.user
            revision.created_at = timezone.now()
            revision.pending = True
            try:
                with transaction.atomic():
                    revision.save()
                    VehicleRevisionFeature.objects.bulk_create(features)

                    if request.user.trusted:
                        apply_revision(revision, features)
                        revision.pending = False
                        revision.save(update_fields=["pending"])

                    context["revision"] = revision
                    form = None

            except IntegrityError as e:
                error = "There's already a pending edit for that"
                if "unique_pending_livery" in e.args[0]:
                    form.add_error("colours", error)
                elif "unique_pending_type" in e.args[0]:
                    form.add_error("vehicle_type", error)
                elif "unique_pending_operator" in e.args[0]:
                    form.add_error("operator", error)
                elif "vehicle_operator_and_code" in e.args[0]:
                    error = f"{form.cleaned_data['operator']} already has a vehicle with the code {vehicle.code}"
                    form.add_error("operator", error)
                else:
                    raise

        if form:
            context["livery"] = form.cleaned_data.get("colours")

    if form:
        context["pending_edits"] = (
            vehicle.vehiclerevision_set.filter(
                Q(pending=True) | Q(created_at__gte=Now() - datetime.timedelta(days=7))
            )
            .select_related(*revision_display_related_fields)
            .prefetch_related("vehiclerevisionfeature_set__feature")
        )

    if vehicle.operator:
        context["breadcrumb"] = [vehicle.operator, Vehicles(vehicle=vehicle), vehicle]
    else:
        context["breadcrumb"] = [vehicle]

    return render(
        request,
        "edit_vehicle.html",
        {
            **context,
            "form": form,
            "object": vehicle,
            "vehicle": vehicle,
        },
    )


@require_POST
@login_required
@transaction.atomic
def vehicle_revision_action(request, revision_id, action):
    revision = get_object_or_404(
        VehicleRevision.objects.select_related(
            *revision_display_related_fields, "vehicle"
        )
        .filter(Q(pending=True) | Q(approved_by=request.user))
        .select_for_update(of=["self"]),
        id=revision_id,
    )

    if action == "disapprove" and request.user.id == revision.user_id:
        revision.delete()  # cancel one's own edit
        return HttpResponse("")
    else:
        assert request.user.trusted

    revision.disapproved_reason = unquote(request.headers.get("HX-Prompt", ""))
    revision.approved_by = request.user
    revision.approved_at = Now()

    if action == "apply":
        apply_revision(revision)
        revision.pending = False
        revision.disapproved = False
    elif action == "disapprove":
        revision.pending = False
        revision.disapproved = True

    revision.save()

    return render(request, "vehicle_revision.html", {"revision": revision})


@require_safe
def vehicle_edits(request):
    revisions = (
        VehicleRevision.objects.select_related(
            *revision_display_related_fields, "user", "vehicle"
        )
        .prefetch_related("vehiclerevisionfeature_set__feature")
        .order_by("-id")
    )

    f = filters.VehicleRevisionFilter(
        request.GET or {"status": "approved"}, queryset=revisions
    )
    if request.user.is_anonymous or not (
        request.user.trusted
        or request.user.is_superuser
        or request.GET.get("user") == str(request.user.id)
    ):
        f.filters["status"].field.choices = [("approved", "approved")]

    if f.is_valid():
        paginator = Paginator(f.qs, 100)
        page = paginator.get_page(request.GET.get("page"))
    else:
        page = None

    return render(
        request,
        "vehicle_edits.html",
        {
            "filter": f,
            "revisions": page,
        },
    )


class VehicleJourneyDetailView(DetailView):
    model = VehicleJourney


@require_safe
def journey_json(request, pk, vehicle_id=None, service_id=None):
    journey = get_object_or_404(
        VehicleJourney.objects.select_related("trip", "vehicle"), pk=pk
    )

    data = {
        "vehicle_id": journey.vehicle_id,
        "service_id": journey.service_id,
        "trip_id": journey.trip_id,
        "datetime": journey.datetime,
        "route_name": journey.route_name,
        "code": journey.code,
        "destination": journey.destination,
        "direction": journey.direction,
        "current": journey.vehicle and journey.id == journey.vehicle.latest_journey_id,
    }

    if redis_client:
        locations = redis_client and redis_client.lrange(journey.get_redis_key(), 0, -1)
    else:
        locations = None

    if locations:
        locations = [
            VehicleLocation.decode_appendage(location) for location in locations
        ]
        locations.sort(key=lambda location: location["datetime"])

        data["locations"] = []

        stationary = False
        previous = None
        previous_latlong = None
        for location in locations:
            latlong = Point(location["coordinates"])

            if previous_latlong:
                distance = latlong.distance(previous_latlong)
                if distance < 0.0005:
                    stationary = True
                elif stationary:
                    # mark end of stationary period
                    data["locations"].append(previous)
                    stationary = False

            if not stationary:
                data["locations"].append(location)

                previous_latlong = latlong

            previous = location

        if stationary:  # add last location
            data["locations"].append(location)

        del locations

    # if not trip - calculate using time and first location?
    # if not trip:
    #     Trip

    if journey.trip:
        data["stops"] = []
        # previous_latlong = None

        trips = journey.trip.get_trips()
        if trips == [journey.trip]:
            stoptimes = trips[0].stoptime_set.select_related("stop__locality")
        else:
            stoptimes = (
                StopTime.objects.filter(trip__in=trips)
                .order_by("trip__start", "id")
                .select_related("stop__locality")
            )
            stoptimes = contiguous_stoptimes_only(stoptimes, journey.trip.id)

        for stoptime in stoptimes:
            stop = stoptime.stop
            # if stop := stoptime.stop:
            #     if stop.latlong:
            #         if previous_latlong:
            #             heading = calculate_bearing(previous_latlong, stop.latlong)
            #         else:
            #             heading = None
            #         previous_latlong = stop.latlong
            data["stops"].append(
                {
                    "id": stoptime.id,
                    "atco_code": stoptime.stop_id,
                    "name": (
                        stop.get_name_for_timetable() if stop else stoptime.stop_code
                    ),
                    "aimed_arrival_time": stoptime.arrival_time(),
                    "aimed_departure_time": stoptime.departure_time(),
                    "minor": stoptime.is_minor(),
                    "heading": stop and stop.get_heading(),
                    "coordinates": stop and stop.latlong and stop.latlong.coords,
                }
            )

    if "stops" in data and "locations" in data:
        # only stops with coordinates
        stops = [stop for stop in data["stops"] if stop["coordinates"]]
        if stops:
            stop_coords = [stop["coordinates"][::-1] for stop in stops]
            vehicle_coords = [
                location["coordinates"][::-1] for location in data["locations"]
            ]
            try:
                haversine_vector_results = haversine_vector(
                    stop_coords,
                    vehicle_coords,
                    Unit.METERS,
                    comb=True,
                )
            except ValueError as e:
                logging.exception(e)
            else:
                for distances, location in zip(
                    haversine_vector_results, data["locations"]
                ):
                    distance, nearest_stop = min(
                        zip(distances, stops), key=lambda x: x[0]
                    )
                    if distance < 100:
                        nearest_stop["actual_departure_time"] = location["datetime"]

    if vehicle_id:
        next_previous_filter = {"vehicle_id": vehicle_id}
    elif service_id:
        next_previous_filter = {
            "service_id": service_id,
            "datetime__date": journey.datetime,
        }
        data["vehicle"] = str(journey.vehicle)
    else:
        next_previous_filter = {"vehicle_id": journey.vehicle_id}

    try:
        next_journey = journey.get_next_by_datetime(**next_previous_filter)
    except VehicleJourney.DoesNotExist:
        pass
    else:
        data["next"] = {"id": next_journey.id, "datetime": next_journey.datetime}

    try:
        previous_journey = journey.get_previous_by_datetime(**next_previous_filter)
    except VehicleJourney.DoesNotExist:
        pass
    else:
        data["previous"] = {
            "id": previous_journey.id,
            "datetime": previous_journey.datetime,
        }

    return JsonResponse(data)


@require_safe
def latest_journey_debug(request, **kwargs):
    vehicle = get_object_or_404(Vehicle, **kwargs)
    if not vehicle.latest_journey_data:
        raise Http404
    return JsonResponse(vehicle.latest_journey_data)


def debug(request):
    form = forms.DebuggerForm(request.POST or None)
    result = None
    if form.is_valid():
        data = form.cleaned_data["data"]
        try:
            item = json.loads(data)
        except ValueError as e:
            form.add_error("data", e)
        else:
            vehicle = None
            journey = None
            connection.force_debug_cursor = True
            try:
                with transaction.atomic():
                    command = import_bod_avl.Command()
                    command.do_source()
                    vehicle, created = command.get_vehicle(item)
                    journey = command.get_journey(item, vehicle)
                    if not journey.datetime:
                        journey.datetime = command.get_datetime(item)
                    raise Exception
            except Exception:
                pass
            connection.force_debug_cursor = False

            result = {
                "vehicle": vehicle,
                "journey": journey,
                "queries": connection.queries,
            }

    return render(request, "vehicles/debug.html", {"form": form, "result": result})


@csrf_exempt
def siri_post(request, uuid):
    get_object_or_404(SiriSubscription, uuid=uuid)

    if request.method == "GET":
        return HttpResponse(
            cache.get("last_siri_post")["body"], content_type="text/xml"
        )

    body = request.body.decode()
    data = xmltodict.parse(body, force_list=["VehicleActivity"])

    handle_siri_post(uuid, data)

    cache.set("last_siri_post", {"headers": request.headers, "body": body})

    return HttpResponse("")


@csrf_exempt
@require_POST
def overland(request, uuid):
    get_object_or_404(SiriSubscription, uuid=uuid)

    data = json.loads(request.body)

    for item in data["locations"][-1:]:
        when = item["properties"]["timestamp"]
        device_id = item["properties"]["device_id"]
        operator, vehicle, line_name, journey_ref = device_id.split(":")
        lon, lat = item["geometry"]["coordinates"]
        activity = {
            "RecordedAtTime": when,
            "MonitoredVehicleJourney": {
                "OperatorRef": operator,
                "VehicleRef": vehicle,
                "PublishedLineName": line_name,
                "VehicleJourneyRef": journey_ref,
                "VehicleLocation": {
                    "Longitude": lon,
                    "Latitude": lat,
                },
            },
        }

        handle_siri_post(
            uuid,
            {
                "Siri": {
                    "ServiceDelivery": {
                        "ResponseTimestamp": when,
                        "VehicleMonitoringDelivery": {
                            "VehicleActivity": [activity],
                            "SubscriptionRef": "",
                        },
                    }
                }
            },
        )

    # https://github.com/aaronpk/Overland-iOS#api
    return JsonResponse({"result": "ok"})
