from ciso8601 import parse_datetime
from django.views.generic.detail import DetailView
from django.utils import timezone
from .models import Route


class RouteDetailView(DetailView):
    model = Route
    # queryset = model.objects.prefetch_related('trip_set__stoptime_set')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date = self.request.GET.get('date')
        today = timezone.localtime().date()
        if date:
            try:
                date = parse_datetime(date).date()
                if date < today:
                    date = today
            except ValueError:
                date = today
        if not date:
            date = today

        timetable = self.object.get_timetable(date)
        timetable.groupings = [grouping for grouping in timetable.groupings if grouping.rows]

        context['timetable'] = timetable

        return context
