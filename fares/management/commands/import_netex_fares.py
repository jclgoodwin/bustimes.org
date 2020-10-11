import os
import xmltodict
from django.core.management.base import BaseCommand
from ...models import FareZone


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_atco_code(stop):
    ref = stop['@ref']
    assert ref.startswith('atco:')
    return ref[5:]


def handle_zone(data):
    zone, created = FareZone.objects.get_or_create(name=data['Name'])
    stops = data['members']['ScheduledStopPointRef']
    if type(stops) is list:
        zone.stops.set([get_atco_code(stop) for stop in stops])
    else:
        zone.stops.set([get_atco_code(stops)])


class Command(BaseCommand):
    def handle(self, **kwargs):
        path = 'connexions_Harrogate_Coa_16.286Z_IOpbaMX.xml'
        path = os.path.join(BASE_DIR, path)

        with open(path, 'rb') as open_file:
            data = xmltodict.parse(open_file)
            for composite_frame in data['PublicationDelivery']['dataObjects']['CompositeFrame']:
                if composite_frame['@responsibilitySetRef'] == 'tariffs':
                    # print(composite_frame['Name'])
                    # print(composite_frame['Description'])
                    # print(composite_frame['ValidBetween'])
                    # print(composite_frame['frames']['ResourceFrame'])
                    # print(composite_frame['frames']['SiteFrame'])
                    for frame in composite_frame['frames']['FareFrame']:
                        if 'fareZones' in frame:
                            for zone in frame['fareZones']['FareZone']:
                                handle_zone(zone)
