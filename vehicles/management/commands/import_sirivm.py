import ciso8601
import xml.etree.cElementTree as ET
from django.contrib.gis.geos import Point
from busstops.models import Operator, Service
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney


NS = {'siri': 'http://www.siri.org.uk/siri'}


def get_latlong(mvj):
    vl = mvj.find('siri:VehicleLocation', NS)
    lat = vl.find('siri:Latitude', NS).text
    lon = vl.find('siri:Longitude', NS).text
    return Point(float(lon), float(lat))


def items_from_response(response):
    try:
        items = ET.fromstring(response.text)
    except ET.ParseError:
        print(response)
        return ()
    return items.findall('siri:ServiceDelivery/siri:VehicleMonitoringDelivery/siri:VehicleActivity', NS)


class Command(ImportLiveVehiclesCommand):
    source_name = 'sirivm'
    url = 'sslink/SSLinkHTTP'

    operators = {
        'ENS': ('ENSB',),
        'HO': ('HEDO',),
        'SE': ('SESX',),
        'SE': ('SESX',),
        'FE': ('FESX',),
        'AKE': ('ARHE',),
        'SQ': ('BLUS', 'SVCT', 'UNIL', 'SWWD', 'DAMY', 'TDTR', 'TOUR', 'WDBC'),
        'FH': ('FHAM',),
        'RL': ('RLNE',),
        'FT': ('FTVA',),
        'FD': ('FDOR',),
        'RB': ('RBUS', 'GLRB'),
        'TV': ('THVB',),
    }

    def get_items(self):
        for subdomain in ('essex', 'southampton', 'slough'):
            data = """
                <Siri xmlns="http://www.siri.org.uk/siri">
                    <ServiceRequest><VehicleMonitoringRequest/></ServiceRequest>
                </Siri>
            """
            response = self.session.post('http://{}.jmwrti.co.uk:8080/RTI-SIRI-Server/SIRIHandler'.format(subdomain),
                                         data=data, timeout=10)
            for item in items_from_response(response):
                yield item

        data = """
            <Siri xmlns="http://www.siri.org.uk/siri">
                <ServiceRequest>
                    <RequestorRef>torbaydevon_siri_traveline</RequestorRef>
                    <VehicleMonitoringRequest/>
                </ServiceRequest>
            </Siri>
        """
        response = self.session.post('http://data.icarus.cloudamber.com/VehicleMonitoringRequest.ashx',
                                     data=data, timeout=10)
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
                    operator = Operator.objects.get(id=operator_ref)
        except (Operator.MultipleObjectsReturned, Operator.DoesNotExist) as e:
            print(e, operator_ref, service)

        vehicle_code = mvj.find('siri:VehicleRef', NS).text
        if operator_ref and vehicle_code.startswith(operator_ref + '-'):
            vehicle_code = vehicle_code[len(operator_ref) + 1:]

        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(
            {
                'source': self.source
            },
            operator=operator,
            code=vehicle_code,
        )

        # TODO: use ServiceCodes for this
        if service == 'QC':
            service = 'QuayConnect'
        elif service == 'FLCN':
            service = 'FALCON'
        elif service == 'P&R' and operator_ref == 'AKE':
            service = 'Colchester Park & Ride'
        elif service == '700' and operator_ref == 'FE':
            service = 'Sandon Park & Ride'
        elif service == '701' and operator_ref == 'FE':
            service = 'Chelmsford Park & Ride'
        elif service and service[:3] == 'BOB':
            service = service[:3] + ' ' + service[3] + ' ' + service[4:]

        services = Service.objects.filter(line_name__iexact=service, current=True)
        if operator_options:
            services = services.filter(operator__in=operator_options)
        elif operator:
            services = services.filter(operator=operator)
        else:
            return journey, vehicle_created

        if services.count() > 1:
            latlong = get_latlong(mvj)
            services = services.filter(geometry__bboverlaps=latlong.buffer(0.1))

        try:
            journey.service = services.get()
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, operator_ref, service, services, get_latlong(mvj))

        return journey, vehicle_created

    def create_vehicle_location(self, item, vehicle, service):
        datetime = item.find('siri:RecordedAtTime', NS).text
        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        latlong = get_latlong(mvj)
        heading = mvj.find('siri:Bearing', NS)
        if heading is not None:
            heading = int(heading.text)
            if heading == -1:
                heading = None
        return VehicleLocation(
            datetime=ciso8601.parse_datetime(datetime),
            latlong=latlong,
            heading=heading,
        )
