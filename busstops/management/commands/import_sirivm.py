import pytz
import ciso8601
import xml.etree.cElementTree as ET
from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, Operator, Service


LOCAL_TIMEZONE = pytz.timezone('Europe/London')
NS = {'siri': 'http://www.siri.org.uk/siri'}


def get_latlong(mvj):
    vl = mvj.find('siri:VehicleLocation', NS)
    lat = vl.find('siri:Latitude', NS).text
    long = vl.find('siri:Longitude', NS).text
    return Point(float(long), float(lat))


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
        'SQ': ('BLUS', 'SVCT', 'UNIL', 'SWWD', 'DAMY', 'TDTR', 'TOUR'),
        'FH': ('FHAM',),
        'RL': ('RLNE',),
        'FT': ('FTVA',),
    }

    def get_items(self):
        for subdomain in ('essex', 'southampton', 'slough'):
            data = """
                <Siri xmlns="http://www.siri.org.uk/siri">
                    <ServiceRequest><VehicleMonitoringRequest/></ServiceRequest>
                </Siri>
            """
            response = self.session.post('http://{}.jmwrti.co.uk:8080/RTI-SIRI-Server/SIRIHandler'.format(subdomain),
                                         data=data)
            items = ET.fromstring(response.text)
            items = items.findall('siri:ServiceDelivery/siri:VehicleMonitoringDelivery/siri:VehicleActivity', NS)
            for item in items:
                yield item

    def get_vehicle_and_service(self, item):
        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        operator_ref = mvj.find('siri:OperatorRef', NS).text
        operator = None

        try:
            operator_options = self.operators.get(operator_ref)
            if operator_options:
                operator = Operator.objects.get(id=operator_options[0])
            else:
                print(operator_ref)
        except (Operator.MultipleObjectsReturned, Operator.DoesNotExist) as e:
            print(operator, e)
        vehicle, created = Vehicle.objects.update_or_create(
            {'operator': operator},
            source=self.source,
            code=mvj.find('siri:VehicleRef', NS).text
        )

        service = mvj.find('siri:LineRef', NS).text
        if service == 'QC':
            service = 'QuayConnect'
        if operator_options:
            try:
                services = Service.objects.filter(operator__in=operator_options, line_name=service, current=True)
                if services.count() > 1:
                    latlong = get_latlong(mvj)
                    services = services.filter(geometry__bbcontains=latlong)
                service = services.get()
            except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
                print(operator_options, service, e)
                service = None
            if service and vehicle.operator != service.operator.first():
                vehicle.operator = service.operator.first()
                vehicle.save()
        else:
            service = None

        return vehicle, created, service

    def create_vehicle_location(self, item, vehicle, service):
        datetime = item.find('siri:RecordedAtTime', NS).text
        mvj = item.find('siri:MonitoredVehicleJourney', NS)
        latlong = get_latlong(mvj)
        heading = mvj.find('siri:Bearing', NS)
        if heading is not None:
            heading = heading.text
        return VehicleLocation(
            datetime=ciso8601.parse_datetime(datetime),
            latlong=latlong,
            heading=heading
            # early=item.find('siri:MonitoredVehicleJourney/siri:Delay', NS)
        )
