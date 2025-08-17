from datetime import datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo

from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2

from django.db.models import Q

from busstops.models import DataSource
from bustimes.models import Note, StopTime, Trip

from ...models import Vehicle, VehicleJourney
from .import_gtfsr_ie import Command as GTFSRCommand


class Command(GTFSRCommand):
    source_name = "Ember"
    vehicle_code_scheme = "Ember"

    @cache
    def get_note(self, note_code, note_text):
        # note_code = note_code or ""
        # note_text = note_text[:255]
        # if (note_code, note_text) in self.existing_notes:
        #     return self.existing_notes[(note_code, note_text)]
        return Note.objects.get_or_create(code=note_code or "", text=note_text[:255])[0]

    def do_source(self):
        self.tzinfo = ZoneInfo("Europe/London")
        self.source, _ = DataSource.objects.get_or_create(name=self.source_name)
        self.url = "https://api.ember.to/v1/gtfs/realtime/"
        return self

    def get_items(self):
        response = self.session.get(self.url, timeout=10)
        response.raise_for_status()

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        items = []

        self.existing_notes = {
            (note.code, note.text): note
            for note in Note.objects.filter(trip__operator="EMBR")
        }
        stop_notes = {}  # map of notes to lists of stop ids

        # the feed contains both vehicle positions and alerts (and possibly other entities)
        for item in feed.entity:
            if item.HasField("vehicle"):
                items.append(item)
            elif item.HasField("alert"):
                header = item.alert.header_text.translation[0].text
                if header == "Pre-booking":
                    note = self.get_note(
                        header[:1],
                        item.alert.description_text.translation[0].text,
                    )
                    if note in stop_notes:
                        stop_notes[note].append(item.alert.informed_entity[0].stop_id)
                    else:
                        stop_notes[note] = [item.alert.informed_entity[0].stop_id]

        # remove old notes
        for note in self.existing_notes.values():
            if note not in stop_notes:
                note.stoptime_set.clear()
                note.trip_set.clear()

        for note in stop_notes:
            stop_times = StopTime.objects.filter(
                stop__in=stop_notes[note], trip__operator="EMBR"
            )
            trips = Trip.objects.filter(stoptime__in=stop_times, operator="EMBR")
            note.stoptime_set.set(stop_times)
            note.trip_set.set(trips)

        return items

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id
        reg = vehicle_code.replace(" ", "")

        return Vehicle.objects.filter(Q(code=vehicle_code) | Q(code=reg)).get_or_create(
            operator_id="EMBR",
            defaults={"code": vehicle_code, "reg": reg},
        )

    def get_journey(self, item, vehicle):
        journey = VehicleJourney(code=item.vehicle.trip.trip_id)

        if (
            latest_journey := vehicle.latest_journey
        ) and latest_journey.code == journey.code:
            return latest_journey

        try:
            trip = Trip.objects.get(operator="EMBR", vehicle_journey_code=journey.code)
        except Trip.DoesNotExist:
            pass
        else:
            journey.trip = trip

            journey.datetime = (
                datetime.strptime(
                    f"{item.vehicle.trip.start_date} 12", "%Y%m%d %H"
                ).replace(tzinfo=self.tzinfo)
                - timedelta(hours=12)
                + trip.start
            )

            journey.service = trip.route.service

            journey.route_name = journey.service.line_name
            journey.destination = trip.headsign

        vehicle.latest_journey_data = json_format.MessageToDict(item)

        return journey
