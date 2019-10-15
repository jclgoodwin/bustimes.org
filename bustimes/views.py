from ciso8601 import parse_datetime
from django.db.models import Min
from django.views.generic.detail import DetailView
from django.utils import timezone
from busstops.models import StopPoint
from .timetables import Timetable
from .models import Route


class RouteDetailView(DetailView):
    model = Route

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        trips = self.object.trip_set.prefetch_related('calendar__calendardate_set')
        context['trips'] = trips.annotate(departure_time=Min('stoptime__departure'))

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

        timetable = Timetable([self.object], date)
        timetable.groupings = [grouping for grouping in timetable.groupings if grouping.rows]

        stops = [row.stop for grouping in timetable.groupings for row in grouping.rows]
        stops = StopPoint.objects.select_related('locality').in_bulk(stops)
        for grouping in timetable.groupings:
            for row in grouping.rows:
                row.stop = stops.get(row.stop.atco_code, row.stop)

        context['timetable'] = timetable

        return context
