import zipfile
import requests
import json
from pathlib import Path
from datetime import timedelta
from ciso8601 import parse_datetime

from django.conf import settings
from django.db.models import Prefetch, Exists, OuterRef
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from rest_framework.renderers import JSONRenderer

from api.serializers import TripSerializer
from busstops.models import Service, DataSource, StopPoint, StopUsage
from departures import live, gtfsr
from vehicles.models import Vehicle
from vehicles.utils import liveries_css_version
from .models import Route, Trip, Block


class ServiceDebugView(DetailView):
    model = Service
    trips = Trip.objects.select_related(
        'garage',
        'block'
    ).prefetch_related(
        'calendar__calendardate_set',
        'calendar__calendarbankholiday_set__bank_holiday'
    ).order_by(
        'calendar',
        'inbound',
        'start'
    )
    prefetch = Prefetch('route_set__trip_set', queryset=trips)
    queryset = model.objects.prefetch_related(prefetch)
    template_name = 'service_debug.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        for route in self.object.route_set.all():
            previous_trip = None

            for trip in route.trip_set.all():
                if previous_trip is None or trip.calendar_id != previous_trip.calendar_id:
                    trip.rowspan = 1
                    previous_trip = trip
                else:
                    previous_trip.rowspan += 1

        context['stopusages'] = self.object.stopusage_set.select_related('stop__locality')

        context['breadcrumb'] = [self.object]

        return context


@require_GET
def route_xml(request, source, code=''):
    source = get_object_or_404(DataSource, id=source)

    if 'tnds' in source.url:
        path = settings.TNDS_DIR / f'{source}.zip'
        with zipfile.ZipFile(path) as archive:
            if code:
                return FileResponse(archive.open(code), content_type='text/plain')
            return HttpResponse('\n'.join(archive.namelist()), content_type='text/plain')

    if code:
        route = Route.objects.filter(source=source, code__startswith=code).first()
        if not route:
            raise Http404

    if 'stagecoach' in source.url:
        path = str(Path(source.url.split('/')[-1]))
    elif '.zip' not in code and code != source.name:
        if source.url.startswith('https://opendata.ticketer.com/uk/'):
            path = source.url.split('/')[4]
            path = Path('ticketer') / f'{path}.zip'
        else:
            path = Path('bod') / str(source.id)
    elif '/' in code:
        path = code.split('/')[0]  # archive name
        code = code[len(path) + 1:]
    else:
        path = None

    if path:
        path = settings.DATA_DIR / path
        if code:
            with zipfile.ZipFile(path) as archive:
                return FileResponse(archive.open(code), content_type='text/xml')
    else:
        path = settings.DATA_DIR / code

    try:
        with zipfile.ZipFile(path) as archive:
            return HttpResponse('\n'.join(archive.namelist()), content_type='text/plain')
    except zipfile.BadZipFile:
        pass

    # FileResponse automatically closes the file
    return FileResponse(open(path, 'rb'), content_type='text/xml')


def stop_time_json(stop_time, date):
    service = {
        "line_name": stop_time.trip.route.service.line_name,
        "operators": [{
            "id": operator.id,
            "name": operator.name,
            "parent": operator.parent,
        } for operator in stop_time.trip.route.service.operator.all()]
    }
    destination = {
        "atco_code": stop_time.trip.destination_id,
        "name": stop_time.trip.destination.get_qualified_name()
    }
    arrival = stop_time.arrival
    departure = stop_time.departure
    if arrival is not None:
        arrival = stop_time.arrival_datetime(date)
    if departure is not None:
        departure = stop_time.departure_datetime(date)
    return {
        "service": service,
        "trip_id":  stop_time.trip_id,
        "destination": destination,
        "aimed_arrival_time": arrival,
        "aimed_departure_time": departure
    }


