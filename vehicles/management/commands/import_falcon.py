from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'Falcon'
    url = 'http://portal.falconbuses.co.uk/api/buses/nearby?latitude&longitude'
