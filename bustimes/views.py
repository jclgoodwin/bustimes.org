import os
import zipfile
from django.conf import settings
from django.db.models import Prefetch
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404
from django.utils import timezone
from busstops.models import Service
from vehicles.views import siri_one_shot, Poorly
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

        now = timezone.localtime()

        context['codes'] = self.object.servicecode_set.all()
        for code in context['codes']:
            if code.scheme.endswith(' SIRI'):
                try:
                    code.siri_one_shot = siri_one_shot(code, now)
                except Poorly:
                    code.siri_one_shot = 'Poorly'

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
    return FileResponse(open(path, 'rb'), content_type='text/xml')
