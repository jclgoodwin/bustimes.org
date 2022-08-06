from django import forms
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from busstops.models import StopPoint
from .utils import get_calendars
from .models import StopTime


class Form(forms.Form):
    source = forms.IntegerField()
    date = forms.DateField()


def get_color(frequency):
    if frequency < 20:
        return "red"
    if frequency < 50:
        return "blue"
    return "green"


@require_GET
def frequency_map(request):
    """special project"""

    form = Form(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    calendars = get_calendars(form.cleaned_data["date"])

    stop_times = StopTime.objects.filter(
        trip__route__source=form.cleaned_data["source"],
        trip__calendar__in=calendars,
    ).iterator()

    pairs = {}
    stops = set()

    previous = None
    for stop_time in stop_times:
        if not stop_time.stop_id:
            continue

        stops.add(stop_time.stop_id)

        if previous and previous.trip_id == stop_time.trip_id:
            pair = (previous.stop_id, stop_time.stop_id)

            if pair in pairs:
                pairs[pair] += 1
            else:
                pairs[pair] = 1

        previous = stop_time

    locations = StopPoint.objects.only("latlong").in_bulk(stops)

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            locations[pair[0]].latlong.coords,
                            locations[pair[1]].latlong.coords,
                        ],
                    },
                    "properties": {
                        "from": pair[0],
                        "to": pair[1],
                        "frequency": pairs[pair],
                    },
                    "style": {"stroke": get_color(pairs[pair])},
                }
                for pair in pairs
            ],
        }
    )
