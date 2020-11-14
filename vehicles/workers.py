from channels.consumer import SyncConsumer
from busstops.models import DataSource
from .management.commands import import_bod_avl


class SiriConsumer(SyncConsumer):
    command = None

    def sirivm(self, message):
        if self.command is None:
            self.command = import_bod_avl.Command()
            self.command.source = DataSource.objects.get(name='Bus Open Data')
        for item in message['items']:
            self.command.handle_item(item, None)
