import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import requests
from ciso8601 import parse_datetime
from django.conf import settings
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import AsSVG
from django.db.models import Exists, OuterRef, Prefetch
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from django.views.generic.detail import DetailView
from rest_framework.renderers import JSONRenderer

from api.serializers import TripSerializer
from busstops.models import DataSource, Operator, Service, StopPoint, StopUsage
from departures import gtfsr, live
from vehicles.models import Vehicle
from vehicles.utils import liveries_css_version

from .download_utils import download
from .models import Block, Route, StopTime, Trip


class ServiceDebugView(DetailView):
    model = Service
    trips = (
        Trip.objects.select_related("garage", "block")
        .prefetch_related(
            "calendar__calendardate_set",
            "calendar__calendarbankholiday_set__bank_holiday",
        )
        .order_by("calendar", "inbound", "start")
    )
    prefetch = Prefetch("route_set__trip_set", queryset=trips)
    queryset = model.objects.prefetch_related(prefetch)
    template_name = "service_debug.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["route_links"] = self.object.routelink_set.annotate(
            svg=AsSVG("geometry", relative=True)
        )

        extent = context["route_links"].aggregate(extent=Extent("geometry"))["extent"]
        if not extent and self.object.geometry:
            extent = self.object.geometry.extent

        if extent:
            x = extent[0]
            y = -extent[3]
            width = extent[2] - extent[0]
            height = extent[3] - extent[1]

            context["view_box"] = f"{x} {y} {width} {height}"

            context["width"] = width * 5000
            context["height"] = height * 5000

        for route in self.object.route_set.all():
            previous_trip = None

            for trip in route.trip_set.all():
                if (
                    previous_trip is None
                    or trip.calendar_id != previous_trip.calendar_id
                ):
                    trip.rowspan = 1
                    previous_trip = trip
                else:
                    previous_trip.rowspan += 1

        context["stopusages"] = self.object.stopusage_set.select_related(
            "stop__locality"
        )

        context["breadcrumb"] = [self.object]

        return context


def maybe_download_file(local_path, s3_key):
    if not local_path.exists():
        if not local_path.parent.exists():
            local_path.parent.mkdir(parents=True)
        client = boto3.client("s3", endpoint_url="https://ams3.digitaloceanspaces.com")
        client.download_file(
            Bucket="bustimes-data", Key=s3_key, Filename=str(local_path)
        )


@require_GET
def route_xml(request, source, code=""):
    source = get_object_or_404(DataSource, id=source)

    if "ftp.tnds.basemap" in source.url:
        filename = Path(source.url).name
        path = settings.DATA_DIR / "TNDS" / filename
        maybe_download_file(path, f"TNDS/{filename}")
        with zipfile.ZipFile(path) as archive:
            if code:
                try:
                    return FileResponse(archive.open(code), content_type="text/plain")
                except KeyError as e:
                    raise Http404(e)
            return HttpResponse(
                "\n".join(archive.namelist()), content_type="text/plain"
            )

    if "stagecoach" in source.url:
        path = settings.DATA_DIR / source.url.split("/")[-1]
        if not path.exists():
            if not path.parent.exists():
                path.parent.mkdir()
            download(path, source.url)
    elif ".zip" not in code and code != source.name:
        if source.url.startswith("https://opendata.ticketer.com/uk/"):
            path = source.url.split("/")[4]
            path = settings.DATA_DIR / "ticketer" / f"{path}.zip"
        elif "bus-data.dft.gov.uk" in source.url:
            path = settings.DATA_DIR / "bod" / str(source.id)
        else:
            raise Http404
        if not path.exists():
            if not path.parent.exists():
                path.parent.mkdir(parents=True)
            download(path, source.url)
    elif "/" in code:
        path = code.split("/")[0]  # archive name
        code = code[len(path) + 1 :]
        path = settings.DATA_DIR / path
    else:
        path = None

    if path:
        if code:
            with zipfile.ZipFile(path) as archive:
                return FileResponse(archive.open(code), content_type="text/xml")
    else:
        path = settings.DATA_DIR / code

    try:
        with zipfile.ZipFile(path) as archive:
            return HttpResponse(
                "\n".join(archive.namelist()), content_type="text/plain"
            )
    except zipfile.BadZipFile:
        pass

    # FileResponse automatically closes the file
    return FileResponse(open(path, "rb"), content_type="text/xml")


