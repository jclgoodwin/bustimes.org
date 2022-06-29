import requests
from datetime import timedelta
from google.transit import gtfs_realtime_pb2
from django.core.cache import cache
from django.conf import settings
from google.protobuf import json_format
from bustimes.formatting import format_timedelta

url = "https://api.nationaltransport.ie/gtfsr/v1"


def get_response():
    if settings.NTA_API_KEY:
        response = requests.get(
            url, headers={"x-api-key": settings.NTA_API_KEY}, timeout=10
        )
        if response.ok:
            return response.content


def update(trip_id):
    content = cache.get_or_set("ntaie", get_response)

    if not content:
        return

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)

    for entity in feed.entity:
        if entity.trip_update.trip.trip_id == trip_id:
            return json_format.MessageToDict(entity)


def get_trip_update(trip):
    if trip.ticket_machine_code:
        key = f"trip{trip.ticket_machine_code}"

        trip_update = cache.get(key)

        trip_update = update(trip.ticket_machine_code)
        if trip_update:
            return trip_update


def apply_trip_update(stops, trip_update):
    if "stopTimeUpdate" not in trip_update["tripUpdate"]:
        return

    stops_by_sequence = {}
    for stop in stops:
        assert stop.sequence not in stops_by_sequence
        stops_by_sequence[stop.sequence] = stop
        stop.update = None

    for stop_time_update in trip_update["tripUpdate"]["stopTimeUpdate"]:
        sequence = stop_time_update["stopSequence"]
        stop_time = stops_by_sequence[sequence]
        assert sequence == stop_time.sequence
        assert stop_time_update["stopId"] == stop_time.stop_id
        stop_time.update = stop_time_update

    stop_time_update = None
    for stop_time in stops:
        if stop_time.update:
            stop_time_update = stop_time.update

        if stop_time_update:
            stop_time.update = stop_time_update
            if stop_time.arrival:
                stop_time.expected_arrival = format_timedelta(
                    stop_time.arrival
                    + timedelta(seconds=stop_time_update["arrival"]["delay"])
                )
            if stop_time.departure:
                stop_time.expected_departure = format_timedelta(
                    stop_time.departure
                    + timedelta(seconds=stop_time_update["departure"]["delay"])
                )
