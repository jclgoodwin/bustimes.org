import xml.etree.cElementTree as ET
from django.contrib.gis.geos import Point
from ..import_live_vehicles import ImportLiveVehiclesCommand
from ...models import Vehicle, VehicleLocation, VehicleJourney, Service


NS = {
    'a': 'http://www.acishorizon.com/',
    's': 'http://www.w3.org/2003/05/soap-envelope'
}


def items_from_response(response):
    try:
        items = ET.fromstring(response.text)
    except ET.ParseError:
        print(response)
        return ()
    return items.findall(
        's:Body/a:GetVehiclesNearPointResponse/a:GetVehiclesNearPointResult/a:Vehicles/a:VehicleRealtime',
        NS
    )


class Command(ImportLiveVehiclesCommand):
    source_name = 'acis'
    url = 'http://belfastapp.acishorizon.com/DataService.asmx'

    def get_response(self, lat=None, lon=None):
        if lat and lon:
            latlong = '<latitude>{}</latitude><longitude>{}</longitude>'.format(lat, lon)
        else:
            latlong = ''
        data = """
            <soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
                <soap12:Body>
                    <GetVehiclesNearPoint xmlns="http://www.acishorizon.com/">
                        {}
                        <maxResults>100</maxResults>
                    </GetVehiclesNearPoint>
                </soap12:Body>
            </soap12:Envelope>
        """.format(latlong)
        return self.session.post(self.url, data=data, timeout=5, headers={'content-type': 'application/soap+xml'})

    def get_items(self):
        for item in items_from_response(self.get_response()):
            yield item
        for item in items_from_response(self.get_response(-5.9169, 54.5957)):
            yield item

    def get_journey(self, item):
        journey = VehicleJourney()

        journey.code = item.find('a:VehicleJourneyId', NS).text
        journey.destination = item.find('a:VehicleDestination', NS).text

        service = item.find('a:VehiclePublicServiceCode', NS).text
        vehicle = item.find('a:VehicleId', NS).text
        operator = item.find('a:VehicleOperatorName', NS).text

        if operator == 'Translink Glider':
            operator = 'GDR'
        else:
            operator = 'MET'

        try:
            try:
                journey.service = Service.objects.get(line_name__iexact=service, operator=operator)
            except Service.DoesNotExist:
                operator = 'ULB'
                service = Service.objects.get(line_name__iexact=service, operator=operator)
        except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
            print(e, service)

        journey.vehicle, vehicle_created = Vehicle.objects.get_or_create(operator_id=operator, code=vehicle,
                                                                         source=self.source)

        return journey, vehicle_created

    def create_vehicle_location(self, item):
        lat = item.find('a:VehicleLatitude', NS).text
        lon = item.find('a:VehicleLongitude', NS).text
        latlong = Point(float(lon), float(lat))
        return VehicleLocation(
            latlong=latlong,
        )
