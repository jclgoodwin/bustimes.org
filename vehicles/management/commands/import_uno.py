
from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'Uno'
    url = 'http://portal.unobus.info/api/buses/nearby?latitude&longitude'

    def get_vehicle(self, item):
        item['OperatorRef'] = 'UNOE'
        return super().get_vehicle(item)
