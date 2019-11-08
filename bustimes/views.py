from django.views.generic.detail import DetailView
from django.utils import timezone
from busstops.views import Service
from vehicles.views import siri_one_shot


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

        return context
