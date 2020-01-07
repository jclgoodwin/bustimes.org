from celery import shared_task
from busstops.models import DataSource
from .management.commands import import_sirivm
from .siri_et import siri_et


@shared_task
def handle_siri_et(request_body):
    siri_et(request_body)


@shared_task
def handle_siri_vm(request_body):
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='TransMach')
    for item in import_sirivm.items_from_response(request_body):
        command.handle_item(item, None)
