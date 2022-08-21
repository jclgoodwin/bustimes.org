import json
import datetime
from urllib.parse import urlencode
from ciso8601 import parse_datetime
from haversine import haversine, haversine_vector, Unit

from django.db import IntegrityError, OperationalError, transaction, connection
from django.db.models import F, Case, When, Q, OuterRef, Max
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.aggregates import StringAgg
from django.http import (
    HttpResponse,
    JsonResponse,
    Http404,
    HttpResponseBadRequest,
    QueryDict,
)
from django.views.generic.detail import DetailView
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from sql_util.utils import Exists, SubqueryCount, SubqueryMin, SubqueryMax

from buses.utils import varnish_ban
from busstops.utils import get_bounding_box
from busstops.models import Operator, Service
from bustimes.models import Garage
from .models import (
    Vehicle,
    VehicleJourney,
    VehicleEdit,
    VehicleEditFeature,
    VehicleRevision,
    VehicleRevisionFeature,
    Livery,
    VehicleEditVote,
)
from . import filters
from . import forms
from .utils import (
    redis_client,
    get_vehicle_edit,
    do_revision,
    do_revisions,
    liveries_css_version,
)
from .management.commands import import_bod_avl


class Vehicles:
    """for linking to an operator's /vehicles page (fleet list) in a breadcrumb list"""

    def __init__(self, operator):
        self.operator = operator

    def __str__(self):
        return "Vehicles"

    def get_absolute_url(self):
        return reverse("operator_vehicles", args=(self.operator.slug,))


@require_GET
def vehicles(request):
    """index of recently AVL-enabled operators, etc"""

    operators = Operator.objects.filter(
        Exists("vehicle", filter=Q(withdrawn=False))
    ).only("name", "slug")

    new_operators = operators.annotate(min=SubqueryMin("vehicle__id"),).order_by(
        "-min"
    )[:36]

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


@require_GET
def map(request):
    return render(request, "map.html", {"liveries_css_version": liveries_css_version()})


