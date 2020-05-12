import requests
# import uuid
import xml.etree.cElementTree as ET
from base64 import b64encode
from django.core.management.base import BaseCommand
from psycopg2.extras import DateTimeTZRange
from busstops.models import DataSource
from ...models import Situation


def get_period(element):
    start = element.find('StartTime').text
    end = element.find('EndTime')
    if end is not None:
        end = end.text
    return DateTimeTZRange(start, end, '[]')


def handle_item(item, source):
    situation_number = item.find('SituationNumber').text
    xml = ET.tostring(item).decode()

    # print(xml)

    try:
        situation = Situation.objects.get(source=source, situation_number=situation_number)
    except Situation.DoesNotExist:
        situation = Situation(
            source=source,
            situation_number=situation_number,
            data=xml,
            created=item.find('CreationTime').text,
            publication_window=get_period(item.find('PublicationWindow')),
            validity_period=get_period(item.find('ValidityPeriod')),
        )

    reason = item.find('MiscellaneousReason')
    if reason is not None:
        situation.reason = reason.text

    situation.summary = item.find('Summary').text
    situation.text = item.find('Description').text
    print(situation.summary)

    situation.save()

    # # print(situation)

    # for thing in item:
    #     print(thing.tag, thing.text)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('app_id', type=str)
        parser.add_argument('app_key', type=str)

    def fetch(self, app_id, app_key):
        url = 'http://api.transportforthenorth.com/siri/sx'

        source, _ = DataSource.objects.get_or_create(name='Transport for the North', url=url)
        authorization = b64encode(f'{app_id}:{app_key}'.encode()).decode()

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
                handle_item(element, source)
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
