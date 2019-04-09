import ciso8601
import logging
import xml.etree.cElementTree as ET
from io import StringIO
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point
from django.db.models import Q
from isodate import parse_duration
from busstops.models import Operator, Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney, JourneyCode


logger = logging.getLogger(__name__)
NS = {'siri': 'http://www.siri.org.uk/siri'}


def get_latlong(mvj):
    vl = mvj.find('siri:VehicleLocation', NS)
    lat = vl.find('siri:Latitude', NS).text
    lon = vl.find('siri:Longitude', NS).text
    return Point(float(lon), float(lat))


def items_from_response(response):
    if not (response and response.text):
        return ()
    try:
        iterator = ET.iterparse(StringIO(response.text))
    except ET.ParseError as e:
        logger.error(e, exc_info=True)
        print(response)
        return ()
    for _, element in iterator:
        if element.tag[29:] == 'VehicleActivity':
            yield element
            element.clear()


class Command(ImportLiveVehiclesCommand):
    source_name = 'sirivm'
    url = 'sslink/SSLinkHTTP'

    operators = {
        'SQ': ('BLUS', 'SVCT', 'UNIL', 'SWWD', 'DAMY', 'TDTR', 'TOUR', 'WDBC'),
        'RB': ('RBUS', 'GLRB'),
        'SCHI': ('SINV', 'SCOR'),
        'SCFI': ('SCFI', 'SSPH', 'SSTY'),
        'SCSO': ('SCHM', 'SCCO', 'SMSO', 'SCHW'),
        'SCNH': ('SCNH', 'SCWW'),
        'CBLE': ('CBBH', 'CBNL'),
        'CSLB': ('CSLB', 'OXBC'),
        'RED': ('RRTR', 'RLNE', 'REDE'),
        'SCCM': ('SCCM', 'SCPB', 'SCHU', 'SCBD'),
        'ATS': ('ARBB', 'ARHE', 'GLAR'),
        'ASC': ('ARBB', 'GLAR'),
    }

    def get_response(self, url, xml):
        try:
            return self.session.post(url, data=xml, timeout=10)
        except RequestException as e:
            print(e)
            return

    def get_items(self):
        url = 'http://{}.jmwrti.co.uk:8080/RTI-SIRI-Server/SIRIHandler'
        data = """
            <Siri xmlns="http://www.siri.org.uk/siri">
                <ServiceRequest><VehicleMonitoringRequest/></ServiceRequest>
            </Siri>
        """
        for subdomain in ('essex', 'southampton', 'slough', 'staffordshire'):
            response = self.get_response(url.format(subdomain), data)
            for item in items_from_response(response):
                yield item

        url = 'http://data.icarus.cloudamber.com/VehicleMonitoringRequest.ashx'
        data = """
            <Siri xmlns="http://www.siri.org.uk/siri">
                <ServiceRequest>
                    <RequestorRef>{}</RequestorRef>
                    <VehicleMonitoringRequest/>
                </ServiceRequest>
            </Siri>
        """
        requestor_ref = 'gatwick_app'
        response = self.get_response(url, data.format(requestor_ref))
        for item in items_from_response(response):
            yield item

    def get_journey(self, item):
        journey = VehicleJourney()

        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        operator_ref = mvj.find('siri:OperatorRef', NS).text
        operator = None
        operator_options = None

        service = mvj.find('siri:LineRef', NS).text

        try:
            if operator_ref == 'TD':  # Xplore Dundee
                return None, None
            elif operator_ref:
                operator_options = self.operators.get(operator_ref)
                if operator_options:
                    operator = Operator.objects.get(id=operator_options[0])
                else:
                    try:
                        operator = Operator.objects.get(operatorcode__source=self.source,
                                                        operatorcode__code=operator_ref)
                    except (Operator.MultipleObjectsReturned, Operator.DoesNotExist):
                        operator = Operator.objects.get(id=operator_ref)
        except (Operator.MultipleObjectsReturned, Operator.DoesNotExist) as e:
            logger.error(e, exc_info=True)
            print(e, operator_ref, service, ET.tostring(item))

        vehicle_code = mvj.find('siri:VehicleRef', NS).text
        while operator_ref and vehicle_code.startswith(operator_ref + '-'):
            if operator_ref == 'SQ' and not vehicle_code.startswith('SQ-SQ-'):
                break
            vehicle_code = vehicle_code[len(operator_ref) + 1:]

        defaults = {
            'source': self.source,
            'operator': operator
        }
        if vehicle_code.isdigit():
            defaults['fleet_number'] = vehicle_code

        vehicles = Vehicle.objects.select_related('latest_location__journey')
        if vehicle_code.startswith('GOEA-') or vehicle_code.startswith('CSLB-'):
            journey.vehicle, vehicle_created = vehicles.get_or_create(
                defaults,
                code=vehicle_code,
            )
        else:
            journey.vehicle, vehicle_created = vehicles.get_or_create(
                defaults,
                operator__in=operator_options or (operator,),
                code=vehicle_code,
            )

        journey_code = mvj.find('siri:FramedVehicleJourneyRef/siri:DatedVehicleJourneyRef', NS)
        if journey_code is not None:
            journey.code = journey_code.text

        departure_time = mvj.find('siri:OriginAimedDepartureTime', NS)
        if departure_time is not None:
            journey.datetime = ciso8601.parse_datetime(departure_time.text)

        destination = mvj.find('siri:DestinationName', NS)
        if destination is not None:
            journey.destination = destination.text

        if service is None and operator_ref == 'TG':
            service = 'Colchester Park & Ride'

        if service:
            journey.route_name = service

        services = Service.objects.filter(current=True)
        services = services.filter(Q(line_name__iexact=service) | Q(servicecode__scheme__endswith=' SIRI',
                                                                    servicecode__code=service))
        if operator_options:
            services = services.filter(operator__in=operator_options).distinct()
        elif operator:
            services = services.filter(operator=operator)
        else:
            return journey, vehicle_created

        latlong = get_latlong(mvj)

        try:
            if operator and operator.id == 'TNXB' and service == '4':
                journey.service_id = 'cen_33-4-W-y11'
            elif operator_ref != 'OFJ':
                journey.service = self.get_service(services, latlong)
        except (Service.MultipleObjectsReturned, Service.DoesNotExist):
            origin_ref = mvj.find('siri:OriginRef', NS)
            destination_ref = mvj.find('siri:DestinationRef', NS)
            if origin_ref is not None:
                origin_ref = origin_ref.text
            if destination_ref is not None:
                destination_ref = destination_ref.text

            if origin_ref:
                for queryset in (
                    services.filter(journey__stopusageusage__stop=origin_ref, journey__destination=destination_ref,
                                    journey__stopusageusage__order=0, journey__datetime=journey.datetime),
                    services.filter(stops=origin_ref).filter(journey__destination=destination_ref),
                    services.filter(stops=origin_ref).filter(stops=destination_ref),
                    services.filter(Q(stops=origin_ref) | Q(stops=destination_ref)),
                ):
                    if queryset.exists():
                        services = queryset.distinct()
                        break
            try:
                journey.service = self.get_service(services, latlong)
            except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
                logger.error(e)

        if not journey.destination and journey.code and journey.service:
            try:
                journey_code = journey.service.journeycode_set.get(code=journey.code)
                journey.destination = journey_code.destination
            except (JourneyCode.DoesNotExist, JourneyCode.MultipleObjectsReturned):
                pass

        if operator_options and operator and journey.service and operator.id == operator_options[0]:
            if operator.id != 'RBUS' and operator.id != 'ARBB':
                try:
                    operator = journey.service.operator.get()
                    if journey.vehicle.operator_id != operator.id:
                        journey.vehicle.operator = operator
                        journey.vehicle.save()
                except (Operator.MultipleObjectsReturned, Operator.DoesNotExist):
                    pass

        return journey, vehicle_created

    def create_vehicle_location(self, item):
        datetime = item.find('siri:RecordedAtTime', NS).text
        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        latlong = get_latlong(mvj)
        heading = mvj.find('siri:Bearing', NS)
        if heading is not None:
            heading = int(heading.text)
            if heading == -1:
                heading = None
        delay = mvj.find('siri:Delay', NS)
        if (delay is not None) and delay.text:
            try:
                delay = parse_duration(delay.text)
                early = -round(delay.total_seconds()/60)
            except ValueError:
                early = None
        else:
            early = None
        return VehicleLocation(
            datetime=ciso8601.parse_datetime(datetime),
            latlong=latlong,
            heading=heading,
            early=early
        )