@require_GET
def liveries_css(request, version=None):
    styles = []
    liveries = Livery.objects.filter(published=True).order_by("id")
    for livery in liveries:
        styles += livery.get_styles()
    return HttpResponse("".join(styles), content_type="text/css")


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
    elif parent:
        operators = list(operators.filter(parent=parent))
        if not operators:
            raise Http404
        vehicles = Vehicle.objects.filter(operator__in=operators).select_related(
            "operator"
        )
        operator = operators[0]

    if "withdrawn" not in request.GET:
        vehicles = vehicles.filter(withdrawn=False)

    vehicles = vehicles.order_by("fleet_number", "fleet_code", "reg", "code")
    if not parent:
        vehicles = vehicles.annotate(feature_names=StringAgg("features__name", ", "))
        vehicles = vehicles.annotate(
            pending_edits=Exists("vehicleedit", filter=Q(approved=None))
        )
        vehicles = vehicles.select_related("latest_journey")

    vehicles = vehicles.annotate(
        vehicle_type_name=F("vehicle_type__name"),
        garage_name=Case(
            When(garage__name="", then="garage__code"),
            default="garage__name",
        ),
    ).select_related("livery")

    context = {"breadcrumb": [operator.region, operator]}

    form = request.path.endswith("/edit")

    now = timezone.localtime()

    if form:
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login/?next={request.path}")

        context["breadcrumb"].append(Vehicles(operator))
        initial = {
            "operator": operator,
        }
        form = forms.EditVehiclesForm(
            request.POST or None, initial=initial, operator=operator, user=request.user
        )

        if request.POST:
            vehicle_ids = request.POST.getlist("vehicle")
            if not vehicle_ids:
                form.add_error(None, "Select some vehicles to change")
            if not form.has_really_changed():
                form.add_error(None, "You haven't changed anything")
            elif form.is_valid() and request.user.trusted is not False:
                data = {key: form.cleaned_data[key] for key in form.changed_data}

                ticked_vehicles = Vehicle.objects.filter(id__in=vehicle_ids)
                if "features" in data:
                    ticked_vehicles = ticked_vehicles.prefetch_related("features")

                revisions, features, changed_fields = do_revisions(
                    ticked_vehicles, data, request.user
                )
                if not features:
                    revisions = [revision for revision in revisions if str(revision)]

                if revisions:
                    if changed_fields:
                        Vehicle.objects.bulk_update(
                            (revision.vehicle for revision in revisions), changed_fields
                        )
                    for revision in revisions:
                        revision.datetime = now
                    VehicleRevision.objects.bulk_create(revisions)
                    VehicleRevisionFeature.objects.bulk_create(features)
                    varnish_ban("/vehicles/history")
                    context["revisions"] = len(revisions)

                if data:
                    # this will fetch the vehicles list
                    # - slightly important that it occurs before any change of operator
                    edits = [
                        get_vehicle_edit(vehicle, data, now, request)
                        for vehicle in ticked_vehicles
                    ]
                    features = [
                        feature for _, features, _ in edits for feature in features
                    ]
                    edits = VehicleEdit.objects.bulk_create(
                        edit for edit, features, changed in edits if changed or features
                    )
                    VehicleEditFeature.objects.bulk_create(features)
                    context["edits"] = edits

                form = forms.EditVehiclesForm(
                    initial=initial, operator=operator, user=request.user
                )

    vehicles = sorted(vehicles, key=lambda v: Service.get_line_name_order(v.fleet_code))
    if operator.name == "National Express":
        vehicles = sorted(vehicles, key=lambda v: v.notes)

    if not vehicles:
        raise Http404

    if parent:
        paginator = Paginator(vehicles, 1000)
        page = request.GET.get("page")
        vehicles = paginator.get_page(page)
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
        # midnight or 12 hours ago, whichever happened first
        if now.hour >= 12:
            today = now - datetime.timedelta(hours=now.hour, minutes=now.minute)
            today = today.replace(second=0, microsecond=0)
        else:
            today = now - datetime.timedelta(hours=12)

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

    context = {
        **context,
        "parent": parent,
        "object": operator,
        "vehicles": vehicles,
        "code_column": any(vehicle.fleet_number_mismatch() for vehicle in vehicles),
        "branding_column": any(
            vehicle.branding and vehicle.branding != "None" for vehicle in vehicles
        ),
        "name_column": any(vehicle.name for vehicle in vehicles),
        "notes_column": any(
            vehicle.notes and vehicle.notes != "Spare ticket machine"
            for vehicle in vehicles
        ),
        "garage_column": any(vehicle.garage_name for vehicle in vehicles),
        "form": form,
        "liveries_css_version": liveries_css_version(),
    }

    return render(request, "operator_vehicles.html", context)


@require_GET
def operator_map(request, slug):
    operator = get_object_or_404(Operator.objects.select_related("region"), slug=slug)

    return render(
        request,
        "operator_map.html",
        {
            "object": operator,
            "operator": operator,
            "breadcrumb": [operator.region, operator],
            "liveries_css_version": liveries_css_version(),
        },
    )


