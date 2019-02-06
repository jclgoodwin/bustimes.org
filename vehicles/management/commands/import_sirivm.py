import ciso8601
import logging
import xml.etree.cElementTree as ET
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point
from isodate import parse_duration
from busstops.models import Operator, Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney


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
        items = ET.fromstring(response.text)
    except ET.ParseError as e:
        logger.error(e, exc_info=True)
        print(response)
        return ()
    return items.findall('siri:ServiceDelivery/siri:VehicleMonitoringDelivery/siri:VehicleActivity', NS)


class Command(ImportLiveVehiclesCommand):
    source_name = 'sirivm'
    url = 'sslink/SSLinkHTTP'

    operators = {
        'SQ': ('BLUS', 'SVCT', 'UNIL', 'SWWD', 'DAMY', 'TDTR', 'TOUR', 'WDBC'),
        'RB': ('RBUS', 'GLRB'),
        'SCHI': ('SINV', 'SCOR'),
        'SCFI': ('SCFI', 'SSPH', 'SSTY'),
        'SCSO': ('SCHM', 'SCCO', 'SMSO'),
        'CBLE': ('CBBH', 'CBNL'),
        'RED': ('RRTR', 'RLNE'),
        'SCCM': ('SCCM', 'SCPB', 'SCHU', 'SCBD')
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

    def get_journey(self, item):
        journey = VehicleJourney()

        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        operator_ref = mvj.find('siri:OperatorRef', NS).text
        operator = None
        operator_options = None

        service = mvj.find('siri:LineRef', NS).text

        try:
            if operator_ref:
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
            print(e, operator_ref, service)

        vehicle_code = mvj.find('siri:VehicleRef', NS).text
        if operator_ref and vehicle_code.startswith(operator_ref + '-') and operator_ref != 'SQ':
            vehicle_code = vehicle_code[len(operator_ref) + 1:]

        defaults = {
            'source': self.source,
            'operator': operator
        }
        if vehicle_code.isdigit():
            defaults['fleet_number'] = vehicle_code
        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(
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

        # TODO: use ServiceCodes for this
        if service == 'QC':
            service = 'QuayConnect'
        elif service == 'FLCN':
            service = 'FALCON'
        elif service is None and operator_ref == 'TG':
            service = 'Colchester Park & Ride'
        elif service == 'P&R' and operator_ref == 'AKE':
            service = 'Colchester Park & Ride'
        elif operator_ref == 'FE':
            if service == '700':
                service = 'Sandon Park & Ride'
            elif service == '701':
                service = 'Chelmsford Park & Ride'
        elif service == 'm1' and operator_ref == 'FB':
            operator = Operator.objects.get(pk='NCTP')

        services = Service.objects.filter(line_name__iexact=service, current=True)
        if operator_options:
            services = services.filter(operator__in=operator_options).distinct()
        elif operator:
            services = services.filter(operator=operator)
        else:
            return journey, vehicle_created

        try:
            if operator and operator.id == 'TNXB' and service == '4':
                journey.service_id = 'cen_33-4-W-y11'
            else:
                journey.service = self.get_service(services, get_latlong(mvj))
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            if operator_ref != 'OFJ':
                logger.error(e, exc_info=True)
                print(e, operator_ref, service, services, get_latlong(mvj))

        if operator_options and operator and journey.service and operator.id == operator_options[0]:
            if operator.id != 'RBUS':
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
