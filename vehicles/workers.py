from channels.consumer import SyncConsumer
from django.core.cache import cache
from django.db.utils import OperationalError
from .management.commands import import_bod_avl


class SiriConsumer(SyncConsumer):
    command = None

    def sirivm(self, message):
        if self.command is None:
            self.command = import_bod_avl.Command().do_source()

        vehicle_cache_keys = [self.command.get_vehicle_cache_key(item) for item in message['items']]
        vehicle_ids = cache.get_many(vehicle_cache_keys)  # code: id
        try:
            vehicles = self.command.vehicles.in_bulk(vehicle_ids.values())  # id: vehicle
            self.command.vehicle_cache = {  # code: vehicle
                key: vehicles[vehicle_id] for key, vehicle_id in vehicle_ids.items() if vehicle_id in vehicles
            }
        except OperationalError:
            vehicles = None

        for item in message['items']:
            self.command.handle_item(item)

        self.command.save()

        if vehicles:
            cache.set_many({
                key: value
                for key, value in self.command.vehicle_id_cache.items()
                if key not in vehicle_ids or value != vehicle_ids
            })
