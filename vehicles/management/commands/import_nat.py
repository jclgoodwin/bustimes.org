from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'NAT'
    url = 'http://portal.natgroup.co.uk/api/buses/nearby?latitude&longitude'
