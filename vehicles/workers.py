from channels.consumer import SyncConsumer
from .management.commands import import_bod_avl


class SiriConsumer(SyncConsumer):
    command = None

    def sirivm(self, message):
        if self.command is None:
            self.command = import_bod_avl.Command().do_source()

        for item in message['items']:
            self.command.handle_item(item)

        self.command.save()
