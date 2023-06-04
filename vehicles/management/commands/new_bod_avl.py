import json

import tqdm
from django.core.cache import cache
from django.utils import timezone

from vehicles.models import VehicleCode

from ...utils import redis_client
from .import_bod_avl import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    wait = 17

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hist = {}
        self.identifiers = {}
        self.journeys_ids = {}
        self.journeys_ids_ids = {}

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

    def handle_items(self, items, identities):
        vehicle_codes = VehicleCode.objects.filter(
            code__in=identities, scheme="BODS"
        ).select_related("vehicle__latest_journey__trip")

        vehicles_by_identity = {code.code: code.vehicle for code in vehicle_codes}

        vehicle_locations = redis_client.mget(
            [f"vehicle{vc.vehicle_id}" for vc in vehicle_codes]
        )
        vehicle_locations = {
            vehicle_codes[i].vehicle_id: json.loads(item)
            for i, item in enumerate(vehicle_locations)
            if item
        }

        for i, item in enumerate(tqdm.tqdm(items)):

            vehicle_identity = identities[i]

            journey_identity = self.journeys_ids[vehicle_identity]

            if vehicle_identity in vehicles_by_identity:
                vehicle = vehicles_by_identity[vehicle_identity]
            else:
                vehicle, created = self.get_vehicle(item)
                # print(vehicle_identity, vehicle, created)
                VehicleCode.objects.create(
                    code=vehicle_identity, scheme="BODS", vehicle=vehicle
                )

            keep_journey = False
            if vehicle_identity in self.journeys_ids_ids:
                journey_identity_id = self.journeys_ids_ids[vehicle_identity]
                if journey_identity_id == (journey_identity, vehicle.latest_journey_id):
                    keep_journey = True  # can dumbly keep same latest_journey

            result = self.handle_item(
                item,
                self.source.datetime,
                vehicle=vehicle,
                latest=vehicle_locations.get(vehicle.id, False),
                keep_journey=keep_journey,
            )

            if result:
                location, vehicle = result

                self.journeys_ids_ids[vehicle_identity] = (
                    journey_identity,
                    vehicle.latest_journey_id,
                )

            self.identifiers[vehicle_identity] = item["RecordedAtTime"]

            if i and not i % 500:
                self.save()

        self.save()

    def get_changed_items(self):
        changed_items = []
        changed_journey_items = []
        changed_item_identities = []
        changed_journey_identities = []
        # (changed items and changed journey items are separate
        # so we can do the quick ones first)

        total_items = 0

        for i, item in enumerate(self.get_items()):
            vehicle_identity = self.get_vehicle_identity(item)

            journey_identity = self.get_journey_identity(item)

            total_items += 1

            if self.identifiers.get(vehicle_identity) == item["RecordedAtTime"]:
                if journey_identity == self.journeys_ids[vehicle_identity]:
                    continue
                print(self.journeys_ids[vehicle_identity], item)
            if (
                vehicle_identity not in self.journeys_ids
                or journey_identity != self.journeys_ids[vehicle_identity]
            ):
                changed_journey_items.append(item)
                changed_journey_identities.append(vehicle_identity)
            else:
                changed_items.append(item)
                changed_item_identities.append(vehicle_identity)

            self.journeys_ids[vehicle_identity] = journey_identity

        return (
            changed_items,
            changed_journey_items,
            changed_item_identities,
            changed_journey_identities,
            total_items,
        )

    def update(self):
        now = timezone.now()

        (
            changed_items,
            changed_journey_items,
            changed_item_identities,
            changed_journey_identities,
            total_items,
        ) = self.get_changed_items()

        age = (now - self.source.datetime).total_seconds()
        self.hist[now.second % 10] = age
        print(self.hist)
        print(
            f"{now.second=} {age=}  {total_items=}  {len(changed_items)=}  {len(changed_journey_items)=}"
        )

        self.handle_items(changed_items, changed_item_identities)
        self.handle_items(changed_journey_items, changed_journey_identities)

        # stats for last 10 updates:
        bod_status = cache.get("bod_avl_status", [])
        bod_status.append(
            (
                now,
                self.source.datetime,
                total_items,
                len(changed_items) + len(changed_journey_items),
            )
        )
        bod_status = bod_status[-50:]
        cache.set_many(
            {
                "bod_avl_status": bod_status,
            },
            None,
        )

        time_taken = (timezone.now() - now).total_seconds()
        print(f"{time_taken=}")

        # bods updates "every 10 seconds",
        # it's usually worth waiting 0-9 seconds
        # before the next fetch
        # for maximum freshness:

        witching_hour = min(self.hist, key=self.hist.get)
        worst_hour = max(self.hist, key=self.hist.get)
        now = timezone.now().second % 10
        wait = witching_hour - now
        if wait < 0:
            wait += 10
        if time_taken < 10:
            wait += 10
        diff = worst_hour - witching_hour
        print(f"{witching_hour=} {worst_hour=} {diff=} {now=} {wait=}\n")
        if diff % 10 == 9:
            return wait

        return max(self.wait - time_taken, 0)
