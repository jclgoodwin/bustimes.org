"""
Command for importing transport services.

So far, all services in the SE, EA, Y and NCSD regions can be imported without
known errors.

Usage:

    ./manage.py import_services EA.zip [EM.zip etc]
"""

import os
import zipfile
import csv
import pickle
import xml.etree.cElementTree as ET

from django.contrib.gis.geos import LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import transaction

from txc.txc import Timetable, sanitize_description_part
from ...models import Operator, StopPoint, Service, StopUsage


DIR = os.path.dirname(os.path.realpath(__file__))

# map names to operator IDs where there is no correspondence between the NOC DB and TNDS:
SPECIAL_OPERATOR_TRADINGNAMES = {
    'Arriva Northumbria': 'ANUM',
    'Southwold Town Council': 'SWTC',
    'H.C.Chambers & Son': 'CHMB',
    'Bungay and Beccles Area CT': 'BBCT',
    'Stowmarket Minibus & Coach Hire': 'MBCH',
    'Harwich Harbour Ferry': 'HHFS',
    'Halesworth Area Community Transport': 'HACT',
    'Dartmouth Steam Railway And River Boat Company': 'DRMR',
    'Borderbus': 'BDRB',
    'ARRIVA LONDON NORTH LIMITED': 'ALNO',
    'ARRIVA LONDON SOUTH LIMITED': 'ALSO',
    'ARRIVA THE SHIRES LIMITED': 'ASES',
    'ARRIVA KENT THAMESIDE LIMITED': 'AMTM',
    'METROBUS LIMITED': 'METR',
    'EAST LONDON BUS & COACH COMPANY LIMITED': 'ELBG',
    'SOUTH EAST LONDON & KENT BUS COMPANY LTD': 'SELK',
    'TRAMTRACK CROYDON LTD': 'TRAM',
    'Westminster Passenger Service Association': 'WPSA',
    'First Cornwall': 'FCWL',
    'IoW Floating Bridge': 'IOWC',
    'Ladies Only Travel': 'YLOT',
    'LONDON SOVEREIGN LIMITED': 'LSOV',
    'ABELLIO LONDON LIMITED': 'ABLO',
    'ABELLIO LONDON (WEST) LIMITED': 'ABLO',
    'TOWER TRANSIT LIMITED': 'TOTR',
    'UNO BUSES LIMITED': 'UNOE',
    'C T PLUS LIMITED': 'NCTP',
    'Gloucestershire': 'SCGL',
    'BLUE TRIANGLE BUSES LIMITED': 'BTRI',
    'METROLINE WEST LIMITED': 'MTLN',
    'LONDON CENTRAL BUS COMPANY LIMITED': 'LONC',
    'SULLIVAN BUS & COACH LIMITED': 'SULV',
    'Notts & Derby': 'NDTR',
    'LIVERPOOL CITY SIGHTS': 'CISI',
    'WDC': 'WDCB',  # Western Dales Community Bus
    'Rothbury Securities Ltd': 'ROTH',
    'KL': 'KELC',  # Keswick Launch Company
    'Carters Heritage Buses': 'CTCS',
    'King Harry Ferry Co': 'KHFC',
    'Fal River Ferries': 'KHFC',
    'KPMG THAMES CLIPPERS': 'NTHC',
    'Stagecoach on Teesside': 'SCNW'
}
# map OperatorCodes to operator IDs (ditto, where there is no TradingName):
SPECIAL_OPERATOR_CODES = {
    'HIB': 'HIMB',  # Holy Island Minibus
    '1866': 'BPTR',  # Burnley & Pendle
    '2152': 'RSTY',  # R S Tyrer & Sons
    '2916': 'SPCT',  # South Pennine Community Transport
    'RB1': 'RBRO',  # Richards Bros
    'ACY': 'ACYM',  # Arriva Cymru/Wales
    'AM0': 'AMID',  # Arriva Midlands
    'RMB': 'RMBL',  # Routemaster Buses Ltd
    'JO1': 'JTMT',  # John's Travel (Merthyr Tydfil)
    'CO': 'CFSV',  # Coniston Launch/Ferry
    'CL': 'CFSV',  # Coniston Launch/Ferry
    'SGI': 'SGIL',  # Steel Group Investments Limited
    'EYM': 'EYMS',  # East Yorkshire Motor Services
    'WINF': 'WMLC',  # Windermere Lake Cruises/Ferry
    'DPC': 'DPCE',  # (Don) Prentice (Coaches)
    'PCV': 'PCVN',  # (Peter) Canavan (Travel)
    'RGJ': 'RGJS',  # R G Jamieson & Son
    'DAM': 'DAMC',  # D A & A J MacLean
    'ADD': 'ADDI',  # Addison News/of Callendar
    'HBSY': 'YTIG',  # Huddersfield Bus Company/Yorkshire Tiger
    'ALI': 'AMDD',   # Alasdair MacDonald
    'EWE': 'EWEN',   # Ewens Coach Hire
    '712CS': 'CSVC',  # Coach Services
}
# see https://docs.python.org/2/library/xml.etree.elementtree.html#parsing-xml-with-namespaces
NS = {'txc': 'http://www.transxchange.org.uk/'}


