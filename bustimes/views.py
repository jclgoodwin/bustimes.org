import csv
import json
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

import requests
from ciso8601 import parse_datetime
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Exists, OuterRef, Prefetch, prefetch_related_objects
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer, XmlLexer
from rest_framework.renderers import JSONRenderer

from api.serializers import TripSerializer
from buses.utils import cache_page
from busstops.models import (
    DataSource,
    Operator,
    Service,
    StopArea,
    StopPoint,
    StopUsage,
)
from departures import avl, gtfsr, live
from vehicles.models import Vehicle
from vehicles.rtpi import add_progress_and_delay

from .download_utils import download
from .models import Garage, Route, StopTime, Trip


class ServiceDebugView(DetailView):
    model = Service
    template_name = "service_debug.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trips = (
            Trip.objects.select_related("garage")
            .prefetch_related(
                "calendar__calendardate_set",
                "calendar__calendarbankholiday_set__bank_holiday",
            )
            .order_by("calendar", "inbound", "start")
        )

        routes = (
            self.object.route_set.select_related("source")
            .prefetch_related(Prefetch("trip_set", queryset=trips))
            .order_by("service_code", "revision_number", "start_date", "line_name")
        )

        for route in routes:
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

        context["routes"] = routes

        context["stopusages"] = self.object.stopusage_set.select_related(
            "stop__locality"
        )

        context["breadcrumb"] = [self.object]

        return context


def maybe_download_file(local_path, s3_key):
    if not local_path.exists():
        import boto3

        if not local_path.parent.exists():
            local_path.parent.mkdir(parents=True)
        client = boto3.client("s3", endpoint_url="https://ams3.digitaloceanspaces.com")
        client.download_file(
            Bucket="bustimes-data", Key=s3_key, Filename=str(local_path)
        )


class SourceListView(ListView):
    model = DataSource
    queryset = (
        DataSource.objects.annotate(
            routes=Count("route"),
        )
        .filter(routes__gt=0)
        .order_by("url")
    )


class SourceDetailView(DetailView):
    model = DataSource

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["routes"] = (
            self.object.route_set.order_by(
                "service_code", "line_name", "start_date", "revision_number"
            )
            .annotate(
                trips=Count("trip"),
            )
            .select_related("service")
        )

        context["breadcrumb"] = [
            {"get_line_name_and_brand": "Sources", "get_absolute_url": "/sources"}
        ]

        return context


@require_GET
@login_required
def route_xml(request, source, code=""):
    source = get_object_or_404(DataSource, id=source)

    if "ftp.tnds.basemap" in source.url:
        filename = Path(source.url).name
        path = settings.DATA_DIR / "TNDS" / filename
        maybe_download_file(path, f"TNDS/{filename}")
        with zipfile.ZipFile(path) as archive:
            if code:
                if code.endswith(".zip"):
                    archive = zipfile.ZipFile(archive.open(code))
                    code = ""

                elif ".zip/" in code:
                    sub_archive, code = code.split("/", 1)
                    archive = zipfile.ZipFile(archive.open(sub_archive))

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
    elif code != source.name:
        url = source.url
        if source.url.startswith("https://opendata.ticketer.com/uk/"):
            path = source.url.split("/")[4]
            path = settings.DATA_DIR / "ticketer" / f"{path}.zip"
        elif "bus-data.dft.gov.uk" in source.url:
            path = settings.DATA_DIR / "bod" / str(source.id)
        elif "data.discoverpassenger" in source.url and "/" in code:
            path, code = code.split("/", 1)
            url = f"https://s3-eu-west-1.amazonaws.com/passenger-sources/{path.split('_')[0]}/txc/{path}"
            path = settings.DATA_DIR / path
        else:
            raise Http404
        if not path.exists():
            if not path.parent.exists():
                path.parent.mkdir(parents=True)
            download(path, url)
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


