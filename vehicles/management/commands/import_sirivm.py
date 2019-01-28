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
    if not response:
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
        if operator_ref and vehicle_code.startswith(operator_ref + '-'):
            vehicle_code = vehicle_code[len(operator_ref) + 1:]

        defaults = {
            'source': self.source,
            'operator': operator
        }
        if vehicle_code.isdigit():
            defaults['fleet_number'] = vehicle_code
        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(
            defaults
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
        elif service == '700' and operator_ref == 'FE':
            service = 'Sandon Park & Ride'
        elif service == '701' and operator_ref == 'FE':
            service = 'Chelmsford Park & Ride'

        services = Service.objects.filter(line_name__iexact=service, current=True)
        if operator_options:
            services = services.filter(operator__in=operator_options)
        elif operator:
            services = services.filter(operator=operator)
        else:
            return journey, vehicle_created

        try:
            journey.service = self.get_service(services, get_latlong(mvj))
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            if operator_ref != 'OFJ':
                logger.error(e, exc_info=True)
                print(e, operator_ref, service, services, get_latlong(mvj))

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
