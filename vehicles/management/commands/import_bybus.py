from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'bybus'
    url = 'https://bybus.arcticapi.com/network/vehicles'
    operators = {
        'YELL': 'YELL',
    }
