import ciso8601
import logging
import xml.etree.cElementTree as ET
from io import StringIO
from requests.exceptions import RequestException
from django.contrib.gis.geos import Point
from django.db.models import Q
from isodate import parse_duration
from busstops.models import Operator, Service, Locality, DataSource
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

    operators_options = {
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
        'ATS': ('ARBB', 'GLAR'),
        'ASC': ('ARHE', 'GLAR'),
        'NXB': ('TNXB', 'TCVW'),
    }
    operators = {}

    @staticmethod
    def get_datetime(item):
        datetime = item.find('siri:RecordedAtTime', NS).text
        return ciso8601.parse_datetime(datetime)

    def get_response(self, url, xml):
        try:
            return self.session.post(url, data=xml, timeout=10)
        except RequestException as e:
            print(e)
            return

    def get_items(self):
        now = self.source.datetime

        url = 'http://{}.jmwrti.co.uk:8080/RTI-SIRI-Server/SIRIHandler'
        data = """<Siri xmlns="http://www.siri.org.uk/siri">
<ServiceRequest><VehicleMonitoringRequest/></ServiceRequest>
</Siri>"""
        for subdomain in ('essex', 'southampton', 'slough', 'staffordshire'):
            response = self.get_response(url.format(subdomain), data)
            if response and response.text:
                self.source, _ = DataSource.objects.update_or_create(
                    {'url': response.url, 'datetime': now},
                    name=subdomain.title() + ' SIRI'
                )
                for item in items_from_response(response):
                    yield item

        url = 'http://data.icarus.cloudamber.com/VehicleMonitoringRequest.ashx'
        data = """<Siri xmlns="http://www.siri.org.uk/siri">
<ServiceRequest><RequestorRef>{}</RequestorRef><VehicleMonitoringRequest/>
</ServiceRequest>
</Siri>"""
        requestor_ref = 'gatwick_app'
        response = self.get_response(url, data.format(requestor_ref))
        if response and response.text:
            self.source, _ = DataSource.objects.update_or_create(
                {'url': response.url, 'datetime': now},
                name='Gatwick SIRI'
            )
            for item in items_from_response(response):
                yield item

    def get_operator(self, operator_ref):
        operator_options = self.operators_options.get(operator_ref)
        if operator_ref in self.operators:
            return self.operators[operator_ref], operator_options
        if operator_options:
            operator = Operator.objects.get(id=operator_options[0])
        else:
            try:
                try:
                    operator = Operator.objects.get(operatorcode__source=self.source,
                                                    operatorcode__code=operator_ref)
                except (Operator.MultipleObjectsReturned, Operator.DoesNotExist):
                    operator = Operator.objects.get(id=operator_ref)
            except (Operator.MultipleObjectsReturned, Operator.DoesNotExist) as e:
                logger.error(e, exc_info=True)
                operator = None
        if operator:
            self.operators[operator_ref] = operator
        return operator, operator_options

    def get_vehicle(self, item):
        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        vehicle_code = mvj.find('siri:VehicleRef', NS).text
        operator_ref = mvj.find('siri:OperatorRef', NS).text
        while operator_ref and vehicle_code.startswith(operator_ref + '-'):
            if operator_ref == 'SQ' and not vehicle_code.startswith('SQ-SQ-') or operator_ref == 'CSLB':
                break
            vehicle_code = vehicle_code[len(operator_ref) + 1:]

        operator, operator_options = self.get_operator(operator_ref)

        if operator:
            if operator.id == 'THVB' or operator.id == 'RBUS' or operator.id == 'CTNY':
                operator_options = ('RBUS', 'CTNY')
                if operator.id == 'THVB':
                    operator = Operator.objects.get(id='RBUS')
            elif operator.id == 'SESX':
                operator_options = ('SESX', 'NIBS', 'GECL')
            elif operator.id == 'FBRI':
                if len(vehicle_code) < 4:
                    return None, None
                if not (vehicle_code.isdigit() or vehicle_code.isalpha()) and vehicle_code.isupper():
                    operator_options = ('ABUS',)
            elif operator_ref == 'AMD' or operator_ref == 'AMN':
                # Arriva Midlands and Midlands North share fleet numbering scheme, but are distinct codes for routes
                operator_options = ('AMNO', 'AMID', 'AFCL')

        defaults = {
            'source': self.source,
            'operator': operator
        }
        if vehicle_code.isdigit():
            defaults['fleet_number'] = vehicle_code
            if operator_ref == 'ATS' and int(vehicle_code) > 8000:
                return None, None
        elif '-' in vehicle_code:
            parts = vehicle_code.split('-')
            if len(parts) == 2 and parts[0].isalpha() and parts[0].isupper() and parts[1].isdigit():
                defaults['fleet_number'] = parts[1]

            if parts[0] == 'GOEA' or parts[0] == 'CSLB':
                return self.vehicles.get_or_create(
                    defaults,
                    code=vehicle_code,
                )

        if not operator_options:
            operator_options = (operator,)
        try:
            if operator and operator.name.startswith('Stagecoach '):
                if '-' in vehicle_code:
                    vehicle_code = vehicle_code.split('-', 1)[-1]
                    if vehicle_code.isdigit():
                        defaults['fleet_number'] = vehicle_code
                return self.vehicles.get_or_create(
                    defaults,
                    operator__name__startswith='Stagecoach ',
                    code=vehicle_code,
                )
            if (operator_ref == 'ATS' or operator_ref == 'AMD') and vehicle_code.isdigit():
                defaults['code'] = vehicle_code
                return self.vehicles.get_or_create(
                    defaults,
                    operator__in=operator_options,
                    fleet_number=vehicle_code,
                )
            return self.vehicles.get_or_create(
                defaults,
                operator__in=operator_options,
                code=vehicle_code,
            )
        except Vehicle.MultipleObjectsReturned as e:
            logger.error(e, exc_info=True)
            return self.vehicles.filter(
                operator__in=operator_options,
                code=vehicle_code
            ).first(), False

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        operator_ref = mvj.find('siri:OperatorRef', NS).text
        service = mvj.find('siri:LineRef', NS).text

        journey_code = mvj.find('siri:FramedVehicleJourneyRef/siri:DatedVehicleJourneyRef', NS)
        if journey_code is not None:
            journey.code = journey_code.text

        departure_time = mvj.find('siri:OriginAimedDepartureTime', NS)
        if departure_time is not None:
            journey.datetime = ciso8601.parse_datetime(departure_time.text)

        if service is None and operator_ref == 'TG':
            service = 'Colchester Park & Ride'

        if service:
            journey.route_name = service

        if vehicle.latest_location and vehicle.latest_location.journey.code == journey.code and (
                                       vehicle.latest_location.journey.route_name == journey.route_name
        ):

            journey.service = vehicle.latest_location.journey.service
            if vehicle.latest_location.journey.destination:
                journey.destination = vehicle.latest_location.journey.destination
            return journey

        destination_ref = mvj.find('siri:DestinationRef', NS)
        if destination_ref is not None:
            destination_ref = destination_ref.text

        if destination_ref:
            try:
                journey.destination = Locality.objects.get(stoppoint=destination_ref).name
            except Locality.DoesNotExist:
                pass
        if not journey.destination:
            destination_name = mvj.find('siri:DestinationName', NS)
            if destination_name is not None:
                journey.destination = destination_name.text

        services = Service.objects.filter(current=True)
        services = services.filter(Q(line_name__iexact=service) | Q(servicecode__scheme__endswith=' SIRI',
                                                                    servicecode__code=service))

        operator, operator_options = self.get_operator(operator_ref)
        if operator_options:
            services = services.filter(operator__in=operator_options).distinct()
        elif operator:
            services = services.filter(operator=operator)
        else:
            return journey

        latlong = get_latlong(mvj)

        if operator_ref != 'OFJ':  # not a Gatwick Airport shuttle

            try:
                journey.service = self.get_service(services, latlong)
            except Service.DoesNotExist:
                pass

            if not journey.service:
                origin_ref = mvj.find('siri:OriginRef', NS)
                destination_ref = mvj.find('siri:DestinationRef', NS)
                if origin_ref is not None:
                    origin_ref = origin_ref.text
                if destination_ref is not None:
                    destination_ref = destination_ref.text

                if origin_ref and destination_ref:
                    for queryset in (
                        services.filter(stops=origin_ref).filter(route__trip__destination=destination_ref),
                        services.filter(stops=origin_ref).filter(stops=destination_ref),
                        services.filter(Q(stops=origin_ref) | Q(stops=destination_ref)),
                    ):
                        if queryset.exists():
                            services = queryset.distinct()
                            break
                try:
                    journey.service = self.get_service(services, latlong)
                    if not journey.service:
                        journey.service = services.first()
                except Service.DoesNotExist as e:
                    print(e, operator, service)

        if not journey.destination and journey.code and journey.service:
            try:
                journey_code = journey.service.journeycode_set.get(code=journey.code)
                journey.destination = journey_code.destination
            except (JourneyCode.DoesNotExist, JourneyCode.MultipleObjectsReturned):
                pass

        if operator_options and operator and journey.service and operator.id == operator_options[0]:
            if operator.id not in {'RBUS', 'ARBB', 'ARHE'}:
                try:
                    operator = journey.service.operator.get()
                    vehicle.maybe_change_operator(operator)
                except (Operator.MultipleObjectsReturned, Operator.DoesNotExist):
                    pass

        return journey

    def create_vehicle_location(self, item):
        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        latlong = get_latlong(mvj)
        heading = mvj.find('siri:Bearing', NS)
        if heading is not None:
            heading = int(heading.text)
            if heading == -1 or heading == 0:
                heading = None
            elif heading == 0:
                operator_ref = mvj.find('siri:OperatorRef', NS).text
                if operator_ref == 'ATS':
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
            latlong=latlong,
            heading=heading,
            early=early
        )
