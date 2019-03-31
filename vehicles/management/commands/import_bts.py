from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'bts'
    url = 'https://bts.arcticapi.com/network/vehicles'
    operators = {
        'BTS': 'BLAC',
    }
