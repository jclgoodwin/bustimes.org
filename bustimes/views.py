import os
import zipfile
from django.conf import settings
from django.db.models import Prefetch
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from busstops.models import Service
from .utils import format_timedelta
from .models import Route, Trip


class ServiceDebugView(DetailView):
    model = Service
    queryset = model.objects.prefetch_related(
        Prefetch(
            'route_set__trip_set',
            queryset=Trip.objects.prefetch_related('calendar__calendardate_set').order_by('calendar', 'inbound')
        )
    )
    template_name = 'service_debug.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['breadcrumb'] = [self.object]

        return context


def route_xml(request, source, code):
    route = Route.objects.filter(source=source, code__startswith=code).select_related('source').first()
    if not route:
        raise Http404

    if 'tnds' in route.source.url:
        path = os.path.join(settings.TNDS_DIR, f'{route.source}.zip')
        with zipfile.ZipFile(path) as archive:
            return FileResponse(archive.open(code), content_type='text/xml')

    if '/' in code:
        path = code.split('/')[0]
        with zipfile.ZipFile(os.path.join(settings.DATA_DIR, path)) as archive:
            code = code[len(path) + 1:]
            return FileResponse(archive.open(code), content_type='text/xml')
    path = os.path.join(settings.DATA_DIR, code)

    if code.endswith('.zip'):
        with zipfile.ZipFile(os.path.join(settings.DATA_DIR, path)) as archive:
            return HttpResponse('\n'.join(archive.namelist()), content_type='text/plain')

    # FileResponse automatically closes the file
    return FileResponse(open(path, 'rb'), content_type='text/xml')


def trip_json(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    print('trip')
    stops = [{
        'name': stop_time.stop.get_qualified_name() if stop_time.stop else stop_time.stop_code,
        'aimed_arrival_time': format_timedelta(stop_time.arrival) if stop_time.arrival else None,
        'aimed_departure_time': format_timedelta(stop_time.departure) if stop_time.departure else None,
    } for stop_time in trip.stoptime_set.select_related('stop__locality')]

    return JsonResponse({
        'stops': stops,
    })