@require_GET
def stop_times_json(request, atco_code):
    stop = get_object_or_404(StopPoint, atco_code__iexact=atco_code)
    times = []

    if 'when' in request.GET:
        try:
            when = parse_datetime(request.GET['when'])
        except ValueError:
            return HttpResponseBadRequest(f"'{request.GET['when']}' isn't in the right format")
        current_timezone = timezone.get_current_timezone()
        when = when.astimezone(current_timezone)
    else:
        when = timezone.localtime()
    services = stop.service_set.filter(current=True).defer('geometry', 'search_vector')

    try:
        limit = int(request.GET['limit'])
    except KeyError:
        limit = 10
    except ValueError:
        return HttpResponseBadRequest("'limit' isn't in the right format (an integer or nothing)")

    routes = {}
    for route in Route.objects.filter(service__in=services).select_related('source'):
        if route.service_id in routes:
            routes[route.service_id].append(route)
        else:
            routes[route.service_id] = [route]

    departures = live.TimetableDepartures(stop, services, None, routes)
    time_since_midnight = timedelta(hours=when.hour, minutes=when.minute, seconds=when.second,
                                    microseconds=when.microsecond)

    # any journeys that started yesterday
    yesterday_date = (when - timedelta(1)).date()
    yesterday_time = time_since_midnight + timedelta(1)
    stop_times = departures.get_times(yesterday_date, yesterday_time)

    for stop_time in stop_times.prefetch_related("trip__route__service__operator")[:limit]:
        times.append(stop_time_json(stop_time, yesterday_date))

    # journeys that started today
    stop_times = departures.get_times(when.date(), time_since_midnight)
    for stop_time in stop_times.prefetch_related("trip__route__service__operator")[:limit]:
        times.append(stop_time_json(stop_time, when.date()))

    return JsonResponse({
        "times": times
    })


@require_GET
def trip_json(request, id):
    trip = get_object_or_404(Trip, id=id)
    times = []
    for stop_time in trip.stoptime_set.select_related('stop__locality'):
        stop = {}
        if stop_time.stop:
            stop['atco_code'] = stop_time.stop_id
            stop['name'] = stop_time.stop.get_qualified_name()
        else:
            stop['name'] = stop_time.stop_code

        times.append({
            "stop": stop,
            "aimed_arrival_time": stop_time.arrival_time(),
            "aimed_departure_time": stop_time.departure_time(),
        })

    return JsonResponse({
        "times": times
    })


class TripDetailView(DetailView):
    model = Trip
    queryset = model.objects.select_related('route__service').prefetch_related('stoptime_set__stop__locality')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['stops'] = self.object.stoptime_set.all()

        trip_serializer = TripSerializer(self.object)
        stops_json = JSONRenderer().render(trip_serializer.data)

        context['stops_json'] = mark_safe(stops_json.decode())

        context['liveries_css_version'] = liveries_css_version()

        context['breadcrumb'] = list(self.object.route.service.operator.all()) + [self.object.route.service]

        trip_update = gtfsr.get_trip_update(self.object)
        if trip_update:
            context['trip_update'] = trip_update
            gtfsr.apply_trip_update(context['stops'], trip_update)

        return context


class BlockDetailView(DetailView):
    model = Block
    queryset = model.objects.prefetch_related('trip_set__destination__locality', 'trip_set__route')


@require_GET
def tfl_vehicle(request, reg):
    reg = reg.upper()

    response = requests.get(
        f'https://api.tfl.gov.uk/vehicle/{reg}/arrivals',
        params=settings.TFL,
        timeout=4
    )
    if response.ok:
        data = response.json()
    else:
        data = None

    vehicles = Vehicle.objects.select_related('livery', 'operator', 'vehicle_type')

    if not data:
        try:
            vehicle = get_object_or_404(vehicles, code=reg)
        except Vehicle.MultipleObjectsReturned:
            vehicle = get_object_or_404(vehicles, source=7, code=reg)
        return render(request, 'vehicles/vehicle_detail.html', {
            'vehicle': vehicle,
            'object': vehicle
        })

    atco_codes = [item['naptanId'] for item in data]
    try:
        service = Service.objects.get(
            Exists(StopUsage.objects.filter(stop_id__in=atco_codes, service=OuterRef('id'))),
            line_name__iexact=data[0]['lineName'],
            current=True
        )
        operator = service.operator.first()
    except (Service.DoesNotExist, Service.MultipleObjectsReturned):
        service = None
        operator = None

    try:
        vehicle = vehicles.get(reg=reg)
    except Vehicle.DoesNotExist:
        vehicle = vehicles.create(source_id=7, code=reg, reg=reg, livery_id=262, operator=operator)

    if operator and not vehicle.operator:
        vehicle.operator = operator
        vehicle.save(update_fields=['operator'])

    stops = StopPoint.objects.in_bulk(atco_codes)

    for item in data:
        item['expectedArrival'] = parse_datetime(item['expectedArrival'])
        if item['platformName'] == 'null':
            item['platformName'] = None
        item['stop'] = stops.get(item['naptanId'])

    stops_json = json.dumps({
        "times": [{
            "stop": {
                "location": item['stop'].latlong.coords,
                'bearing': item['stop'].get_heading(),
            },
            'aimed_arrival_time': str(timezone.localtime(item['expectedArrival']).time())
        } for item in data if item['stop'] and item['stop'].latlong]})

    return render(request, 'tfl_vehicle.html', {
        'breadcrumb': [service],
        'data': data,
        'object': vehicle,
        'stops_json': mark_safe(stops_json)
    })
