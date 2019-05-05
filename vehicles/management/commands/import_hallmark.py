from .import_bushub import Command as BusHubCommand


class Command(BusHubCommand):
    source_name = 'Hallmark'
    url = 'http://portal.hallmarkbus.com/api/buses/nearby?latitude&longitude'

    def get_vehicle(self, item):
        item['OperatorRef'] = 'WNGS'
        return super().get_vehicle(item)
