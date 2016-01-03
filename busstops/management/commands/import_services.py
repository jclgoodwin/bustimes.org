"""
Command for importing transport services.

So far, all services in the SE, EA, Y and NCSD regions can be imported without
known errors.

Usage:

    ./manage.py import_services EA.zip [EM.zip etc]
"""

from django.core.management.base import BaseCommand
from busstops.models import Operator, StopPoint, Service

import re
import zipfile
import csv
import xml.etree.cElementTree as ET
from datetime import datetime
from titlecase import titlecase


class Command(BaseCommand):

    # see https://docs.python.org/2/library/xml.etree.elementtree.html#parsing-xml-with-namespaces
    ns = {'txc': 'http://www.transxchange.org.uk/'}

    now = datetime.today()

    serviceversion_regex = re.compile(r'(SVR|[^ _]+_TXC_|[a-z]+_|.*_atco_)(.+).xml$')
    net_regex = re.compile(r'([a-z]+)_$')
    description_regex = re.compile(r'.+,([^ ].+)$')

    # map TradingNames to operator IDs where there is no correspondence between the NOC DB and TNDS:
    SPECIAL_OPERATOR_TRADINGNAMES = {
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
        'Notts & Derby': 'NDTR'
    }
    # map OperatorCodes to operator IDs (ditto, where there is no TradingName):
    SPECIAL_OPERATOR_CODES = {
        'HIB':  'HIMB',  # Holy Island Minibus
        '1866': 'BPTR',  # Burnley & Pendle
        '2152': 'RSTY',  # R S Tyrer & Sons
        '2916': 'SPCT',  # South Pennine Community Transport
        'RB1':  'RBRO',  # Richards Bros
        'ACY':  'ACYM',  # Arriva Cymru/Wales
        'AM0':  'AMID',  # Arriva Midlands
        'RMB':  'RMBL',  # Routemaster Buses Ltd
        'JO1':  'JTMT',  # John's Travel (Merthyr Tydfil)
        'CO':   'CFSV',  # Coniston Launch/Ferry
        'CL':   'CFSV',  # Coniston Launch/Ferry
        'SGI':  'SGIL',  # Steel Group Investments Limited
        'EYM':  'EYMS',  # East Yorkshire Motor Services
        'WINF': 'WMLC',  # Windermere Lake Cruises/Ferry
        'DPC':  'DPCE',  # (Don) Prentice (Coaches)
        'PCV':  'PCVN',  # (Peter) Canavan (Travel)
        'RGJ':  'RGJS',  # R G Jamieson & Son
        'DAM':  'DAMC',  # D A & A J MacLean
        'ADD':  'ADDI',  # Addison News/of Callendar
    }

    def add_arguments(self, parser):
        parser.add_argument('filenames', nargs='+', type=str)

    def get_net(self, file_name):
        """
        Get the service 'net' (for services in the EA, EM, L, WM, SE and SW regions).
        """
        matches = self.serviceversion_regex.match(file_name)

        if matches is not None:
            net_matches = self.net_regex.match(matches.group(1))
            if net_matches is not None:
                return net_matches.group(1)
        return ''

    def sanitize_description_part(self, part):
        sanitized_part = self.description_regex.match(part.strip())
        return sanitized_part.group(1) if sanitized_part is not None else part

    def sanitize_description(self, name):
        """
        Given an oddly formatted description from the North East,
        like 'Bus Station bay 5,Blyth - Grange Road turning circle,Widdrington Station',
        returns a shorter, more normal version like
        'Blyth - Widdrington Station'
        """

        parts = [self.sanitize_description_part(part) for part in name.split(' - ')]
        return ' - '.join(parts)

    def get_operator_name(self, operator_element):
        "Given an Operator element, returns the operator name or None"

        for element_name in ('TradingName', 'OperatorNameOnLicence', 'OperatorShortName'):
            element = operator_element.find('txc:%s' % element_name, self.ns)
            if element is not None and element.text is not None:
                return element.text.replace('&amp;', '&')

    def get_operator_code(self, operator_element):
        "Given an Operator element, returns the operator code or None"

        for element_name in ('National', ''):
            element = operator_element.find('txc:%sOperatorCode' % element_name, self.ns)
            if element is not None:
                return element.text

    def get_operator(self, operator_element):
        "Given an Operator element, returns an Operator object."

        try:
            # Get by national operator code
            operator_code = self.get_operator_code(operator_element)
            possible_operators = Operator.objects.filter(id=operator_code)
            if len(possible_operators) == 1:
                return possible_operators.first()

            # Get by name
            operator_name = self.get_operator_name(operator_element)

            if operator_name == 'Replacement Service':
                return None

            possible_operators = Operator.objects.filter(name__startswith=operator_name)
            if len(possible_operators) == 1:
                return possible_operators.first()

            if operator_name in self.SPECIAL_OPERATOR_TRADINGNAMES:
                return Operator.objects.get(id=self.SPECIAL_OPERATOR_TRADINGNAMES[operator_name])

            if operator_code in self.SPECIAL_OPERATOR_CODES:
                return Operator.objects.get(id=self.SPECIAL_OPERATOR_CODES[operator_code])

        except Exception, error:
            print str(error)
            print ET.tostring(operator_element)

    def do_service(self, root, region_id, service_descriptions=None):

        file_name = root.attrib['FileName']

        for service_element in root.find('txc:Services', self.ns):

            line_name = service_element.find('txc:Lines', self.ns)[0][0].text
            if len(line_name) > 64:
                print 'Name "%s" is too long in %s' % (line_name, file_name)
                line_name = line_name[:64]

            mode_element = service_element.find('txc:Mode', self.ns)
            if mode_element is not None:
                mode = mode_element.text[:10]
            else:
                mode = ''

            # service operators:
            # (doing this preliminary bit now, to make getting NCSD descriptions possible)

            operators_element = root.find('txc:Operators', self.ns)
            operators = map(self.get_operator, operators_element)
            operators = filter(None, operators)
            if len(operators) == 0:
                print file_name
                print ET.tostring(operators_element)

            # service description:

            description_element = service_element.find('txc:Description', self.ns)
            if description_element is not None:
                description = description_element.text
            elif service_descriptions is not None:
                description = service_descriptions.get(operators[0].id + line_name, '')
            else:
                print '%s is missing a name' % file_name
                description = ''

            if description.isupper():
                description = titlecase(description)

            if region_id == 'NE':
                description = self.sanitize_description(description)

            if len(description) > 128:
                print 'Description "%s" is too long in %s' % (description, file_name)
                description = description[:128]

            # service:

            service = Service.objects.update_or_create(
                service_code=service_element.find('txc:ServiceCode', self.ns).text,
                defaults=dict(
                    line_name=line_name,
                    mode=mode,
                    description=description,
                    net=self.get_net(file_name),
                    region_id=region_id,
                    date=root.attrib['ModificationDateTime'][:10],
                    current=True
                )
            )[0]

            # service operators (part 2):

            if operators:
                try:
                    service.operator.add(*operators)
                except Exception, error:
                    print file_name
                    print str(error)

            # service stops:

            try:
                stop_elements = root.find('txc:StopPoints', self.ns)
                stop_ids = [stop.find('txc:StopPointRef', self.ns).text for stop in stop_elements]
                stops = StopPoint.objects.filter(atco_code__in=stop_ids)
                service.stops.add(*stops)
            except Exception, error:
                print str(error)


    def handle(self, *args, **options):

        service_descriptions = None

        for archive_name in options['filenames']:

            region_id = archive_name.split('/')[-1][:-4]
            if region_id == 'NCSD':
                region_id = 'GB'

            archive = zipfile.ZipFile(archive_name)

            Service.objects.filter(region_id=region_id).update(current=False)

            # the NCSD has service descriptions in a separate file:
            if 'IncludedServices.csv' in archive.namelist():
                with archive.open('IncludedServices.csv') as csv_file:
                    reader = csv.DictReader(csv_file)
                    service_descriptions = {}
                    for row in reader:
                        # e.g. {'NATX323': 'Cardiff - Liverpool'}
                        service_descriptions[row['Operator'] + row['LineName']] = row['Description']

            for i, file_name in enumerate(archive.namelist()):
                if (i - 1) % 1000 == 0:
                    print i

                if file_name.endswith('.xml'):
                    try:
                        root = ET.parse(archive.open(file_name)).getroot()
                        self.do_service(root, region_id, service_descriptions=service_descriptions)
                    except Exception, error:
                        print str(error)

            Service.objects.filter(region_id=region_id, current=False).delete()