@require_GET
def vehicles_json(request) -> JsonResponse:
    try:
        bounds = get_bounding_box(request)
    except KeyError:
        bounds = None

    all_vehicles = (
        Vehicle.objects.select_related("vehicle_type")
        .annotate(
            feature_names=StringAgg("features__name", ", "),
            service_line_name=F("latest_journey__trip__route__line_name"),
            service_slug=F("latest_journey__service__slug"),
        )
        .defer("data", "latest_journey_data")
    )

    vehicles = all_vehicles
    vehicle_ids = None
    service_ids = None

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
        vehicle_ids = list(
            redis_client.sunion(
                [f"service{service_id}vehicles" for service_id in service_ids]
            )
        )
    elif "operator" in request.GET:
        vehicles = vehicles.filter(
            operator__in=request.GET["operator"].split(",")
        ).in_bulk()
    elif "id" in request.GET:
        # specified vehicle ids
        vehicle_ids = request.GET["id"].split(",")
    else:
        # ids of all vehicles
        vehicle_ids = redis_client.zrange("vehicle_location_locations", 0, -1)

    if vehicle_ids is None:
        vehicle_ids = list(vehicles.keys())

    vehicle_locations = redis_client.mget(
        [f"vehicle{int(vehicle_id)}" for vehicle_id in vehicle_ids]
    )
    vehicle_locations = [
        json.loads(item) if item else item for item in vehicle_locations
    ]

    if type(vehicles) is not dict:
        # remove expired items from 'vehicle_location_locations'
        to_remove = [
            vehicle_ids[i] for i, item in enumerate(vehicle_locations) if not item
        ]

        if to_remove:
            redis_client.zrem("vehicle_location_locations", *to_remove)

        journeys = cache.get_many(
            [f"journey{item['journey_id']}" for item in vehicle_locations if item]
        )

        # only get vehicles with unexpired locations
        try:
            vehicles = vehicles.in_bulk(
                [
                    vehicle_ids[i]
                    for i, item in enumerate(vehicle_locations)
                    if item and f"journey{item['journey_id']}" not in journeys
                ]
            )
        except OperationalError:
            vehicles = {}
    else:
        journeys = {}

    locations = []

    trip = request.GET.get("trip")
    if trip:
        trip = int(trip)

    journeys_to_cache_later = {}

    for i, item in enumerate(vehicle_locations):
        vehicle_id = int(vehicle_ids[i])
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
                    journey = {"vehicle": vehicle.get_json(item["heading"])}
                    if vehicle.service_slug:
                        journey["service"] = {
                            "url": f"/services/{vehicle.service_slug}",
                            "line_name": vehicle.service_line_name
                            or item.get("service") and item["service"]["line_name"],
                        }
                    journeys_to_cache_later[journey_cache_key] = journey
                    item.update(journey)

            del item["journey_id"]

            if (
                trip
                and "delay" not in item
                and "trip_id" in item
                and item["trip_id"] == trip
            ):
                vj = VehicleJourney(service_id=item["service_id"], trip_id=trip)
                progress = vj.get_progress(*item["coordinates"])
                if progress:
                    prev_stop, next_stop = progress
                    item["progress"] = {
                        "prev_stop": prev_stop.stop_id,
                        "next_stop": next_stop.stop_id,
                    }
                    when = parse_datetime(item["datetime"])
                    when = timezone.localtime(when)
                    when = datetime.timedelta(
                        hours=when.hour, minutes=when.minute, seconds=when.second
                    )

                    prev_time = prev_stop.departure_or_arrival()
                    next_time = next_stop.arrival_or_departure()

                    # correct for timetable times being > 24 hours:
                    if when - prev_time < -datetime.timedelta(hours=12):
                        when += datetime.timedelta(hours=24)

                    if prev_time <= when <= next_time:
                        delay = 0
                    elif prev_time < when:
                        delay = (when - next_time).total_seconds()  # late
                    else:
                        delay = (when - prev_time).total_seconds()  # early
                    item["delay"] = delay

        if service_ids and (not item or item.get("service_id") not in service_ids):
            for service_id in service_ids:
                redis_client.srem(f"service{service_id}vehicles", vehicle_id)
        elif item:
            locations.append(item)

    if journeys_to_cache_later:
        cache.set_many(journeys_to_cache_later, 3600)  # an hour

    if not locations and "id" in request.GET:
        vehicles = all_vehicles.in_bulk(vehicle_ids)
        for vehicle_id, vehicle in vehicles.items():
            location = redis_client.lindex(f"journey{vehicle.latest_journey_id}", -1)
            if location:
                location = json.loads(location)
                item = {
                    "coordinates": location[1],
                    "heading": location[2],
                    "datetime": location[0],
                }
                if vehicle.service_slug:
                    item["service"] = {
                        "line_name": vehicle.service_line_name,
                        "url": f"/services/{vehicle.service_slug}",
                    }
                else:
                    item["service"] = {
                        "line_name": vehicle.latest_journey.route_name,
                    }

                locations.append(item)

    return JsonResponse(locations, safe=False)


