from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'EYMS'
    url = 'https://eyms.arcticapi.com/network/vehicles'
    operators = {
        'HOT_RACK_': 'EYMS',
        'EY': 'EYMS',
    }
