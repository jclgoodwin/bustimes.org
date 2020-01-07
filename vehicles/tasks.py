from celery import shared_task
from busstops.models import DataSource
import xml.etree.cElementTree as ET
from io import StringIO
from .management.commands import import_sirivm
from .siri_et import siri_et


@shared_task
def handle_siri_et(request_body):
    siri_et(request_body)


@shared_task
def handle_siri_vm(request_body):
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='TransMach')
    iterator = ET.iterparse(StringIO(request_body))
    for _, element in iterator:
        if element.tag[:5] != '{http':
            element.tag = '{http://www.siri.org.uk/siri}' + element.tag
        if element.tag[-15:] == 'VehicleActivity':
            command.handle_item(element, None)
            element.clear()
