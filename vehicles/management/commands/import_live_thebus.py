import pytz
import xml.etree.cElementTree as ET
from io import StringIO
from datetime import datetime
from django.contrib.gis.geos import Point
from django.conf import settings
from django.utils import timezone
from ..import_live_vehicles import ImportLiveVehiclesCommand
from busstops.models import Service
from ...models import VehicleLocation, VehicleJourney


hawaii_timezone = pytz.timezone('US/Hawaii')


class Command(ImportLiveVehiclesCommand):
    source_name = 'TheBus'
    url = 'http://api.thebus.org/vehicle/'

    @staticmethod
    def get_datetime(item):
        last_message = datetime.strptime(item.find('last_message').text, '%m/%d/%Y %I:%M:%S %p')
        return timezone.make_aware(last_message, hawaii_timezone)

    def get_items(self):
        response = self.session.get(self.url, params={'key': settings.THEBUS_KEY})
        if response.ok:
            try:
                text = response.text.replace(' & ', ' &amp; ')
                iterator = ET.iterparse(StringIO(text))
                for _, element in iterator:
                    if element.tag == 'vehicle':
                        yield element
                        element.clear()
            except ET.ParseError as e:
                print(e)
                return

    def get_vehicle(self, item):
        vehicle = item.find('number').text
        return self.vehicles.get_or_create(source=self.source, code=vehicle, operator_id='thebus')

    def get_journey(self, item, vehicle):
        journey = VehicleJourney()

        route_name = item.find('route_short_name').text
        if route_name != 'null':
            journey.route_name = route_name
            try:
                journey.service = Service.objects.get(line_name=route_name, region_id='HI', current=True)
            except (Service.MultipleObjectsReturned, Service.DoesNotExist):
                pass

        destination = item.find('headsign').text
        if destination != 'null':
            journey.destination = destination

        return journey

    def create_vehicle_location(self, item):
        lon = item.find('longitude').text
        lat = item.find('latitude').text
        return VehicleLocation(
            latlong=Point(float(lon), float(lat))
        )