def get_dates(vehicle=None, service=None):
    if vehicle:
        key = f"vehicle:{vehicle.id}:dates"
        journeys = vehicle.vehiclejourney_set
    else:
        key = f"service:{service.id}:dates"
        journeys = service.vehiclejourney_set

    dates = cache.get(key)

    if not dates and vehicle:
        # return
        try:
            dates = list(journeys.dates("datetime", "day"))
        except OperationalError:
            return

        if dates:
            now = timezone.localtime()
            if dates[-1] == now.date():
                time_to_midnight = (
                    datetime.timedelta(days=1)
                    - datetime.timedelta(
                        hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                ).total_seconds()
                if time_to_midnight > 0:
                    cache.set(key, dates, time_to_midnight)

    return dates


def journeys_list(request, journeys, service=None, vehicle=None):
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

    if date or dates:
        context["dates"] = dates
        if not date:
            date = context["dates"][-1]
        context["date"] = date

        journeys = (
            journeys.filter(datetime__date=date).select_related("trip").order_by("id")
        )

        pipe = redis_client.pipeline(transaction=False)
        for journey in journeys:
            pipe.exists(f"journey{journey.id}")

        locations = pipe.execute()

        previous = None

        for i, journey in enumerate(journeys):
            journey.locations = locations[i]

            if journey.locations:
                if previous:
                    previous.next = journey
                    journey.previous = previous
                previous = journey

        context["journeys"] = journeys
    elif service:
        raise Http404

    return context


@require_GET
def service_vehicles_history(request, slug):
    service = get_object_or_404(Service.objects.with_line_names(), slug=slug)

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

        if "journeys" in context:
            garages = set(
                journey.trip.garage_id
                for journey in context["journeys"]
                if journey.trip and journey.trip.garage_id
            )
            if len(garages) == 1:
                context["garage"] = Garage.objects.get(id=garages.pop())

            context["tracking"] = any(
                getattr(journey, "locations", False) for journey in context["journeys"]
            )

        context["pending_edits"] = self.object.vehicleedit_set.filter(
            approved=None
        ).exists()

        if self.object.operator:
            context["breadcrumb"] = [
                self.object.operator,
                Vehicles(self.object.operator),
            ]

            context["previous"] = self.object.get_previous()
            context["next"] = self.object.get_next()

        return context


@login_required
def edit_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(
        Vehicle.objects.select_related(
            "vehicle_type", "livery", "operator", "latest_journey"
        ),
        id=vehicle_id,
    )

    ip_address = request.headers.get("CF-Connecting-IP")
    if request.user.ip_address != ip_address:
        request.user.ip_address = ip_address
        request.user.save(update_fields=["ip_address"])

    context = {}
    revision = None
    initial = {
        "operator": vehicle.operator,
        "reg": vehicle.reg,
        "vehicle_type": vehicle.vehicle_type,
        "other_vehicle_type": str(vehicle.vehicle_type or ""),
        "features": vehicle.features.all(),
        "colours": str(vehicle.livery_id or vehicle.colours),
        "branding": vehicle.branding,
        "name": vehicle.name,
        "previous_reg": vehicle.data and vehicle.data.get("Previous reg") or None,
        "notes": vehicle.notes,
        "withdrawn": vehicle.withdrawn,
        "spare_ticket_machine": vehicle.notes == "Spare ticket machine",
    }
    if vehicle.fleet_code:
        initial["fleet_number"] = vehicle.fleet_code
    elif vehicle.fleet_number is not None:
        initial["fleet_number"] = str(vehicle.fleet_number)

    form = forms.EditVehicleForm(
        request.POST or None,
        initial=initial,
        operator=vehicle.operator,
        vehicle=vehicle,
        user=request.user,
    )

    pending_edits = vehicle.vehicleedit_set.filter(approved=None)

    if request.POST:
        if not form.has_really_changed():
            form.add_error(None, "You haven't changed anything")
        elif form.is_valid():
            data = {key: form.cleaned_data[key] for key in form.changed_data}
            for edit in pending_edits:
                if (
                    edit.livery_id
                    and "colours" in data
                    and str(edit.livery_id) == data["colours"]
                ):
                    form.add_error("colours", "There's already a pending edit for that")
                if (
                    edit.vehicle_type
                    and "vehicle_type" in data
                    and edit.vehicle_type == str(data["vehicle_type"])
                ):
                    form.add_error(
                        "vehicle_type", "There's already a pending edit for that"
                    )

        if request.user.trusted is False:
            context["edit"] = True
            form = None
        elif form.is_valid():
            now = timezone.now()
            try:
                revision, features = do_revision(vehicle, data, request.user)
            except IntegrityError:
                if "operator" in form.changed_data:
                    form.add_error(
                        "operator",
                        f"{form.cleaned_data['operator']} already has a vehicle with the code {vehicle.code}",
                    )
                else:
                    raise
            else:
                if revision:
                    revision.datetime = now
                    revision.save()
                    if features:
                        VehicleRevisionFeature.objects.bulk_create(features)
                    context["revision"] = revision
                    varnish_ban("/vehicles/history")

                if data:
                    edit, features, changed = get_vehicle_edit(
                        vehicle, data, now, request
                    )
                    if changed or features:
                        edit.save()
                        context["edit"] = edit
                        VehicleEditFeature.objects.bulk_create(features)

                if revision or edit.id:
                    form = None
                else:
                    form.add_error(None, "You haven't changed anything")

    if form:
        context["pending_edits"] = pending_edits

    if vehicle.operator:
        context["breadcrumb"] = [vehicle.operator, Vehicles(vehicle.operator), vehicle]
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
            "previous": vehicle.get_previous(),
            "next": vehicle.get_next(),
        },
    )


