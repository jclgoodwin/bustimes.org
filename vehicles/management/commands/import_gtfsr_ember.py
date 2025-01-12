from datetime import datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo

from google.protobuf import json_format
from google.transit import gtfs_realtime_pb2

from busstops.models import DataSource
from bustimes.models import Note, StopTime, Trip

from ...models import Vehicle, VehicleJourney
from .import_gtfsr_ie import Command as BaseCommand


class Command(BaseCommand):
    source_name = "Ember"

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
        assert response.ok

        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)

        items = []
        vehicle_codes = []

        self.existing_notes = {
            (note.code, note.text): note
            for note in Note.objects.filter(trip__operator="EMBR")
        }
        stop_notes = {}

        # build list of vehicles that have moved
        for item in feed.entity:
            if item.HasField("vehicle"):
                key = item.vehicle.vehicle.id
                value = (
                    item.vehicle.trip.route_id,
                    item.vehicle.trip.trip_id,
                    item.vehicle.trip.start_date,
                    item.vehicle.position.latitude,
                    item.vehicle.position.longitude,
                )
                if self.previous_locations.get(key) != value:
                    items.append(item)
                    vehicle_codes.append(key)
                    vehicle_codes.append(key.replace(" ", ""))
                    self.previous_locations[key] = value
            elif item.HasField("alert"):
                note = self.get_note(
                    item.alert.header_text.translation[0].text[:1],
                    item.alert.description_text.translation[0].text,
                )
                if note in stop_notes:
                    stop_notes[note].append(item.alert.informed_entity[0].stop_id)
                else:
                    stop_notes[note] = [item.alert.informed_entity[0].stop_id]

        self.prefetch_vehicles(vehicle_codes)

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

    def prefetch_vehicles(self, vehicle_codes):
        vehicles = self.vehicles.filter(operator="EMBR", code__in=vehicle_codes)
        self.vehicle_cache = {vehicle.code: vehicle for vehicle in vehicles}

    def get_vehicle(self, item):
        vehicle_code = item.vehicle.vehicle.id
        vehicle = self.vehicle_cache.get(vehicle_code)

        if not vehicle:
            vehicle = self.vehicle_cache.get(vehicle_code.replace(" ", ""))
            if vehicle:
                vehicle.code = vehicle_code
                vehicle.save(update_fields=["code"])
                self.vehicle_cache[vehicle_code] = vehicle

        if vehicle:
            return vehicle, False  # not created

        vehicle = Vehicle(code=vehicle_code, operator_id="EMBR", source=self.source)
        vehicle.save()

        return vehicle, True  # created

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
            if trip.destination_id:
                journey.destination = str(trip.destination.locality)

        vehicle.latest_journey_data = json_format.MessageToDict(item)

        return journey
