from datetime import timedelta

from django import forms
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from busstops.models import StopPoint
from .utils import get_calendars
from .models import StopTime, RouteLink


class Form(forms.Form):
    source = forms.IntegerField()
    date = forms.DateField()
    from_time = forms.TimeField()
    to_time = forms.TimeField()


@require_GET
def frequency_map(request):
    """special project"""

    form = Form(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    calendars = get_calendars(form.cleaned_data["date"])

    from_time = form.cleaned_data["from_time"]
    to_time = form.cleaned_data["to_time"]
    from_time = timedelta(hours=from_time.hour, minutes=from_time.minute)
    to_time = timedelta(hours=to_time.hour, minutes=to_time.minute)

    stop_times = StopTime.objects.filter(
        trip__route__source=form.cleaned_data["source"],
        trip__calendar__in=calendars,
        trip__start__gte=from_time,
        trip__start__lt=to_time,
    ).iterator()

    duration = to_time - from_time

    pairs = {}
    stops = set()

    route_links = RouteLink.objects.filter(service__source=form.cleaned_data["source"])
    route_links = {
        (route_link.from_stop_id, route_link.to_stop_id): route_link.geometry
        for route_link in route_links
    }

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
                        "coordinates": route_links[pair].coords
                        if pair in route_links
                        else [
                            locations[pair[0]].latlong.coords,
                            locations[pair[1]].latlong.coords,
                        ],
                    },
                    "properties": {
                        # "from": pair[0],
                        # "to": pair[1],
                        "frequency": (duration / pairs[pair]).total_seconds()
                        / 60,
                    },
                }
                for pair in pairs
            ],
        },
        headers={
            "access-control-allow-origin": "*",
            "cache-control": "max-age=6000",
        },
    )
