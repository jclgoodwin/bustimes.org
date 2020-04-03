from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'Go North East'
    url = 'https://gonortheast.arcticapi.com/network/vehicles'
    operators = {
        'GNE': 'GNEL'
    }
