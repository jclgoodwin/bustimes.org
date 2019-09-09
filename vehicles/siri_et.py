import xml.etree.cElementTree as ET
from io import StringIO
from ciso8601 import parse_datetime
from busstops.models import Service, DataSource
from .models import Vehicle, VehicleLocation, VehicleJourney, Call


ns = {
    'siri': 'http://www.siri.org.uk/siri'
}
operator_refs = {
    'ANW': ('ANWE', 'AMSY', 'ACYM'),
    'AYK': ('WRAY',),
    'YTG': ('YTIG',),
    'ATS': ('ARBB', 'GLAR'),
    'ANE': ('ANEA', 'ANUM'),
    'ASC': ('ARHE', 'AKSS', 'AMTM'),
    'AMD': ('AMNO', 'AMID', 'AFCL'),
}
vehicles = Vehicle.objects.select_related('latest_location__journey')


def handle_journey(element, source, when):
    journey_element = element.find('siri:EstimatedVehicleJourney', ns)
    vehicle = journey_element.find('siri:VehicleRef', ns)
    if vehicle is None:
        return

    operator = None
    operator_ref, fleet_number = vehicle.text.split('-')
    if not fleet_number.isdigit():
        fleet_number = None
    if operator_ref in operator_refs:
        operator = operator_refs[operator_ref]
        vehicle, vehicle_created = vehicles.get_or_create({'source': source}, code=vehicle.text,
                                                          fleet_number=fleet_number, operator_id=operator[0])
    else:
        vehicle, vehicle_created = vehicles.get_or_create({'source': source}, code=vehicle.text,
                                                          fleet_number=fleet_number)

    journey_ref = journey_element.find('siri:DatedVehicleJourneyRef', ns).text
    if vehicle.latest_location and vehicle.latest_location.journey.code == journey_ref:
        journey = vehicle.latest_location.journey
        journey_created = False
    else:
        journey = None

    calls = []

    for call in journey_element.find('siri:EstimatedCalls', ns):
        visit_number = int(call.find('siri:VisitNumber', ns).text)
        stop_id = call.find('siri:StopPointRef', ns).text
        if not journey and visit_number == 1:
            departure_time = call.find('siri:AimedDepartureTime', ns)
            if departure_time is None:
                return
            departure_time = departure_time.text
            route_name = journey_element.find('siri:PublishedLineName', ns).text
            destination = journey_element.find('siri:DirectionName', ns).text
            try:
                services = Service.objects.filter(current=True, stops=stop_id, line_name=route_name).distinct()
                if operator:
                    service = services.get(operator__in=operator)
                else:
                    service = services.get()
                if not service.tracking:
                    service.tracking = True
                    service.save(update_fields=['tracking'])
            except (Service.MultipleObjectsReturned, Service.DoesNotExist):
                service = None

            journey, journey_created = VehicleJourney.objects.get_or_create({
                'code': journey_ref,
                'route_name': route_name,
                'destination': destination,
                'source': source,
                'service': service
                },
                vehicle=vehicle,
                datetime=departure_time
            )
        if not journey:
            return
        aimed_arrival_time = call.find('siri:AimedArrivalTime', ns)
        if aimed_arrival_time is not None:
            aimed_arrival_time = aimed_arrival_time.text
        expected_arrival_time = call.find('siri:ExpectedArrivalTime', ns)
        if expected_arrival_time is not None:
            expected_arrival_time = parse_datetime(expected_arrival_time.text)
        aimed_departure_time = call.find('siri:AimedDepartureTime', ns)
        if aimed_departure_time is not None:
            aimed_departure_time = aimed_departure_time.text
        expected_departure_time = call.find('siri:ExpectedDepartureTime', ns)
        if expected_departure_time is not None:
            expected_departure_time = parse_datetime(expected_departure_time.text)
        if journey_created:
            call = Call(stop_id=stop_id, journey=journey, visit_number=visit_number,
                        aimed_arrival_time=aimed_arrival_time, aimed_departure_time=aimed_departure_time)
            call_created = False
        else:
            call, call_created = Call.objects.get_or_create({
                'aimed_arrival_time': aimed_arrival_time,
                'expected_arrival_time': expected_arrival_time,
                'aimed_departure_time': aimed_departure_time,
                'expected_departure_time': expected_departure_time
            }, stop_id=stop_id, journey=journey, visit_number=visit_number)
        if not call_created:
            call.expected_arrival_time = expected_arrival_time
            call.expected_departure_time = expected_departure_time
            calls.append(call)
    if journey_created:
        Call.objects.bulk_create(calls)
    else:
        Call.objects.bulk_update(calls, fields=['expected_arrival_time', 'expected_departure_time'])
    previous_call = None
    for call in journey.call_set.order_by('visit_number'):
        if previous_call:
            previous_time = previous_call.expected_arrival_time or previous_call.expected_departure_time
            time = call.expected_departure_time or call.expected_arrival_time
            if previous_time and time and previous_time <= when and time >= when:
                if vehicle.latest_location:
                    vehicle.latest_location.journey = journey
                    vehicle.latest_location.latlong = previous_call.stop.latlong
                    vehicle.latest_location.heading = previous_call.stop.get_heading()
                    vehicle.latest_location.datetime = previous_time
                    vehicle.latest_location.save()
                else:
                    vehicle.latest_location = VehicleLocation.objects.create(
                        journey=journey,
                        latlong=previous_call.stop.latlong,
                        heading=previous_call.stop.get_heading(),
                        datetime=previous_time,
                        current=True
                    )
                    vehicle.save(update_fields=['latest_location'])
                vehicle.update_last_modified()
                return
        previous_call = call


def siri_et(request_body):
    source = DataSource.objects.get(name='Arriva')
    iterator = ET.iterparse(StringIO(request_body))
    for _, element in iterator:
        tag = element.tag[29:]
        if tag == 'RecordedAtTime':
            when = parse_datetime(element.text)
        elif tag == 'EstimatedJourneyVersionFrame':
            handle_journey(element, source, when)
            element.clear()
