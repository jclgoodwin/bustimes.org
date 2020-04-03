from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'ccts'
    url = 'https://ccts.arcticapi.com/network/vehicles'
    operators = {
        'CB': 'CBUS',
    }
