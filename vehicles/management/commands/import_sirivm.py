from ciso8601 import parse_datetime
from requests.exceptions import RequestException
from busstops.models import DataSource
from .import_bod_avl import Command as BaseCommand


class Command(BaseCommand):
    source_name = 'sirivm'
    url = 'sslink/SSLinkHTTP'

    def get_response(self, url, xml):
        try:
            return self.session.post(url, data=xml, timeout=10)
        except RequestException as e:
            print(e)
            return

    def get_items(self):
        now = self.source.datetime

        for source in DataSource.objects.filter(name__in=('Gatwick SIRI', 'Essex SIRI')):
            if source.settings and source.settings['RequestorRef']:
                requestor_ref = source.settings['RequestorRef']
                requestor_ref = f'<RequestorRef>{requestor_ref}</RequestorRef>'
            else:
                requestor_ref = ''
            data = f"""<Siri xmlns="http://www.siri.org.uk/siri">
<ServiceRequest>{requestor_ref}<VehicleMonitoringRequest/></ServiceRequest>
</Siri>"""
            response = self.get_response(source.url, data)
            if response and response.text:
                source.datetime = now
                self.source = source
                data = self.items_from_response(response.content)

                self.source.datetime = parse_datetime(data['Siri']['ServiceDelivery']['ResponseTimestamp'])

                for item in data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']:
                    yield item
