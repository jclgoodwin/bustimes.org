import os
import zipfile
from django.conf import settings
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404, HttpResponse
from busstops.models import Service, DataSource
from .models import Route, Trip


class ServiceDebugView(DetailView):
    model = Service
    queryset = model.objects.prefetch_related(
        Prefetch(
            'route_set__trip_set',
            queryset=Trip.objects.prefetch_related('calendar__calendardate_set').order_by('calendar', 'inbound', 'start')
        )
    )
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
