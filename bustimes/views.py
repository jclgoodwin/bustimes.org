import os
import zipfile
from datetime import timedelta
from ciso8601 import parse_datetime
from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404, HttpResponse, JsonResponse, HttpResponseBadRequest
from busstops.models import Service, DataSource, StopPoint
from departures.live import TimetableDepartures
from .models import Route, Trip


class ServiceDebugView(DetailView):
    model = Service
    trips = Trip.objects.prefetch_related('calendar__calendardate_set').order_by('calendar', 'inbound', 'start')
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
        with zipfile.ZipFile(os.path.join(settings.DATA_DIR, path)) as archive:
            code = code[len(path) + 1:]
            return FileResponse(archive.open(code), content_type='text/xml')

    path = os.path.join(settings.DATA_DIR, code)

    if code.endswith('.zip'):
        try:
            with zipfile.ZipFile(path) as archive:
                return HttpResponse('\n'.join(archive.namelist()), content_type='text/plain')
        except zipfile.BadZipFile:
            pass

    # FileResponse automatically closes the file
    return FileResponse(open(path, 'rb'), content_type='text/xml')


def stop_times_json(request, atco_code):
    stop = get_object_or_404(StopPoint, atco_code=atco_code)
    times = []
    if 'when' in request.GET:
        try:
            when = parse_datetime(request.GET['when'])
        except ValueError:
            return HttpResponseBadRequest("'when' isn't in the right format")
    else:
        when = timezone.now()
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

    for stop_time in departures.get_times(when).prefetch_related("trip__route__service__operator")[:limit]:
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
        times.append({
            "service": service,
            "trip_id":  stop_time.trip_id,
            "destination": destination,
            "aimed_arrival_time": arrival,
            "aimed_departure_time": departure
        })

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
            "aimed_arrival_time": stop_time.arrival_time() if stop_time.arrival else None,
            "aimed_departure_time": stop_time.departure_time() if stop_time.departure else None,
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

        context['breadcrumb'] = [self.object.route.service]

        return context
