from channels.consumer import SyncConsumer
from busstops.models import DataSource
from .management.commands import import_bod_avl


class SiriConsumer(SyncConsumer):
    def __init__(self):
        print('init')
        self.command = import_bod_avl.Command()
        self.command.source = DataSource.objects.get(name='Bus Open Data')

    def sirivm(self, message):
        self.command.handle_item(message['item'], None)
