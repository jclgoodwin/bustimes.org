from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'Borders Buses'
    url = 'https://bordersbuses.arcticapi.com/network/vehicles'
    operators = {
        'BB': 'BORD'
    }
