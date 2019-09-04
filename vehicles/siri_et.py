import xml.etree.cElementTree as ET
from io import BytesIO
from ciso8601 import parse_datetime
from django.utils import timezone
from busstops.models import Service, StopPoint, DataSource
from .models import Vehicle, VehicleLocation, VehicleJourney, Call


ns = {
    'siri': 'http://www.siri.org.uk/siri'
}
operator_refs = {
    'ANW': ('ANWE',),
    'AYK': ('WRAY',),
    'YTG': ('YTIG',),
    'ATS': ('ARBB',),
    'ANE': ('ANEA',),
    'ASC': ('ARHE',),
}


def handle_journey(element, source):
    journey = element.find('siri:EstimatedVehicleJourney', ns)
    vehicle = journey.find('siri:VehicleRef', ns)
    if vehicle is None:
        return
    try:
        operator = None
        operator_ref, fleet_number = vehicle.text.split('-')
        if not fleet_number.isdigit():
            fleet_number = None
        if operator_ref in operator_refs:
            operator = operator_refs[operator_ref]
            vehicle, created = Vehicle.objects.get_or_create({'source': source}, code=vehicle.text,
                                                             fleet_number=fleet_number, operator_id=operator[0])
        else:
            vehicle, created = Vehicle.objects.get_or_create({'source': source}, code=vehicle.text,
                                                             fleet_number=fleet_number)
        vehicle_journey = None
        stop_id = None
        for call in journey.find('siri:EstimatedCalls', ns):
            visit_number = int(call.find('siri:VisitNumber', ns).text)
            stop_id = call.find('siri:StopPointRef', ns).text
            if visit_number == 1:
                journey_ref = journey.find('siri:DatedVehicleJourneyRef', ns).text
                if not created and vehicle.latest_location:
                    if vehicle.latest_location.journey.code == journey_ref:
                        vehicle_journey = vehicle.latest_location.journey
                else:
                    departure_time = call.find('siri:AimedDepartureTime', ns)
                    if departure_time is None:
                        return
                    departure_time = departure_time.text
                    route_name = journey.find('siri:PublishedLineName', ns).text
                    destination = journey.find('siri:DirectionName', ns).text
                    try:
                        services = Service.objects.get(current=True, stops=stop_id, line_name=route_name)
                        if operator:
                            service = services.get(operator__in=operator)
                        else:
                            service = services.get()
                        if not service.tracking:
                            service.tracking = True
                            service.save(update_fields=['tracking'])
                    except (Service.MultipleObjectsReturned, Service.DoesNotExist):
                        service = None
                    vehicle_journey, _ = VehicleJourney.objects.get_or_create(
                        {
                            'code': journey_ref,
                            'route_name': route_name,
                            'destination': destination,
                            'source': source,
                            'service': service
                        },
                        vehicle=vehicle,
                        datetime=departure_time
                    )
            if not vehicle_journey:
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
                    vehicle.latest_location.journey = vehicle_journey
                    vehicle.latest_location.latlong = stop.latlong
                    vehicle.latest_location.heading = stop.get_heading()
                    vehicle.latest_location.datetime = expected_arrival_time
                    vehicle.latest_location.save()
                else:
                    vehicle.latest_location = VehicleLocation.objects.create(
                        journey=vehicle_journey,
                        latlong=stop.latlong,
                        heading=stop.heading,
                        datetime=expected_arrival_time
                    )
                    vehicle.save(update_fields=['latest_location'])
            Call.objects.update_or_create(
                {
                    'aimed_arrival_time': aimed_arrival_time,
                    'expected_arrival_time': expected_arrival_time,
                    'aimed_departure_time': aimed_departure_time,
                    'expected_departure_time': expected_departure_time,
                },
                stop_id=stop_id,
                journey=vehicle_journey,
                visit_number=visit_number
            )
    except StopPoint.DoesNotExist as e:
        print(e)


def siri_et(request_body):
    source = DataSource.objects.get_or_create(name='Arriva')[0]
    iterator = ET.iterparse(BytesIO(request_body))
    for _, element in iterator:
        if element.tag[29:] == 'EstimatedJourneyVersionFrame':
            handle_journey(element, source)
            element.clear()