def stop_time_json(stop_time, date):
    destination = stop_time.trip.destination
    route = stop_time.trip.route
    arrival = stop_time.arrival
    departure = stop_time.departure
    if arrival is not None:
        arrival = stop_time.arrival_datetime(date)
    if departure is not None:
        departure = stop_time.departure_datetime(date)
    return {
        "service": {
            "line_name": route.line_name,
            "operators": [
                {
                    "id": operator.noc,
                    "name": operator.name,
                    "parent": operator.parent,
                }
                for operator in route.service.operator.all()
            ],
        },
        "trip_id": stop_time.trip_id,
        "destination": {
            "atco_code": destination.atco_code,
            "name": destination.get_qualified_name(),
            "locality": destination.locality and str(destination.locality),
        },
        "aimed_arrival_time": arrival,
        "aimed_departure_time": departure,
    }


@require_GET
def stop_times_json(request, atco_code):
    stop = get_object_or_404(StopPoint, atco_code__iexact=atco_code)
    times = []

    if "when" in request.GET:
        try:
            when = parse_datetime(request.GET["when"])
        except ValueError:
            return HttpResponseBadRequest(
                f"'{request.GET['when']}' isn't in the right format"
            )
        current_timezone = timezone.get_current_timezone()
        when = when.astimezone(current_timezone)
    else:
        when = timezone.localtime()
    services = stop.service_set.filter(current=True).defer("geometry", "search_vector")

    try:
        limit = int(request.GET["limit"])
    except KeyError:
        limit = 10
    except ValueError:
        return HttpResponseBadRequest(
            "'limit' isn't in the right format (an integer or nothing)"
        )

    routes = {}
    for route in Route.objects.filter(service__in=services).select_related("source"):
        if route.service_id in routes:
            routes[route.service_id].append(route)
        else:
            routes[route.service_id] = [route]

    departures = live.TimetableDepartures(stop, services, None, routes)
    time_since_midnight = timedelta(
        hours=when.hour,
        minutes=when.minute,
        seconds=when.second,
        microseconds=when.microsecond,
    )

    # any journeys that started yesterday
    yesterday_date = (when - timedelta(1)).date()
    yesterday_time = time_since_midnight + timedelta(1)
    stop_times = departures.get_times(yesterday_date, yesterday_time)

    for stop_time in stop_times.prefetch_related("trip__route__service__operator")[
        :limit
    ]:
        times.append(stop_time_json(stop_time, yesterday_date))

    # journeys that started today
    stop_times = departures.get_times(when.date(), time_since_midnight)
    for stop_time in stop_times.prefetch_related("trip__route__service__operator")[
        :limit
    ]:
        times.append(stop_time_json(stop_time, when.date()))

    return JsonResponse({"times": times})


@require_GET
def trip_json(request, id):
    trip = get_object_or_404(Trip, id=id)
    times = []
    for stop_time in trip.stoptime_set.select_related("stop__locality"):
        stop = {}
        if stop_time.stop:
            stop["atco_code"] = stop_time.stop_id
            stop["name"] = stop_time.stop.get_qualified_name()
        else:
            stop["name"] = stop_time.stop_code

        times.append(
            {
                "stop": stop,
                "aimed_arrival_time": stop_time.arrival_time(),
                "aimed_departure_time": stop_time.departure_time(),
            }
        )

    return JsonResponse({"times": times})


