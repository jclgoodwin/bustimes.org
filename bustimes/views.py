import os
import zipfile
import requests
import json
from datetime import timedelta
from ciso8601 import parse_datetime
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.shortcuts import get_object_or_404, render
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from busstops.models import Service, DataSource, StopPoint
from departures.live import TimetableDepartures
from vehicles.models import Vehicle
from .models import Route, Trip


class ServiceDebugView(DetailView):
    model = Service
    trips = Trip.objects.select_related('garage')
    trips = trips.prefetch_related('calendar__calendardate_set').order_by('calendar', 'inbound', 'start')
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

        context['breadcrumb'] = [self.object]

        return context


def route_xml(request, source, code=''):
    source = get_object_or_404(DataSource, id=source)

    if 'tnds' in source.url:
        path = os.path.join(settings.TNDS_DIR, f'{source}.zip')
        with zipfile.ZipFile(path) as archive:
            if code:
                return FileResponse(archive.open(code), content_type='text/xml')
            return HttpResponse('\n'.join(archive.namelist()), content_type='text/plain')

    route = Route.objects.filter(source=source, code__startswith=code).first()
    if not route:
        raise Http404

    if '/' in code:
        path = code.split('/')[0]
        code = code[len(path) + 1:]
        path = os.path.join(settings.DATA_DIR, path)
        if code:
            with zipfile.ZipFile(path) as archive:
                return FileResponse(archive.open(code), content_type='text/xml')
    else:
        path = os.path.join(settings.DATA_DIR, code)

    try:
        with zipfile.ZipFile(path) as archive:
            return HttpResponse('\n'.join(archive.namelist()), content_type='text/plain')
    except zipfile.BadZipFile:
        pass

    # FileResponse automatically closes the file
    return FileResponse(open(path, 'rb'), content_type='text/xml')


def stop_time_json(stop_time, midnight):
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
    if arrival:
        arrival = midnight + stop_time.arrival
    if departure:
        departure = midnight + stop_time.departure
    return {
        "service": service,
        "trip_id":  stop_time.trip_id,
        "destination": destination,
        "aimed_arrival_time": arrival,
        "aimed_departure_time": departure
    }


def stop_times_json(request, atco_code):
    stop = get_object_or_404(StopPoint, atco_code=atco_code)
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

    departures = TimetableDepartures(stop, services, when, routes)
    time_since_midnight = timedelta(hours=when.hour, minutes=when.minute, seconds=when.second,
                                    microseconds=when.microsecond)
    midnight = when - time_since_midnight

    stop_times = departures.get_times(when.date(), time_since_midnight)
    stop_times = stop_times.prefetch_related("trip__route__service__operator")[:limit]

    for stop_time in stop_times:
        times.append(stop_time_json(stop_time, midnight))

    return JsonResponse({
        "times": times
    })


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
    queryset = model.objects.select_related('route__service')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['stops'] = self.object.stoptime_set.select_related('stop__locality')

        stops_json = json.dumps([{
            'latlong': stop_time.stop.latlong.coords,
            'bearing': stop_time.stop.get_heading(),
            'time': stop_time.departure_time() or stop_time.arrival_time()
        } for stop_time in context['stops'] if stop_time.stop and stop_time.stop.latlong])

        context['stops_json'] = mark_safe(stops_json)

        context['liveries_css_version'] = cache.get('liveries_css_version', 0)

        context['breadcrumb'] = [self.object.route.service]

        return context


def tfl_vehicle(request, reg):
    reg = reg.upper()

    data = requests.get(f'https://api.tfl.gov.uk/vehicle/{reg}/arrivals', params=settings.TFL).json()
    if not data:
        raise Http404

    try:
        vehicle = Vehicle.objects.get(reg=reg)
    except Vehicle.DoesNotExist:
        vehicle = Vehicle.objects.create(source_id=7, code=reg, reg=reg, livery_id=262)

    stops = StopPoint.objects.in_bulk(item['naptanId'] for item in data)

    for item in data:
        item['expectedArrival'] = parse_datetime(item['expectedArrival'])
        if item['platformName'] == 'null':
            item['platformName'] = None
        item['stop'] = stops.get(item['naptanId'])

    stops_json = json.dumps([{
        'latlong': item['stop'].latlong.coords,
        'bearing': item['stop'].get_heading(),
        'time': str(timezone.localtime(item['expectedArrival']).time())
    } for item in data if item['stop'] and item['stop'].latlong])

    return render(request, 'tfl_vehicle.html', {
        'data': data,
        'object': vehicle,
        'stops_json': mark_safe(stops_json)
    })