def stop_time_json(stop_time, date) -> dict:
    trip = stop_time.trip
    destination = trip.destination
    route = trip.route

    arrival = stop_time.arrival
    departure = stop_time.departure
    if arrival is not None:
        arrival = stop_time.arrival_datetime(date)
    if departure is not None:
        departure = stop_time.departure_datetime(date)

    operators = []
    if trip.operator:
        operators.append(
            {
                "id": trip.operator.noc,
                "name": trip.operator.name,
                "parent": trip.operator.parent,
                "vehicle_mode": trip.operator.vehicle_mode,
            }
        )

    return {
        "stop_time": stop_time,
        "id": stop_time.id,
        "trip_id": stop_time.trip_id,
        "service": {
            "line_name": route.line_name,
            "operators": operators,
        },
        "destination": destination
        and {
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
                "'when' isn't in the right format (should be an ISO 8601 datetime)"
            )
        current_timezone = timezone.get_current_timezone()
        when = when.astimezone(current_timezone)
        now = False
    else:
        when = timezone.localtime()
        now = True
    services = stop.service_set.filter(current=True, timetable_wrong=False).defer(
        "geometry", "search_vector"
    )

    by_trip = None
    if now:
        vehicle_locations = avl.get_tracking(stop, services)
        if vehicle_locations:
            by_trip = {
                item["trip_id"]: item for item in vehicle_locations if "trip_id" in item
            }

    try:
        limit = int(request.GET["limit"])
    except KeyError:
        limit = 10
    except ValueError:
        return HttpResponseBadRequest(
            "'limit' isn't in the right format (an integer or nothing)"
        )

    routes = Route.objects.filter(service__in=services).select_related("source")

    departures = live.TimetableDepartures(stop, services, None, routes, by_trip)
    time_since_midnight = timedelta(
        hours=when.hour,
        minutes=when.minute,
        seconds=when.second,
    )

    # any journeys that started yesterday
    yesterday_date = (when - timedelta(1)).date()
    yesterday_time = time_since_midnight + timedelta(1)
    stop_times = departures.get_times(yesterday_date, yesterday_time)

    for stop_time in stop_times.select_related(
        "trip__destination__locality", "trip__route__service", "trip__operator"
    )[:limit]:
        times.append(stop_time_json(stop_time, yesterday_date))

    # journeys that started today
    # possibly late-running
    if by_trip:
        stop_times = departures.get_times(when.date(), time_since_midnight, by_trip)
        for stop_time in stop_times.select_related(
            "trip__destination__locality", "trip__route__service", "trip__operator"
        )[:limit]:
            times.append(stop_time_json(stop_time, when.date()))

    stop_times = departures.get_times(when.date(), time_since_midnight)
    for stop_time in stop_times.select_related(
        "trip__destination__locality", "trip__route__service", "trip__operator"
    )[:limit]:
        times.append(stop_time_json(stop_time, when.date()))

    if by_trip:
        prefetch_related_objects(
            [time["stop_time"].trip for time in times if time["trip_id"] in by_trip],
            Prefetch(
                "stoptime_set",
                StopTime.objects.select_related("stop").filter(
                    stop__latlong__isnull=False
                ),
            ),
        )

        for time in times:
            if time["trip_id"] in by_trip:
                item = by_trip[time["trip_id"]]

                if "progress" not in item:
                    add_progress_and_delay(item, time["stop_time"])
                if "progress" not in item:
                    continue

                if (
                    (time["aimed_arrival_time"] or time["aimed_departure_time"]) >= when
                    or item["progress"]["id"] < time["id"]
                    or item["progress"]["id"] == time["id"]
                    and item["progress"]["progress"] == 0
                ):
                    delay = timedelta(seconds=item["delay"])
                    time["delay"] = delay
                    if delay < timedelta() and item["progress"]["sequence"] == 0:
                        delay = timedelta()
                    if time["aimed_departure_time"]:
                        time["expected_departure_time"] = (
                            time["aimed_departure_time"] + delay
                        )
                    if time["aimed_arrival_time"]:
                        time["expected_arrival_time"] = (
                            time["aimed_arrival_time"] + delay
                        )
                    else:
                        time["expected_arrival_time"] = time["expected_departure_time"]

    times = [
        time
        for time in times
        if "delay" in time
        or (time["aimed_arrival_time"] or time["aimed_departure_time"]) >= when
    ]
    for time in times:
        del time["stop_time"]

    return JsonResponse({"times": times})


@require_GET
@login_required
def stop_debug(request, atco_code: str):
    stop = get_object_or_404(
        StopPoint.objects.select_related("locality"), atco_code=atco_code
    )

    responses = []

    formatter = HtmlFormatter()
    css = formatter.get_style_defs()

    for key, response in cache.get_many(
        [
            f"TflDepartures:{stop.pk}",
            f"SiriSmDepartures:{stop.pk}",
            f"AcisHorizonDepartures:{stop.pk}",
            f"EdinburghDepartures:{stop.pk}",
            f"tfwm:{stop.pk}",
        ]
    ).items():
        response_text = response.text
        # syntax-highlight and pretty-print XML and JSON responses
        try:
            # XML
            ET.register_namespace("", "http://www.siri.org.uk/siri")
            xml = ET.XML(response.text)
            ET.indent(xml)
            response_text = ET.tostring(xml).decode()
            response_text = mark_safe(highlight(response_text, XmlLexer(), formatter))
        except ET.ParseError:
            # JSON
            response_text = json.dumps(response.json(), indent=2)
            response_text = mark_safe(highlight(response_text, JsonLexer(), formatter))
        responses.append(
            {"url": response.url, "text": response_text, "headers": response.headers}
        )

    return render(
        request,
        "stoppoint_debug.html",
        {
            "object": stop,
            "breadcrumb": [stop.locality, stop],
            "responses": responses,
            "css": css,
        },
    )


class TripDetailView(DetailView):
    model = Trip
    queryset = model.objects.select_related(
        "route__service", "operator", "route__source"
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

        trips = self.object.get_trips()

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

            if self.object.route.source.name == "Realtime Transport Operators":
                trip_update = gtfsr.get_trip_update(self.object)
                if trip_update:
                    context["trip_update"] = trip_update
                    gtfsr.apply_trip_update(stops, trip_update)

        context["stops"] = stops
        self.object.stops = stops
        trip_serializer = TripSerializer(self.object)
        stops_json = JSONRenderer().render(trip_serializer.data)

        context["stops_json"] = mark_safe(stops_json.decode())

        return context


@require_GET
def trip_block(request, pk: int):
    trip = get_object_or_404(Trip, pk=pk)

    if not trip.block:
        raise Http404

    trips = (
        Trip.objects.filter(
            block=trip.block,
            route__source=trip.route.source,
        )
        .order_by("start", "calendar")
        .select_related("route", "destination__locality")
    )

    return render(
        request,
        "bustimes/block_detail.html",
        {"object": trip.block, "trips": trips},
    )


@require_GET
@cache_page(60)
def tfl_vehicle(request, reg: str):
    reg = reg.upper()

    vehicles = Vehicle.objects.select_related("latest_journey")
    vehicle = vehicles.filter(vehiclecode__code=f"TFLO:{reg}").first()

    response = requests.get(
        f"https://api.tfl.gov.uk/Vehicle/{reg}/Arrivals", params=settings.TFL, timeout=8
    )
    if response.ok:
        data = response.json()
    else:
        data = None

    if not data:
        if vehicle:
            if vehicle.latest_journey and vehicle.latest_journey.trip_id:
                return redirect(vehicle.latest_journey.trip)
            return redirect(vehicle)
        raise Http404

    atco_codes = []
    for item in data:
        atco_code = item["naptanId"]
        # try "03700168" as well as "3700168"
        if atco_code[:3] == "370" and atco_code.isdigit():
            atco_codes.append(f"0{atco_code}")
        atco_codes.append(atco_code)

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

    stops = StopPoint.objects.in_bulk(atco_codes)
    if not stops:
        stops = StopArea.objects.in_bulk(atco_codes)

    times = []
    for i, item in enumerate(data):
        expected_arrival = timezone.localtime(parse_datetime(item["expectedArrival"]))
        expected_arrival = round(expected_arrival.timestamp() / 60) * 60
        expected_arrival = datetime.fromtimestamp(expected_arrival)
        time = {
            "id": i,
            "stop": {
                "name": item["stationName"],
            },
            "expected_arrival_time": str(expected_arrival.time())[:5],
        }
        atco_code = item["naptanId"]
        stop = stops.get(atco_code) or stops.get(f"0{atco_code}")

        if stop:
            if type(stop) is StopPoint:
                time["stop"]["atco_code"] = stop.atco_code
                time["stop"]["bearing"] = stop.get_heading()

            if stop.latlong:
                time["stop"]["location"] = stop.latlong.coords

        if item["platformName"] and item["platformName"] != "null":
            time["stop"]["icon"] = item["platformName"]

        times.append(time)

    stops_json = json.dumps({"times": times})

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


@require_GET
def garages(request):
    response = HttpResponse(content_type="text/plain")

    writer = csv.writer(response)
    writer.writerow(["id", "name"])
    for garage in Garage.objects.all():
        writer.writerow([garage.id, garage])

    return response


@require_GET
def garage_trips(request, pk):
    garage = get_object_or_404(Garage, pk=pk)

    response = HttpResponse(content_type="text/plain")

    writer = csv.writer(response)
    writer.writerow(["id", "calendar", "from_date", "to_date", "block"])
    for trip in garage.trip_set.select_related("calendar"):
        writer.writerow(
            [
                trip.id,
                trip.calendar,
                trip.calendar.start_date,
                trip.calendar.end_date,
                trip.block,
            ]
        )

    return response
