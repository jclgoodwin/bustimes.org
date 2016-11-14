import io
import os
from django.core.management.base import BaseCommand
from busstops.models import Operator, Service, StopPoint, StopUsage


class Command(BaseCommand):
    services = {}

    @staticmethod
    def get_file_header(line):
        return {
            'file_type': line[:8],
            'version': line[8:12],
            'file_originator': line[12:44],
            'source_product': line[44:60],
            'production_datetime': line[60:74]
        }

    @staticmethod
    def get_journey_header(line):
        return {
            'transaction_type': line[2:3],
            'operator': line[3:7],
            'unique_journey_identifier': line[7:13],
            'direction': line[64:],
        }

    @staticmethod
    def get_route_description(line):
        return {
            'transaction_type': line[2:3],
            'operator': line[3:7],
            'route_number': line[7:11],
            'route_direction': line[11:12],
            'route_description': line[12:]
        }

    @staticmethod
    def get_journey_note(line):
        return {
            'note_code': line[2:7],
            'note_text': line[7:],
        }

    def handle_file(self, open_file):
        # print(self.get_file_header(open_file.readline()))

        for line in open_file:
            record_identity = line[:2]
            # QS - Journey Header
            if record_identity == 'QS':
                direction = self.get_journey_header(line)['direction'].strip()
            # QD - Route Description
            elif record_identity == 'QD':
                service = self.get_route_description(line)
                operator = service['operator'].strip().upper()
                route_number = service['route_number'].strip()
                service_code = route_number + '_' + operator
                if service_code not in self.services:
                    self.services[service_code] = {'O': {}, 'I': {}}
                    try:
                        Service.objects.update_or_create(
                            service_code=service_code,
                            defaults={
                                'region_id': 'NI',
                                'date': '2016-11-01',
                                'line_name': line[7:11].strip(),
                                'description': service['route_description'].strip(),
                                'operator': [operator] if operator else None,
                                'mode': 'bus'
                            }
                        )
                    except Exception as e:
                        print(e)
            # QO - Journey Origin
            # QI - Journey Intermediate
            # QT - Journey Destination
            elif record_identity in ('QO', 'QI', 'QT'):
                atco_code = line[2:14]
                if atco_code not in self.services[service_code][direction]:
                    if not StopPoint.objects.filter(atco_code=atco_code).exists():
                        print(line)
                        continue
                    if record_identity == 'QI':
                        timing_status = line[26:28]
                        order = 1
                    else:
                        timing_status = line[21:23]
                        if record_identity == 'QO':
                            order = 0
                        else:
                            order = 2
                    self.services[service_code][direction][atco_code] = StopUsage.objects.create(
                        service_id=service_code,
                        stop_id=atco_code,
                        direction=('Outbound' if direction == 'O' else 'Inbound'),
                        timing_status=('PTP' if timing_status == 'T1' else 'OTH'),
                        order=order
                    )

    def handle(self, *args, **options):
        Operator.objects.update_or_create(id='MET', name='Translink Metro', region_id='NI')
        Operator.objects.update_or_create(id='ULB', name='Ulsterbus', region_id='NI')
        Operator.objects.update_or_create(id='GLE', name='Goldline Express', region_id='NI')
        Operator.objects.update_or_create(id='UTS', name='Ulsterbus Town Services', region_id='NI')
        Operator.objects.update_or_create(id='FY', name='Ulsterbus Foyle', region_id='NI')

        Service.objects.filter(region_id='NI').delete()

        with io.open('MET20160901v1.cif', encoding='cp1252') as open_file:
            self.handle_file(open_file)

        for dirpath, _, filenames in os.walk('ULB'):
            for filename in filenames:
                with io.open(os.path.join(dirpath, filename), encoding='cp1252') as open_file:
                    self.handle_file(open_file)
