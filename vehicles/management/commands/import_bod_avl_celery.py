from celery import group
from django.utils import timezone
from ...tasks import bod_avl
from .import_bod_avl import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    def update(self):
        now = timezone.now()

        items = self.get_items()
        if items:
            # encourage items to be grouped by operator
            items.sort(key=lambda item: item['MonitoredVehicleJourney']['OperatorRef'])

            identifiers = {}
            i = 0
            chunks = [[]]

            for item in items:
                monitored_vehicle_journey = item['MonitoredVehicleJourney']
                key = f"{monitored_vehicle_journey['OperatorRef']}-{monitored_vehicle_journey['VehicleRef']}"
                if self.identifiers.get(key) != item['RecordedAtTime']:
                    identifiers[key] = item['RecordedAtTime']
                    if i % 50:
                        chunks.append([])
                    chunks[-1].append(item)
                    i += 1
            job = group(bod_avl.s(chunk) for chunk in chunks)
            job().get()

            self.identifiers.update(identifiers)
        else:
            return 300  # no items - wait five minutes

        time_taken = timezone.now() - now
        print(time_taken)
        time_taken = time_taken.total_seconds()
        if time_taken < self.wait:
            return self.wait - time_taken
        return 0  # took longer than self.wait
