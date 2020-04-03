from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'West Coast Motors'
    url = 'https://westcoastmotors.arcticapi.com/network/vehicles'
    operators = {
        'GCB': 'GCTB',
        'WCM': 'WCMO'
    }
