import json

import tqdm
from django.core.cache import cache
from django.utils import timezone

from vehicles.models import VehicleCode

from ...utils import redis_client
from .import_bod_avl import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    wait = 28
    identifiers = {}
    journeys = {}

    @staticmethod
    def get_vehicle_identity(item):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]
        operator_ref = monitored_vehicle_journey["OperatorRef"]
        vehicle_ref = monitored_vehicle_journey["VehicleRef"]

        try:
            vehicle_unique_id = item["Extensions"]["VehicleJourney"]["VehicleUniqueId"]
        except (KeyError, TypeError):
            pass
        else:
            vehicle_ref = f"{vehicle_ref}:{vehicle_unique_id}"

        return f"{operator_ref}:{vehicle_ref}"

    @staticmethod
    def get_journey_identity(item):
        monitored_vehicle_journey = item["MonitoredVehicleJourney"]
        try:
            journey_ref = monitored_vehicle_journey["FramedVehicleJourneyRef"]
        except (KeyError, ValueError):
            journey_ref = monitored_vehicle_journey.get("VehicleJourneyRef")

        return f"{journey_ref}"

    def update(self):
        now = timezone.localtime()
        self.source.datetime = now

        items = self.get_items()

        changed_items = []
        changed_item_identities = []

        changed_journeys = 0

        for i, item in enumerate(items):
            vehicle_identity = self.get_vehicle_identity(item)

            journey_identity = self.get_journey_identity(item)

            # datetime = self.get_datetime(item)
            # if (now - datetime).total_seconds() > 900:
            #     continue

            if self.identifiers.get(vehicle_identity) == item["RecordedAtTime"]:
                assert journey_identity == self.journeys[vehicle_identity]
                continue
            else:
                changed_items.append(item)
                changed_item_identities.append(vehicle_identity)

                if (
                    journey_identity not in self.journeys
                    or journey_identity != self.journeys[vehicle_identity]
                ):
                    changed_journeys += 0

            self.journeys[vehicle_identity] = journey_identity

        print(f"{changed_journeys=}")

        vehicle_codes = VehicleCode.objects.filter(
            code__in=changed_item_identities, scheme="BODS"
        ).select_related("vehicle__latest_journey__trip")
        vehicles_by_identity = {code.code: code for code in vehicle_codes}

        print(f"{len(items)=}")
        print(f"{len(changed_items)=}")

        vehicle_locations = redis_client.mget(
            [f"vehicle{vc.vehicle_id}" for vc in vehicle_codes]
        )
        vehicle_locations = {
            vehicle_codes[i].vehicle_id: json.loads(item)
            for i, item in enumerate(vehicle_locations)
            if item
        }

        ev = 0
        nv = 0

        for i, item in enumerate(tqdm.tqdm(changed_items)):
            vehicle_identity = changed_item_identities[i]

            if vehicle_identity in vehicles_by_identity:
                vehicle = vehicles_by_identity[vehicle_identity].vehicle
                ev += 1
            else:
                vehicle, created = self.get_vehicle(item)
                # print(vehicle_identity, vehicle, created)
                VehicleCode.objects.create(
                    code=vehicle_identity, scheme="BODS", vehicle=vehicle
                )
                nv += 1

            self.handle_item(
                item, vehicle=vehicle, latest=vehicle_locations.get(vehicle.id, False)
            )

            self.identifiers[vehicle_identity] = item["RecordedAtTime"]

            if i and not i % 500:
                self.save()

        self.save()

        # stats for last 10 updates:
        bod_status = cache.get("bod_avl_status", [])
        bod_status.append((timezone.now(), self.source.datetime, len(items), ev + nv))
        bod_status = bod_status[-50:]
        cache.set_many(
            {
                "bod_avl_status": bod_status,
                # "bod_avl_identifiers": self.identifiers,  # backup
            },
            None,
        )

        time_taken = (timezone.now() - now).total_seconds()

        if ev + nv == 0:
            return 11

        return max(self.wait - time_taken, 0)