@login_required
def vehicle_edits(request):
    ip_address = request.headers.get("CF-Connecting-IP")
    if request.user.ip_address != ip_address:
        request.user.ip_address = ip_address
        request.user.save(update_fields=["ip_address"])

    if request.method == "POST":
        assert request.user.is_staff
        edits = VehicleEdit.objects.filter(id__in=request.POST.getlist("edit"))
        action = request.POST["action"]
        for edit in edits:
            if action == "apply":
                edit.apply(user=request.user)
            else:
                if action == "approve":
                    edit.approved = True
                else:
                    assert action == "disapprove"
                    edit.approved = False
                edit.arbiter = request.user
        if action != "apply":
            VehicleEdit.objects.bulk_update(edits, fields=["approved", "arbiter"])

    edits = VehicleEdit.objects.order_by("-id")

    edits = edits.select_related(
        "livery",
        "vehicle__livery",
        "user",
        "vehicle__operator",
        "vehicle__latest_journey",
    )
    edits = edits.prefetch_related(
        "vehicleeditfeature_set__feature", "vehicle__features"
    )

    order = request.GET.get("order")

    if order in ("score", "-score"):
        edits = edits.order_by(order)
    if order in ("edit_count", "-edit_count"):
        edit_count = SubqueryCount("vehicle__vehicleedit", filter=Q(approved=None))
        edits = edits.annotate(edit_count=edit_count)
        edits = edits.order_by(order, "vehicle")

    query_dict = QueryDict("pending=true", mutable=True)
    query_dict.update(request.GET)
    f = filters.VehicleEditFilter(query_dict, queryset=edits)

    if f.is_valid():
        paginator = Paginator(f.qs, 100)
        page = paginator.get_page(request.GET.get("page"))
    else:
        page = None

    parameters = {key: value for key, value in request.GET.items() if key != "page"}

    toggle_order = {
        "score": urlencode(
            {**parameters, "order": "score" if order == "-score" else "-score"}
        ),
        "vehicle": urlencode(
            {
                **parameters,
                "order": "edit_count" if order == "-edit_count" else "-edit_count",
            }
        ),
    }

    parameters = urlencode(parameters)

    return render(
        request,
        "vehicle_edits.html",
        {
            "filter": f,
            "parameters": parameters,
            "toggle_order": toggle_order,
            "edits": page,
            "liveries_css_version": liveries_css_version(),
        },
    )


@require_POST
@login_required
def vehicle_edit_vote(request, edit_id, direction):
    edit = get_object_or_404(VehicleEdit, id=edit_id)

    assert request.user.id != edit.user_id

    votes = edit.vehicleeditvote_set
    positive = direction == "up"

    VehicleEditVote.objects.update_or_create(
        {"positive": positive}, for_edit=edit, by_user=request.user
    )

    # a bit dodgy - a vote could change direction between the two count queries!
    edit.score = (
        votes.filter(positive=True).count() - votes.filter(positive=False).count()
    )
    edit.save(update_fields=["score"])

    return HttpResponse(edit.score)