class Command(BaseCommand):
    "Command that imports bus services from a zip file"

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('filenames', nargs='+', type=str)

    @staticmethod
    def infer_from_filename(filename):
        """
        Given a filename like 'ea_21-45A-_-y08-1.xml',
        returns a (net, service_code, line_ver) tuple like ('ea', 'ea_21-45A-_-y08', '1')

        Given any other sort of filename, returns ('', None, None)
        """
        parts = filename.split('-')  # ['ea_21', '3', '_', '1']
        if len(parts) == 5:
            net = parts[0].split('_')[0]
            if len(net) <= 3 and net.islower():
                return (net, '-'.join(parts[:-1]), parts[-1][:-4])
        return ('', None, None)

    @staticmethod
    def sanitize_description(name):
        """
        Given an oddly formatted description from the North East,
        like 'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
        returns a shorter, more normal version like
        'Blyth - Widdrington Station'
        """

        parts = [sanitize_description_part(part) for part in name.split(' - ')]
        return ' - '.join(parts)

    @classmethod
    def get_operator_name(cls, operator_element):
        "Given an Operator element, returns the operator name or None"

        for element_name in ('TradingName', 'OperatorNameOnLicence', 'OperatorShortName'):
            element = operator_element.find('txc:%s' % element_name, NS)
            if element is not None and element.text is not None:
                return element.text.replace('&amp;', '&')

    @classmethod
    def get_operator_code(cls, operator_element):
        "Given an Operator element, returns the operator code or None"

        for element_name in ('National', ''):
            element = operator_element.find('txc:%sOperatorCode' % element_name, NS)
            if element is not None:
                return element.text

    @classmethod
    def get_operator(cls, operator_element):
        "Given an Operator element, returns an Operator object."

        # Get by national operator code
        operator_code = cls.get_operator_code(operator_element)
        if len(operator_code) > 2:
            possible_operators = Operator.objects.filter(id=operator_code)
            if possible_operators:
                return possible_operators[0]

        # Get by name
        operator_name = cls.get_operator_name(operator_element)

        if operator_name in ('Replacement Service', 'UNKWN'):
            return None

        if operator_name in SPECIAL_OPERATOR_TRADINGNAMES:
            return Operator.objects.get(id=SPECIAL_OPERATOR_TRADINGNAMES[operator_name])

        if operator_code in SPECIAL_OPERATOR_CODES:
            return Operator.objects.get(id=SPECIAL_OPERATOR_CODES[operator_code])

        if operator_name:
            possible_operators = Operator.objects.filter(name__istartswith=operator_name)
            if len(possible_operators) == 1:
                return possible_operators[0]

        print(ET.tostring(operator_element))

    @classmethod
    def get_line_name_and_brand(cls, service_element, filename):
        """
        Given a Service element and (purely for debugging) a filename
        returns a (line_name, line_brand) tuple
        """
        line_name = service_element.find('txc:Lines', NS)[0][0].text
        if '|' in line_name:
            line_name_parts = line_name.split('|', 1)
            line_name = line_name_parts[0]
            line_brand = line_name_parts[1]
        else:
            line_brand = ''

        if len(line_name) > 64:
            print('Name "%s" is too long in %s' % (line_name, filename))
            line_name = line_name[:64]

        return (line_name, line_brand)

    @staticmethod
    def line_string_from_journeypattern(journeypattern, stops):
        points = []
        stop = stops.get(journeypattern.sections[0].timinglinks[0].origin.stop.atco_code)
        if stop:
            points.append(stop.latlong)
        for section in journeypattern.sections:
            for timinglink in section.timinglinks:
                stop = stops.get(timinglink.destination.stop.atco_code)
                if stop:
                    points.append(stop.latlong)
        try:
            linestring = LineString(points)
            return linestring
        except ValueError as error:
            print(error, points)

    @classmethod
    def do_service(cls, open_file, region_id, filename, service_descriptions=None):
        """
        Given a root element, region ID, filename, and optional dictionary of service descriptions
        (for the NCSD), does stuff
        """
        timetable = Timetable(open_file)

        operators = [operator for operator in map(cls.get_operator, timetable.operators) if operator]

        stop_ids = timetable.stops.keys()

        service_element = timetable.element.find('txc:Services/txc:Service', NS)

        line_name, line_brand = cls.get_line_name_and_brand(
            service_element, filename
        )

        # service description:

        description = timetable.description
        if service_descriptions is not None:
            description = service_descriptions.get('%s%s' % (operators[0].id, line_name), '')
        elif not description:
            print('%s is missing a name' % filename)

        if region_id == 'NE':
            description = cls.sanitize_description(description)

        if len(description) > 128:
            print('Description "%s" is too long in %s' % (description, filename))
            description = description[:128]

        # net and service code:

        net, service_code, line_ver = cls.infer_from_filename(timetable.element.attrib['FileName'])
        if service_code is None:
            service_code = timetable.service_code

        # stops:

        stops = StopPoint.objects.in_bulk(stop_ids)

        try:
            stop_usages = []
            for grouping in timetable.groupings:
                stop_usages += [
                    StopUsage(
                        service_id=service_code, stop_id=row.part.stop.atco_code,
                        direction=grouping.direction, order=i, timing_status=row.part.timingstatus
                    )
                    for i, row in enumerate(grouping.rows) if row.part.stop.atco_code in stops
                ]

            show_timetable = True
            line_strings = []
            for grouping in timetable.groupings:
                show_timetable = show_timetable and (
                    len(grouping.journeys) < 40 or
                    len(grouping.rows[0].times) < 40
                )
                for journeypattern in grouping.journeypatterns:
                    line_string = cls.line_string_from_journeypattern(journeypattern, stops)
                    if line_string not in line_strings:
                        line_strings.append(line_string)
                multi_line_string = MultiLineString(*(ls for ls in line_strings if ls))

            if show_timetable:
                del timetable.journeypatterns
                del timetable.stops
                del timetable.operators
                del timetable.element
                for grouping in timetable.groupings:
                    del grouping.journeys
                    del grouping.journeypatterns
                    for row in grouping.rows:
                        del row.next
                pickle_dir = os.path.join(DIR, '../../../data/TNDS', 'NCSD' if region_id == 'GB' else region_id)
                if not os.path.exists(pickle_dir):
                    os.makedirs(pickle_dir)
                    if region_id == 'GB':
                        os.mkdir(os.path.join(pickle_dir, 'NCSD_TXC'))
                basename = filename[:-4]
                with open('%s/%s' % (pickle_dir, basename), 'wb') as open_file:
                    pickle.dump(timetable, open_file)
                    cache.set('%s/%s' % (region_id, basename.replace(' ', '')), timetable)

        except (AttributeError, IndexError) as error:
            print(error, filename)
            show_timetable = False
            stop_usages = [StopUsage(service_id=service_code, stop_id=stop, order=0) for stop in stops]

        # service:

        service, created = Service.objects.update_or_create(
            service_code=service_code,
            defaults=dict(
                line_name=line_name,
                line_brand=line_brand,
                mode=timetable.mode,
                description=description,
                net=net,
                line_ver=line_ver,
                region_id=region_id,
                date=timetable.date,
                current=True,
                show_timetable=show_timetable,
                geometry=multi_line_string
            )
        )

        if created:
            service.operator.add(*operators)
        else:
            service.operator.set(operators)
            service.stops.clear()
        StopUsage.objects.bulk_create(stop_usages)

    @classmethod
    @transaction.atomic
    def handle_region(cls, archive_name):
        region_id = archive_name.split('/')[-1][:-4]
        if region_id == 'NCSD':
            region_id = 'GB'

        Service.objects.filter(region_id=region_id).update(current=False)

        with zipfile.ZipFile(archive_name) as archive:

            # the NCSD has service descriptions in a separate file:
            if 'IncludedServices.csv' in archive.namelist():
                with archive.open('IncludedServices.csv') as csv_file:
                    reader = csv.DictReader(line.decode('utf-8') for line in csv_file)
                    # e.g. {'NATX323': 'Cardiff - Liverpool'}
                    service_descriptions = {row['Operator'] + row['LineName']: row['Description'] for row in reader}
            else:
                service_descriptions = None

            for i, filename in enumerate(archive.namelist()):
                if i % 100 == 0:
                    print(i)

                if filename.endswith('.xml'):
                    with archive.open(filename) as open_file:
                        cls.do_service(open_file, region_id, filename, service_descriptions=service_descriptions)

    @classmethod
    def handle(cls, *args, **options):
        for archive_name in options['filenames']:
            print(archive_name)
            cls.handle_region(archive_name)
