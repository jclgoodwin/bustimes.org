import xml.etree.cElementTree as ET
from io import StringIO
from ciso8601 import parse_datetime
from django.utils import timezone
from busstops.models import Service, StopPoint, DataSource
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


def handle_journey(element, source):
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

    journey = None

    journey_ref = journey_element.find('siri:DatedVehicleJourneyRef', ns).text
    if vehicle.latest_location and vehicle.latest_location.journey.code == journey_ref:
        journey = vehicle.latest_location.journey

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
                services = Service.objects.filter(current=True, stops=stop_id, line_name=route_name)
                if operator:
                    service = services.get(operator__in=operator)
                else:
                    service = services.get()
                    if not service.tracking:
                        service.tracking = True
                        service.save(update_fields=['tracking'])
            except (Service.MultipleObjectsReturned, Service.DoesNotExist):
                service = None

            journey, _ = VehicleJourney.objects.get_or_create({
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
        if expected_arrival_time and expected_arrival_time < timezone.now():
            stop = StopPoint.objects.get(pk=stop_id)
            if vehicle.latest_location:
                vehicle.latest_location.journey = journey
                vehicle.latest_location.latlong = stop.latlong
                vehicle.latest_location.heading = stop.get_heading()
                vehicle.latest_location.datetime = expected_arrival_time
                vehicle.latest_location.save()
            else:
                vehicle.latest_location = VehicleLocation.objects.create(
                    journey=journey,
                    latlong=stop.latlong,
                    heading=stop.heading,
                    datetime=expected_arrival_time
                )
                vehicle.save(update_fields=['latest_location'])
        Call.objects.update_or_create({
            'aimed_arrival_time': aimed_arrival_time,
            'expected_arrival_time': expected_arrival_time,
            'aimed_departure_time': aimed_departure_time,
            'expected_departure_time': expected_departure_time,
            },
            stop_id=stop_id,
            journey=journey,
            visit_number=visit_number
        )


def siri_et(request_body):
    source = DataSource.objects.get(name='Arriva')
    iterator = ET.iterparse(StringIO(request_body))
    for _, element in iterator:
        if element.tag[29:] == 'EstimatedJourneyVersionFrame':
            try:
                handle_journey(element, source)
            except StopPoint.DoesNotExist as e:
                print(e)
                pass
            element.clear()
