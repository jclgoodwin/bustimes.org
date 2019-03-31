from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'White Bus'
    url = 'http://portal.whitebus.co.uk/api/buses/nearby?latitude&longitude'
