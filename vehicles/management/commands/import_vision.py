from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'Vision Bus'
    url = 'http://portal.visionbus.co.uk/api/buses/nearby?latitude&longitude'