class TripDetailView(DetailView):
    model = Trip
    queryset = model.objects.select_related(
        "route__service", "operator", "calendar"
    ).defer("route__service__search_vector")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.object.operator:
            operators = [self.object.operator]
        elif self.object.route.service:
            operators = list(self.object.route.service.operator.all())
        else:
            operators = []

        if self.object.route.service:
            self.object.route.service.line_name = self.object.route.line_name

        context["breadcrumb"] = operators + [self.object.route.service]

        if self.object.ticket_machine_code and self.object.block_id:
            trips = Trip.objects.filter(
                calendar=self.object.calendar_id,
                inbound=self.object.inbound,
                ticket_machine_code=self.object.ticket_machine_code,
                block_id=self.object.block_id,
                route__service=self.object.route.service_id,
            )
        else:
            trips = [self.object]

        stops = (
            StopTime.objects.filter(trip__in=trips)
            .select_related("stop__locality")
            .defer(
                "stop__search_vector",
                "stop__locality__search_vector",
                "stop__locality__latlong",
            )
            .order_by("trip__start", "id")
        )
        stops = list(stops)

        if stops:
            if stops[0].stop:
                context["origin"] = stops[0].stop.locality
            if stops[-1].stop:
                context["destination"] = stops[-1].stop.locality

            if operators and operators[0].name in settings.NTA_OPERATORS:
                trip_update = gtfsr.get_trip_update(self.object)
                if trip_update:
                    context["trip_update"] = trip_update
                    gtfsr.apply_trip_update(stops, trip_update)

        context["stops"] = stops
        self.object.stops = stops
        trip_serializer = TripSerializer(self.object)
        stops_json = JSONRenderer().render(trip_serializer.data)

        context["stops_json"] = mark_safe(stops_json.decode())

        context["liveries_css_version"] = liveries_css_version()

        return context


class BlockDetailView(DetailView):
    model = Block
    queryset = model.objects.prefetch_related(
        "trip_set__destination__locality", "trip_set__route"
    )


@require_GET
@cache_page(60)
def tfl_vehicle(request, reg):
    reg = reg.upper()

    response = requests.get(
        f"https://api.tfl.gov.uk/vehicle/{reg}/arrivals", params=settings.TFL, timeout=4
    )
    if response.ok:
        data = response.json()
    else:
        data = None

    vehicles = Vehicle.objects.select_related("livery", "operator", "vehicle_type")
    vehicle = vehicles.filter(code=reg).first()

    if not data:
        if not vehicle:
            raise Http404
        return render(
            request,
            "vehicles/vehicle_detail.html",
            {"vehicle": vehicle, "object": vehicle},
        )

    atco_codes = [item["naptanId"] for item in data]
    try:
        service = Service.objects.get(
            Exists(
                StopUsage.objects.filter(stop_id__in=atco_codes, service=OuterRef("id"))
            ),
            line_name__iexact=data[0]["lineName"],
            current=True,
        )
    except (Service.DoesNotExist, Service.MultipleObjectsReturned):
        service = None

    if service and vehicle:
        operator = service.operator.first()
        if vehicle.operator != operator:
            vehicle.operator = operator
            vehicle.save(update_fields=["operator"])

    stops = StopPoint.objects.in_bulk(atco_codes)

    for item in data:
        item["expectedArrival"] = parse_datetime(item["expectedArrival"])
        if item["platformName"] == "null":
            item["platformName"] = None
        item["stop"] = stops.get(item["naptanId"])

    stops_json = json.dumps(
        {
            "times": [
                {
                    "stop": {
                        "location": item["stop"].latlong.coords,
                        "bearing": item["stop"].get_heading(),
                    },
                    "aimed_arrival_time": str(
                        timezone.localtime(item["expectedArrival"]).time()
                    ),
                }
                for item in data
                if item["stop"] and item["stop"].latlong
            ]
        }
    )

    return render(
        request,
        "tfl_vehicle.html",
        {
            "breadcrumb": [service],
            "data": data,
            "object": vehicle,
            "stops_json": mark_safe(stops_json),
        },
    )


@require_GET
def trip_updates(request):
    feed = gtfsr.get_feed_entities()

    journey_codes = feed["entity"].keys()
    trips = Trip.objects.filter(ticket_machine_code__in=journey_codes)
    operators = Operator.objects.filter(
        service__route__in=set(trip.route_id for trip in trips)
    ).distinct()
    trips = {trip.ticket_machine_code: trip for trip in trips}

    trip_updates = [
        (entity, trips.get(trip_id)) for trip_id, entity in feed["entity"].items()
    ]

    return render(
        request,
        "trip_updates.html",
        {
            "trips": len(trips),
            "operators": operators,
            "timestamp": datetime.fromtimestamp(int(feed["header"]["timestamp"])),
            "trip_updates": trip_updates,
        },
    )
