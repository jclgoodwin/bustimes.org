import requests
import xml.etree.cElementTree as ET
from requests_toolbelt.adapters.source import SourceAddressAdapter
from django.core.management.base import BaseCommand
# from busstops.models import DataSource


class Command(BaseCommand):
    def fetch(self):
        url = "https://siri-sx-tfn.itoworld.com"
        requestor_ref = "BusTimes"

        # Access to the subscription endpoint is restricted to certain IP addresses,
        # so use a Digital Ocean floating IP address
        self.session.mount('http://', SourceAddressAdapter('10.16.0.7'))

        # source = DataSource.objects.get(name="Ito World")
        # app_id = source.settings['app_id']
        # app_key = source.settings['app_key']
        # authorization = b64encode(f'{app_id}:{app_key}'.encode()).decode()

        # situations = []

        response = requests.get(url)
        print(response.text)

        response = requests.post(
            url,
            data=f"""<?xml version="1.0" encoding="UTF-8"?>
<Siri xmlns="http://www.siri.org.uk/siri" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.0"
xsi:schemaLocation="http://www.siri.org.uk/siri http://www.siri.org.uk/schema/2.0/xsd/siri.xsd">
    <ServiceRequest>
        <RequestorRef>{requestor_ref}</RequestorRef>
        <SituationExchangeRequest version="2.0">
        </SituationExchangeRequest>
    </ServiceRequest>
</Siri>""",
            headers={
                # 'Authorization': f'Basic {authorization}',
                'Content-Type': 'application/xml'
            },
            stream=True
        )

        print(response.content.decode())

        for _, element in ET.iterparse(response.raw):
            if element.tag[:29] == '{http://www.siri.org.uk/siri}':
                element.tag = element.tag[29:]

            if element.tag.endswith('PtSituationElement'):
                print(ET.tostring(element).decode())
                # situations.append(handle_item(element, source))
                element.clear()

        # Situation.objects.filter(source=source, current=True).exclude(id__in=situations).update(current=False)

    def handle(self, *args, **options):
        self.fetch()
