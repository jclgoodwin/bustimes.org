import xml.etree.cElementTree as ET
from ciso8601 import parse_datetime
from celery import shared_task
from busstops.models import DataSource, ServiceCode, Operator
from io import StringIO
from .management.commands import import_sirivm
from .models import JourneyCode, Vehicle, VehicleJourney
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
    }, service_id=service_id, code=journey_ref, siri_source_id=source_id)


@shared_task
def log_vehicle_journey(operator_ref, vehicle, service, time, journey_ref, destination, source_name, source_url):
    if operator_ref == 'UNIB' or operator_ref == 'GCB':
        return
    if not (time or journey_ref):
        return

    if operator_ref and vehicle.startswith(operator_ref + '-'):
        vehicle = vehicle[len(operator_ref) + 1:]
    elif operator_ref == 'FAB' and vehicle.startswith('111-'):  # Aberdeen
        vehicle = vehicle[4:]
    elif vehicle[:5] in {'ASES-', 'CTNY-'}:
        vehicle = vehicle[5:]

    if not vehicle or vehicle == '-':
        return

    try:
        operator = Operator.objects.get(id=operator_ref)
    except Operator.DoesNotExist:
        try:
            operator = Operator.objects.get(service=service)
        except (Operator.DoesNotExist, Operator.MultipleObjectsReturned):
            return

    if operator.name.startswith('Stagecoach'):
        return

    data_source, _ = DataSource.objects.get_or_create({'url': source_url}, name=source_name)

    defaults = {
        'source': data_source
    }

    if vehicle.isdigit():
        defaults['code'] = vehicle
        vehicle, created = Vehicle.objects.get_or_create(defaults, operator=operator, fleet_number=vehicle)
    else:
        vehicle, created = Vehicle.objects.get_or_create(defaults, operator=operator, code=vehicle)

    if journey_ref and journey_ref.startswith('Unknown'):
        journey_ref = ''

    time = parse_datetime(time)

    destination = destination or ''
    if journey_ref:
        try:
            existing_journey = VehicleJourney.objects.get(vehicle=vehicle, service_id=service, code=journey_ref,
                                                          datetime__date=time.date())
            if existing_journey.datetime != time:
                existing_journey.datetime = time
                existing_journey.save(update_fields=['datetime'])
        except VehicleJourney.DoesNotExist:
            VehicleJourney.objects.create(vehicle=vehicle, service_id=service, code=journey_ref,
                                          datetime=time,
                                          source=data_source, destination=destination)
        except VehicleJourney.MultipleObjectsReturned:
            pass
    else:
        defaults = {
            'destination': destination,
            'source': data_source
        }
        VehicleJourney.objects.get_or_create(defaults, vehicle=vehicle, service=service,
                                             datetime=time)