@require_POST
@login_required
def vehicle_revision_revert(request, revision_id):
    assert request.user.is_superuser

    revision = get_object_or_404(VehicleRevision, id=revision_id)

    messages = list(revision.revert())

    return HttpResponse("\n".join(messages))


@require_POST
@login_required
def vehicle_edit_action(request, edit_id, action):
    edit = get_object_or_404(VehicleEdit, id=edit_id)

    if not request.user.has_perm("vehicles.change_vehicle"):
        assert (
            (action == "disapprove" and request.user.id == edit.user_id)
            or request.user.trusted
            and edit.is_simple()
        )

    if action == "apply":
        edit.apply(user=request.user)
    else:
        if action == "disapprove":
            edit.approved = False
        else:
            assert action == "approve"
            edit.approved = True
        edit.arbiter = request.user

        edit.save(update_fields=["approved", "arbiter"])

    return HttpResponse()


@require_GET
def vehicle_history(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    revisions = vehicle.vehiclerevision_set.select_related(
        "vehicle", "from_livery", "to_livery", "from_type", "to_type", "user"
    ).order_by("-id")
    return render(
        request,
        "vehicle_history.html",
        {
            "breadcrumb": [
                vehicle.operator,
                vehicle.operator and Vehicles(vehicle.operator),
                vehicle,
            ],
            "vehicle": vehicle,
            "revisions": revisions,
        },
    )


@require_GET
def vehicles_history(request):
    revisions = VehicleRevision.objects.all().select_related(
        "vehicle", "from_livery", "to_livery", "from_type", "to_type", "user"
    )
    revisions = revisions.order_by("-id")

    f = filters.VehicleRevisionFilter(request.GET, queryset=revisions)

    if f.is_valid():
        paginator = Paginator(f.qs, 100)
        page = paginator.get_page(request.GET.get("page"))
    else:
        page = None

    return render(
        request,
        "vehicle_history.html",
        {
            "filter": f,
            "revisions": page,
            "parameters": urlencode(f.data),
        },
    )


@require_GET
def journey_json(request, pk):
    journey = get_object_or_404(VehicleJourney.objects.select_related("trip"), pk=pk)

    data = {}

    if journey.trip:
        data["stops"] = [
            {
                "name": stop_time.stop.get_name_for_timetable()
                if stop_time.stop
                else stop_time.stop_code,
                "aimed_arrival_time": stop_time.arrival_time(),
                "aimed_departure_time": stop_time.departure_time(),
                "minor": stop_time.is_minor(),
                "coordinates": stop_time.stop
                and stop_time.stop.latlong
                and stop_time.stop.latlong.coords,
            }
            for stop_time in journey.trip.stoptime_set.select_related("stop__locality")
        ]

    locations = redis_client.lrange(f"journey{pk}", 0, -1)

    if locations:
        locations = (json.loads(location) for location in locations)
        data["locations"] = [
            {
                "coordinates": location[1],
                "delta": location[3],
                "direction": location[2],
                "datetime": parse_datetime(location[0]),
            }
            for location in locations
            if location[1][0] and location[1][1]
        ]
        data["locations"].sort(key=lambda location: location["datetime"])

    if journey.trip and locations:
        # only stops with coordinates
        stops = [stop for stop in data["stops"] if stop["coordinates"]]
        if stops:
            haversine_vector_results = haversine_vector(
                [stop["coordinates"] for stop in stops],
                [location["coordinates"] for location in data["locations"]],
                Unit.METERS,
                comb=True,
            )
            for i, distances in enumerate(haversine_vector_results):
                minimum, index_of_minimum = min(
                    ((value, index) for index, value in enumerate(distances))
                )
                if minimum < 100:
                    stops[index_of_minimum]["actual_departure_time"] = data[
                        "locations"
                    ][i]["datetime"]

    return JsonResponse(data)


@require_GET
def latest_journey_debug(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
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

            result = {
                "vehicle": vehicle,
                "journey": journey,
                "queries": connection.queries,
            }

    return render(request, "vehicles/debug.html", {"form": form, "result": result})
