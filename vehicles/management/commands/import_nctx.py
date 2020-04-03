from .import_polar import Command as ImportLiveVehiclesCommand


class Command(ImportLiveVehiclesCommand):
    source_name = 'nctx'
    url = 'https://nctx.arcticapi.com/network/vehicles'
    operators = {
        'NCT': 'NCTR',
    }
