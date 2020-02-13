from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'Courtney'
    url = 'https://courtney.arcticapi.com/network/vehicles'
    operators = {
        'CTNY': 'CTNY',
    }
