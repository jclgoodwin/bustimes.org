import os
import zipfile
from django.conf import settings
from django.views.generic.detail import DetailView
from django.http import FileResponse, Http404
from django.utils import timezone
from busstops.views import Service
from vehicles.views import siri_one_shot
from .models import Route


class ServiceDebugView(DetailView):
    model = Service
    queryset = model.objects.prefetch_related('route_set__trip_set__calendar__calendardate_set')
    template_name = 'service_debug.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        now = timezone.localtime()

        context['codes'] = self.object.servicecode_set.all()
        for code in context['codes']:
            if code.scheme.endswith(' SIRI'):
                code.siri_one_shot = siri_one_shot(code, now)

        context['breadcrumb'] = [self.object]

        return context


def route_xml(request, source, code):
    try:
        Route.objects.get(source=source, code__startswith=code)
    except Route.MultipleObjectsReturned:
        pass
    except Route.DoesNotExist:
        raise Http404
    path = os.path.join(settings.TNDS_DIR, f'{source}.zip')
    try:
        with zipfile.ZipFile(path) as archive:
            return FileResponse(archive.open(code), content_type='text/xml')
    except FileNotFoundError:
        path = code.split('/')[0]
        with zipfile.ZipFile(os.path.join(settings.DATA_DIR, path)) as archive:
            code = code[len(path) + 1:]
            return FileResponse(archive.open(code), content_type='text/xml')
