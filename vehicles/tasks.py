import xml.etree.cElementTree as ET
from io import StringIO
from ciso8601 import parse_datetime
from celery import shared_task
from busstops.models import DataSource, ServiceCode, Operator
from django.db.models import Q
from disruptions.management.commands.import_siri_sx import handle_item as siri_sx
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
def handle_siri_sx(request_body):
    source = DataSource.objects.get(name='Transport for the North')
    iterator = ET.iterparse(StringIO(request_body))
    for _, element in iterator:
        if element.tag[:29] == '{http://www.siri.org.uk/siri}':
            element.tag = element.tag[29:]
            if element.tag == 'PtSituationElement':
                siri_sx(element, source)
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
def log_vehicle_journey(service, data, time, destination, source_name, url):
    operator_ref = data['OperatorRef']
    if operator_ref in {'UNIB', 'GCB', 'PLYC', 'OBC', 'SOX'}:
        return

    if not time:
        time = data.get('OriginAimedDepartureTime')

    if 'FramedVehicleJourneyRef' in data and 'DatedVehicleJourneyRef' in data['FramedVehicleJourneyRef']:
        journey_ref = data['FramedVehicleJourneyRef']['DatedVehicleJourneyRef']
    else:
        journey_ref = None

    if not (time or journey_ref):
        return

    vehicle = data['VehicleRef']

    if operator_ref and vehicle.startswith(operator_ref + '-'):
        vehicle = vehicle[len(operator_ref) + 1:]
    elif operator_ref == 'FAB' and vehicle.startswith('111-'):  # Aberdeen
        vehicle = vehicle[4:]
    elif vehicle[:5] in {'ASES-', 'CTNY-'}:
        vehicle = vehicle[5:]

    if not vehicle or vehicle == '-':
        return

    if operator_ref == 'FB' and not vehicle.isdigit():
        operator_ref = 'ABUS'

    try:
        operator = Operator.objects.get(id=operator_ref)
    except Operator.DoesNotExist:
        if not service:
            return
        try:
            operator = Operator.objects.get(service=service)
        except (Operator.DoesNotExist, Operator.MultipleObjectsReturned):
            return

    if operator.parent == 'Stagecoach':
        return

    data_source, _ = DataSource.objects.get_or_create({'url': url}, name=source_name)

    defaults = {
        'source': data_source,
        'operator': operator,
        'code': vehicle
    }

    vehicles = Vehicle.objects
    if operator.parent == 'First':
        vehicles = Vehicle.objects.filter(operator__parent='First')
    else:
        vehicles = operator.vehicle_set

    if vehicle.isdigit():
        defaults['fleet_number'] = vehicle
        vehicles = vehicles.filter(Q(code=vehicle)
                                   | Q(code__endswith=f'-{vehicle}') | Q(code__startswith=f'{vehicle}_-_'))
    else:
        vehicles = vehicles.filter(code=vehicle)

    vehicle, created = vehicles.get_or_create(defaults)

    if journey_ref and journey_ref.startswith('Unknown'):
        journey_ref = ''

    time = parse_datetime(time)

    destination = destination or ''
    route_name = data.get('LineName') or data.get('LineRef')
    if journey_ref:
        try:
            existing_journey = VehicleJourney.objects.get(vehicle=vehicle, route_name=route_name, code=journey_ref,
                                                          datetime__date=time.date())
            if existing_journey.datetime != time:
                existing_journey.datetime = time
                existing_journey.save(update_fields=['datetime'])
        except VehicleJourney.DoesNotExist:
            VehicleJourney.objects.create(vehicle=vehicle, service_id=service, route_name=route_name,
                                          code=journey_ref, datetime=time, source=data_source, destination=destination)
        except VehicleJourney.MultipleObjectsReturned:
            return
    elif not VehicleJourney.objects.filter(vehicle=vehicle, route_name=route_name, datetime=time).exists():
        VehicleJourney.objects.create(vehicle=vehicle, service_id=service, route_name=route_name,
                                      datetime=time, source=data_source, destination=destination)
