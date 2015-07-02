from django.core.management.base import BaseCommand, CommandError
from busstops.models import Operator, StopPoint, Service, ServiceVersion

import re
import os
import xml.etree.ElementTree as ET

from datetime import timedelta, date, datetime


class Command(BaseCommand):

    ns = {'txc': 'http://www.transxchange.org.uk/'} # see https://docs.python.org/2/library/xml.etree.elementtree.html#parsing-xml-with-namespaces
    now = datetime.today()

    def do_operators(self, operators_element):
        """
        Given an Operators element,
        returns a dictionary mapping "local" operator codes to Operator objects

        """
        operators = {}
        for o in operators_element:
            local_code = o.find('txc:OperatorCode', self.ns).text
            national_code = o.find('txc:NationalOperatorCode', self.ns).text
            operators[local_code] = Operator.objects.get(id=national_code)
        return operators

    def do_service(self, services_element, service_version_name, operators):

        for service_element in services_element:
            service = Service.objects.get_or_create(
                service_code=service_element.find('txc:ServiceCode', self.ns).text,
                defaults={'operator': operators[service_element.find('txc:RegisteredOperatorRef', self.ns).text]},
                )[0]

            service_version = ServiceVersion(
                name=service_version_name,
                service=service,
                mode=service_element.find('txc:Mode', self.ns).text,
                description=service_element.find('txc:Description', self.ns).text,
                line_name=service_element.find('txc:Lines', self.ns)[0][0].text
                )

            date_element = service_element.find('txc:OperatingPeriod', self.ns)
            start_date_element = date_element.find('txc:StartDate', self.ns)
            end_date_element = date_element.find('txc:EndDate', self.ns)

            # print start_date_element

            if end_date_element is not None:
                end_date = datetime.strptime(end_date_element.text, '%Y-%m-%d')
                if end_date < self.now:
                    break
                service_version.end_date = end_date

            service_version.start_date = datetime.strptime(start_date_element.text, '%Y-%m-%d')

            service_version.save()

        # return service_version # assuming one service version per file


    def handle(self, *args, **options):

        for root, dirs, files in os.walk('data/Y'):

            for file in files:
                print file
                e = ET.parse('data/Y/' + file).getroot()
                operators = self.do_operators(e.find('txc:Operators', self.ns))
                # service_version = 
                self.do_service(e.find('txc:Services', self.ns), file[3:-4], operators)
