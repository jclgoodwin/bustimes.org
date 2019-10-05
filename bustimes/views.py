from ciso8601 import parse_datetime
from django.views.generic.detail import DetailView
from django.utils import timezone
from busstops.models import StopPoint
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
                date = None
        if not date:
            date = None

        timetable = self.object.get_timetable(date)
        timetable.groupings = [grouping for grouping in timetable.groupings if grouping.rows]

        stops = [row.stop for grouping in timetable.groupings for row in grouping.rows]
        stops = StopPoint.objects.select_related('locality').in_bulk(stops)
        for grouping in timetable.groupings:
            for row in grouping.rows:
                row.stop = stops.get(row.stop, row.stop)

        context['timetable'] = timetable

        return context
