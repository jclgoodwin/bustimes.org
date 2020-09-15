import requests
import xml.etree.cElementTree as ET
from ciso8601 import parse_datetime
from base64 import b64encode
from django.core.management.base import BaseCommand
from psycopg2.extras import DateTimeTZRange
from busstops.models import DataSource, Service
from ...models import Situation, Consequence, ValidityPeriod, Link


def get_period(element):
    start = element.find('StartTime').text
    end = element.find('EndTime')
    if end is not None:
        end = end.text
    return DateTimeTZRange(start, end, '[]')


def handle_item(item, source):
    situation_number = item.find('SituationNumber').text
    xml = ET.tostring(item).decode()

    created_time = parse_datetime(item.find('CreationTime').text)

    try:
        situation = Situation.objects.get(source=source, situation_number=situation_number)
        if situation.data == xml:
            return situation.id
        created = False
    except Situation.DoesNotExist:
        situation = Situation(source=source, situation_number=situation_number)
        created = True
    situation.data = xml
    situation.created = created_time
    situation.publication_window = get_period(item.find('PublicationWindow'))
    situation.current = item.find('Progress').text == 'open'

    reason = item.find('MiscellaneousReason')
    if reason is not None:
        situation.reason = reason.text

    situation.summary = item.find('Summary').text
    situation.text = item.find('Description').text
    situation.save()

    for i, link_element in enumerate(item.findall('InfoLinks/InfoLink/Uri')):
        link = Link(situation=situation)
        if not created and i == 0:
            try:
                link = situation.link_set.get()
            except Link.MultipleObjectsReturned:
                situation.link_set.all().delete()
            except Link.DoesNotExist:
                pass
        if link_element.text:
            link.url = link_element.text
            link.save()

    for i, period_element in enumerate(item.findall('ValidityPeriod')):
        period = ValidityPeriod(situation=situation)
        if not created and i == 0:
            try:
                period = situation.validityperiod_set.get()
            except ValidityPeriod.MultipleObjectsReturned:
                situation.validityperiod_set.all().delete()
            except ValidityPeriod.DoesNotExist:
                pass
        period.period = get_period(period_element)
        period.save()

    for i, consequence_element in enumerate(item.find('Consequences')):
        consequence = Consequence(situation=situation)
        if not created and i == 0:
            try:
                consequence = situation.consequence_set.get()
            except Consequence.MultipleObjectsReturned:
                situation.consequence_set.all().delete()
            except Consequence.DoesNotExist:
                pass

        consequence.text = consequence_element.find('Advice/Details').text
        consequence.data = ET.tostring(consequence_element).decode()
        consequence.save()

        for line in consequence_element.findall('Affects/Networks/AffectedNetwork/AffectedLine'):
            line_name = line.find('PublishedLineName')
            if line_name is None:
                line_name = line.find('LineRef')
            line_name = line_name.text
            for operator in line.findall('AffectedOperator'):
                operator_ref = operator.find('OperatorRef').text
                services = Service.objects.filter(current=True, line_name__iexact=line_name, operator=operator_ref)
                for service in services:
                    consequence.services.add(service)
                    service.varnish_ban()

        stops = consequence_element.findall('Affects/StopPoints/AffectedStopPoint')
        stops = [stop.find('StopPointRef').text for stop in stops]
        consequence.stops.set(stops)

    return situation.id


class Command(BaseCommand):
    def fetch(self):
        url = 'http://api.transportforthenorth.com/siri/sx'

        source = DataSource.objects.get(name='Transport for the North')
        app_id = source.settings['app_id']
        app_key = source.settings['app_key']
        authorization = b64encode(f'{app_id}:{app_key}'.encode()).decode()

        situations = []

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
                situations.append(handle_item(element, source))
                element.clear()

        Situation.objects.filter(source=source, current=True).exclude(id__in=situations).update(current=False)

    def handle(self, *args, **options):
        self.fetch()
