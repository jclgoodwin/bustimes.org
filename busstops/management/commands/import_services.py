"""
Command for importing transport services.

So far, all services in the SE, EA, Y and NCSD regions can be imported without
known errors.

Usage:

    ./manage.py import_services EA.zip [EM.zip etc]
"""

import os
import shutil
import zipfile
import csv
import yaml
import warnings
import xml.etree.cElementTree as ET
from datetime import date
from django.contrib.gis.geos import LineString, MultiLineString
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from timetables.txc import Timetable, sanitize_description_part
from ...models import Operator, StopPoint, Service, StopUsage, DataSource, Region, Journey, ServiceCode, ServiceDate
from .generate_departures import handle_region as generate_departures
from .generate_service_dates import handle_services as generate_service_dates


# see https://docs.python.org/2/library/xml.etree.elementtree.html#parsing-xml-with-namespaces
NS = {'txc': 'http://www.transxchange.org.uk/'}


class Command(BaseCommand):
    "Command that imports bus services from a zip file"

    service_descriptions = None
    region_id = None

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

    @staticmethod
    def get_operator_code(operator_element, element_name):
        element = operator_element.find('txc:{}'.format(element_name), NS)
        if element is not None:
            return element.text

    @classmethod
    def get_operator_name(cls, operator_element):
        "Given an Operator element, returns the operator name or None"

        for element_name in ('TradingName', 'OperatorNameOnLicence', 'OperatorShortName'):
            name = cls.get_operator_code(operator_element, element_name)
            if name:
                return name.replace('&amp;', '&')

    @staticmethod
    def get_operator_by(scheme, code):
        if code:
            return Operator.objects.filter(operatorcode__code=code, operatorcode__source__name=scheme).first()

    def get_operator(self, operator_element):
        "Given an Operator element, returns an operator code for an operator that exists."

        for tag_name, scheme in (
            ('NationalOperatorCode', 'National Operator Codes'),
            ('LicenceNumber', 'Licence'),
        ):
            operator_code = self.get_operator_code(operator_element, tag_name)
            if operator_code:
                operator = self.get_operator_by(scheme, operator_code)
                if operator:
                    return operator

        # Get by regional operator code
        operator_code = self.get_operator_code(operator_element, 'OperatorCode')
        if operator_code:
            operator = self.get_operator_by(self.region_id, operator_code)
            if not operator:
                operator = self.get_operator_by('National Operator Codes', operator_code)
            if operator:
                return operator

        # Get by name
        operator_name = self.get_operator_name(operator_element)

        if operator_name in ('Replacement Service', 'UNKWN'):
            return None

        warnings.warn('No operator found for element %s' %
                      ET.tostring(operator_element).decode('utf-8'))

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
        elif line_name == 'ZAP':
            line_brand = 'Cityzap'
        elif line_name == 'TAD':
            line_brand = 'Tadfaster'
        else:
            line_brand = ''

        if len(line_name) > 64:
            warnings.warn('Name "%s" too long in %s' % (line_name, filename))
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
        except ValueError:
            pass

    def do_service(self, open_file, filename):
        """
        Given a root element, region ID, filename, and optional dictionary of service descriptions
        (for the NCSD), does stuff
        """

        timetable = Timetable(open_file)

        if not hasattr(timetable, 'element'):  # invalid file
            return

        if timetable.mode == 'underground':
            return

        if timetable.operating_period.end and timetable.operating_period.end < date.today():
            return

        operators = timetable.operators
        # if timetable.operator and len(operators) > 1:
        #     operators = [operator for operator in operators if operator.get('id') == timetable.operator]
        operators = [operator for operator in map(self.get_operator, operators) if operator]

        line_name, line_brand = self.get_line_name_and_brand(timetable.element.find('txc:Services/txc:Service', NS),
                                                             filename)

        # net and service code:
        net, service_code, line_ver = self.infer_from_filename(filename)
        if service_code is None:
            service_code = timetable.service_code

        defaults = dict(
            line_name=line_name,
            line_brand=line_brand,
            mode=timetable.mode,
            net=net,
            line_ver=line_ver,
            region_id=self.region_id,
            date=timetable.transxchange_date,
            current=True,
            source=self.source
        )

        # stops:
        stops = StopPoint.objects.in_bulk(timetable.stops.keys())

        try:
            stop_usages = []
            for grouping in timetable.groupings:
                if grouping.rows:
                    stop_usages += [
                        StopUsage(
                            service_id=service_code, stop_id=row.part.stop.atco_code,
                            direction=grouping.direction, order=i, timing_status=row.part.timingstatus
                        )
                        for i, row in enumerate(grouping.rows) if row.part.stop.atco_code in stops
                    ]
                    if grouping.direction == 'outbound' or grouping.direction == 'inbound':
                        defaults[grouping.direction + '_description'] = str(grouping)

            show_timetable = True
            line_strings = []
            for grouping in timetable.groupings:
                for journeypattern in grouping.journeypatterns:
                    line_string = self.line_string_from_journeypattern(journeypattern, stops)
                    if line_string not in line_strings:
                        line_strings.append(line_string)
            multi_line_string = MultiLineString(*(ls for ls in line_strings if ls))

        except (AttributeError, IndexError) as error:
            warnings.warn('%s, %s' % (error, filename))
            show_timetable = False
            stop_usages = [StopUsage(service_id=service_code, stop_id=stop, order=0) for stop in stops]
            multi_line_string = None

        # service:
        defaults['show_timetable'] = show_timetable
        defaults['geometry'] = multi_line_string

        if self.service_descriptions:
            filename_parts = filename.split('_')
            operator = filename_parts[-2]
            line_name = filename_parts[-1][:-4]
            defaults['outbound_description'] = self.service_descriptions.get('%s%s%s' % (operator, line_name, 'O'), '')
            defaults['inbound_description'] = self.service_descriptions.get('%s%s%s' % (operator, line_name, 'I'), '')
            defaults['description'] = defaults['outbound_description'] or defaults['inbound_description']
        else:
            description = timetable.description
            if not description:
                warnings.warn('%s missing a description' % filename)
            elif len(description) > 255:
                warnings.warn('Description "%s" too long in %s' % (description, filename))
                description = description[:255]

            if self.region_id == 'NE':
                description = self.sanitize_description(description)
            if description and description != 'Origin - Destination':
                defaults['description'] = description

            parts = service_code.split('_')
            if parts[0] == 'NW':
                assert len(parts) >= 5
                assert parts[-1].isdigit()

                homogeneous_service_code = '_'.join(parts[:-1])

                same_services = Service.objects.filter(description=description, current=True)
                same_service = same_services.filter(service_code__startswith=homogeneous_service_code + '_')
                same_service = same_service.exclude(service_code=service_code).first()

                if same_service:
                    ServiceCode.objects.update_or_create(service=same_service, code=service_code, scheme='NW TNDS')
                    service_code = same_service.service_code

                    for stop_usage in stop_usages:
                        stop_usage.service_id = service_code

        service, created = Service.objects.update_or_create(service_code=service_code, defaults=defaults)

        if created:
            service.operator.add(*operators)
        else:
            if service.slug == service_code.lower():
                service.slug = ''
                service.save()
            service.operator.set(operators)
            if service_code not in self.service_codes:
                service.stops.clear()
        StopUsage.objects.bulk_create(stop_usages)

        if timetable.private_code:
            ServiceCode.objects.update_or_create({
                'code': timetable.private_code
            }, service=service, scheme='Traveline Cymru')

        self.service_codes.add(service_code)

    def set_region(self, archive_name):
        self.region_id, _ = os.path.splitext(os.path.basename(archive_name))

        self.source, _ = DataSource.objects.get_or_create(name=self.region_id)

        if self.region_id == 'NCSD':
            self.region_id = 'GB'

    def handle_region(self, archive_name):
        self.set_region(archive_name)
        self.service_codes = set()

        with transaction.atomic():
            Service.objects.filter(source=self.source, current=True).update(current=False)

            with zipfile.ZipFile(archive_name) as archive:
                # the NCSD has service descriptions in a separate file:
                if 'IncludedServices.csv' in archive.namelist():
                    with archive.open('IncludedServices.csv') as csv_file:
                        reader = csv.DictReader(line.decode('utf-8') for line in csv_file)
                        # e.g. {'NATX323': 'Cardiff - Liverpool'}
                        self.service_descriptions = {
                            row['Operator'] + row['LineName'] + row['Dir']: row['Description'] for row in reader
                        }
                else:
                    self.service_descriptions = None

                for filename in archive.namelist():
                    if filename.endswith('.xml'):
                        with archive.open(filename) as open_file:
                            self.do_service(open_file, filename)

            # correct services
            with open(os.path.join(settings.DATA_DIR, 'services.yaml')) as open_file:
                records = yaml.load(open_file, Loader=yaml.FullLoader)
                for service_code in records:
                    services = Service.objects.filter(service_code=service_code)
                    if 'operator' in records[service_code]:
                        if services.exists():
                            services.get().operator.set(records[service_code]['operator'])
                            del records[service_code]['operator']
                        else:
                            continue
                    services.update(**records[service_code])

            self.source.datetime = timezone.now()
            self.source.save()

        try:
            shutil.copy(archive_name, settings.TNDS_DIR)
        except shutil.SameFileError:
            pass

        with transaction.atomic():
            Journey.objects.filter(service__region=self.region_id).delete()
            generate_departures(Region.objects.get(id=self.region_id))

        with transaction.atomic():
            ServiceDate.objects.filter(service__region=self.region_id).delete()
            generate_service_dates(Service.objects.filter(region=self.region_id))

        # StopPoint.objects.filter(active=True).exclude(service__current=True).update(active=False)
        # StopPoint.objects.filter(active=False, service__current=True).update(active=True)

        Service.objects.filter(region=self.region_id, current=False, geometry__isnull=False).update(geometry=None)

    def handle(self, *args, **options):
        for archive_name in options['filenames']:
            self.handle_region(archive_name)
