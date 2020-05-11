import requests
# import uuid
import xml.etree.cElementTree as ET
from base64 import b64encode
from django.core.management.base import BaseCommand
from busstops.models import DataSource
from ...models import Disruption


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('app_id', type=str)
        parser.add_argument('app_key', type=str)

    def handle_item(self, item, source):
        # situation_number = item.find('SituationNumber').text
        xml = ET.tostring(item).decode()

        try:
            disruption = Disruption.objects.get(text=xml)
            # disruption.save(update_fields=['text'])
        except Disruption.DoesNotExist:
            disruption = Disruption.objects.create(text=xml, source=source)

        print(disruption)

        for thing in item:
            print(thing.tag, thing.text)

    def fetch(self, app_id, app_key):
        url = 'http://api.transportforthenorth.com/siri/sx'

        source, _ = DataSource.objects.get_or_create(name='Transport for the North', url=url)
        authorization = b64encode(f'{app_id}:{app_key}'.encode()).decode()
        print(authorization)

        response = requests.post(
            url,
            data=f"""<?xml version="1.0" encoding="UTF-8"?>
<Siri xmlns="http://www.siri.org.uk/siri" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="2.0"
xsi:schemaLocation="http://www.siri.org.uk/siri http://www.siri.org.uk/schema/2.0/xsd/siri.xsd">
    <ServiceRequest>
        <RequestorRef>{app_id}</RequestorRef>
        <SituationExchangeRequest version="2.0">
        </SituationExchangeRequest>
    </ServiceRequest>
</Siri>""",
            headers={
                'Authorization': f'Basic {authorization}',
                'Content-Type': 'application/xml'
            },
            stream=True
        )

        for _, element in ET.iterparse(response.raw):
            if element.tag[:29] == '{http://www.siri.org.uk/siri}':
                element.tag = element.tag[29:]

            if element.tag.endswith('PtSituationElement'):
                self.handle_item(element, source)
                element.clear()

    # def subscribe(self):
    #     subscription_id = str(uuid.uuid4())
    #     print(subscription_id)
    #     callback_url = 'http://bustimes.org/siri'
    #     foo = requests.post(
    #         'http://dm-api-tfn.transportapi.com/subscriptions.xml',
    #         headers={
    #             'subscription_id': subscription_id,
    #             'callback_url': callback_url
    #         }
    #     )
    #     print(foo)
    #     print(foo.text)
    #     print(foo.headers)

    # def unsubscribe(self):
    #     subscription_id = 'd2e75ab4-9389-4682-9740-bd6f5b985268'
    #     foo = requests.delete(
    #         'http://dm-api-tfn.transportapi.com/subscriptions.xml',
    #         headers={
    #             'subscription_id': subscription_id,
    #         }
    #     )
    #     print(foo)
    #     print(foo.text)
    #     print(foo.headers)

    def handle(self, app_id, app_key, *args, **options):
        self.fetch(app_id, app_key)

        # self.subscribe()
        # self.unsubscribe()
