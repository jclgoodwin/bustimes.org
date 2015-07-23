from django.core.management.base import BaseCommand, CommandError
from busstops.models import Operator, StopPoint, Service, ServiceVersion

import os
import xml.etree.ElementTree as ET
# import re
from datetime import datetime


class Command(BaseCommand):

    # see https://docs.python.org/2/library/xml.etree.elementtree.html#parsing-xml-with-namespaces
    ns = {'txc': 'http://www.transxchange.org.uk/'}

    now = datetime.today()

    # map TradingNames to operator IDs where there is no correspondence between the NOC DB and TNDS
    SPECIAL_OPERATORS = {
        'Southwold Town Council': 'SWTC',
        'H.C.Chambers & Son': 'CHMB',
        'Bungay and Beccles Area CT': 'BBCT',
        'Stowmarket Minibus & Coach Hire': 'MBCH',
        'Harwich Harbour Ferry': 'HHFS',
        'Halesworth Area Community Transport': 'HACT',
    }

    # @staticmethod
    # def parse_duration(string):
    #     """
    #     Given a TransXChange RunTime string, e.g. 'PT180S',
    #     returns a timedelta, e.g. 180 seconds.

    #     Thanks to http://stackoverflow.com/a/4628148
    #     """
    #     regex = re.compile(r'PT((?P<hours>\d+?)H)?((?P<minutes>\d+?)M)?((?P<seconds>\d+?)S)?')
    #     matches = regex.match(string).groupdict()
    #     time_params = {}
    #     for (name, param) in matches.iteritems():
    #         if param:
    #             time_params[name] = int(param)
    #     return timedelta(**time_params)

    # @staticmethod
    # def weekday_to_int(weekday):
    #     weekdays = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')
    #     for i, day in enumerate(weekdays):
    #         if weekday == day:
    #             return i

    # @staticmethod
    # def get_operating_profile(element):
    #     """
    #     Given an OperatingProfile element,
    #     returns an OperatingProfile object that is (now) in the database
    #     """
    #     regular_days = ','.join(
    #         map(
    #             lambda e: weekday_to_int(e.tag[33:]), # tag name with namespace prefix removed
    #             element.find('txc:RegularDayType', ns).find('txc:DaysOfWeek', ns) # iterable containing children of DaysOfWeek element
    #             )
    #         )
    #     print regular_days
    #     profile, created = OperatingProfile.objects.get_or_create(
    #         regular_days=regular_days,
    #         )
    #     print profile

    def get_operator(self, operator_element):
        "Given an operators element, returns an Operator object."

        national_code_element = operator_element.find('txc:NationalOperatorCode', self.ns)

        # try:
        if national_code_element is not None:
            operator = Operator.objects.get(id=national_code_element.text)
        else:
            operator_name = str.replace(
                operator_element.find('txc:TradingName', self.ns).text,
                '&amp;',
                '&'
                )
            if operator_name in self.SPECIAL_OPERATORS:
                operator = Operator.objects.get(id=self.SPECIAL_OPERATORS[operator_name])
            else:
                operator = Operator.objects.get(name=operator_name)

        return operator

        # except:
            # print national_code_element.text

    def do_operators(self, operators_element):
        "Given an Operators element, returns a dict mapping local codes to Operator objects."

        operators = {}

        for operator_element in operators_element:
            if 'id' in operator_element.attrib:
                local_code = operator_element.attrib['id']
            else:
                local_code = operator_element.find('txc:OperatorCode', self.ns).text

            operator = self.get_operator(operator_element)
            operators[local_code] = operator

        return operators

    def do_service(self, services_element, service_version_name, operators, root):

        for service_element in services_element:

            service, created = Service.objects.get_or_create(
                service_code=service_element.find('txc:ServiceCode', self.ns).text
                )

            service.save()

            for operator in operators.values():
                service.operator.add(operator)

            for stop_element in root.find('txc:StopPoints', self.ns):
                try:
                    stop_atco_code = stop_element.find('txc:StopPointRef', self.ns).text
                    stop = StopPoint.objects.get(atco_code=stop_atco_code)
                    service.stops.add(stop)
                except:
                    print "Problem adding stop %s to service %s" % (stop_atco_code, service.service_code)

            service_version = ServiceVersion(
                name=service_version_name,
                service=service,
                mode=service_element.find('txc:Mode', self.ns).text,
                line_name=service_element.find('txc:Lines', self.ns)[0][0].text.split('|', 1)[0][:24] # shorten "N|Turquoise line", for example
                )

            description_element = service_element.find('txc:Description', self.ns)
            if description_element is not None:
                service_version.description = description_element.text

            date_element = service_element.find('txc:OperatingPeriod', self.ns)
            start_date_element = date_element.find('txc:StartDate', self.ns)
            end_date_element = date_element.find('txc:EndDate', self.ns)

            if end_date_element is not None:
                end_date = datetime.strptime(end_date_element.text, '%Y-%m-%d')
                if end_date < self.now:
                    break
                service_version.end_date = end_date

            service_version.start_date = datetime.strptime(start_date_element.text, '%Y-%m-%d')
            service_version.save()


    def handle(self, *args, **options):

        for root, dirs, files in os.walk('../TNDS/'):

            for i, file_name in enumerate(files):
                if i % 100 == 0:
                    print i

                # print file_name
                if file_name[-4:] == '.xml':
                    # try:
                        file_path = os.path.join(root, file_name)
                        e = ET.parse(file_path).getroot()
                        operators = self.do_operators(e.find('txc:Operators', self.ns))
                        self.do_service(e.find('txc:Services', self.ns), file_name[3:-4], operators, e)
                    # except:
                        # print "problem with %s" % file_path
