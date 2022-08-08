from django import forms
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET

from busstops.models import StopPoint
from .models import StopTime, RouteLink


class Form(forms.Form):
    source = forms.IntegerField()
    day = forms.CharField()
    from_time = forms.DurationField()
    to_time = forms.DurationField()


@require_GET
def frequency_map(request):
    """special project"""

    form = Form(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    from_time = form.cleaned_data["from_time"]
    to_time = form.cleaned_data["to_time"]

    day = form.cleaned_data["day"]

    stop_times = StopTime.objects.filter(
        **{f"trip__calendar__{day}": True},
        trip__route__source=form.cleaned_data["source"],
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

    pairs = [
        (
            route_links[pair].coords
            if pair in route_links
            else [
                locations[pair[0]].latlong.coords,
                locations[pair[1]].latlong.coords,
            ],
            (duration / pairs[pair]).total_seconds() / 60,
        )
        for pair in pairs
    ]

    pairs.sort(key=lambda pair: -pair[1])  # most frequent lasti

    return JsonResponse(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coordinates,
                    },
                    "properties": {"frequency": frequency},
                }
                for coordinates, frequency in pairs
            ],
        },
        headers={
            "access-control-allow-origin": "*",
            "cache-control": "max-age=6000",
        },
    )
