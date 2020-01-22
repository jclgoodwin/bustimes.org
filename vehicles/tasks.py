from celery import shared_task
from busstops.models import DataSource, ServiceCode
import xml.etree.cElementTree as ET
from io import StringIO
from .management.commands import import_sirivm
from .models import JourneyCode
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


@shared_task
def create_service_code(line_ref, service_id, scheme):
    ServiceCode.objects.update_or_create({'code': line_ref}, service_id=service_id, scheme=scheme)


@shared_task
def create_journey_code(destination, service_id, journey_ref, source_id):
    JourneyCode.objects.update_or_create({
        'destination': destination
    }, service=service_id, code=journey_ref, siri_source_id=source_id)
