from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'Lynx'
    url = 'http://portal.lynxbus.co.uk/api/buses/nearby?latitude&longitude'
