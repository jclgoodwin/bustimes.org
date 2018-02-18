# -*- coding: utf-8 -*-
import io
import os
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.conf import settings
from django.db import transaction
from chardet.universaldetector import UniversalDetector
from titlecase import titlecase
from busstops.models import Operator, Service, StopPoint, StopUsage


class Command(BaseCommand):
    services = {}
    deferred_stop_codes = []
    deferred_stops = {}
    direction = None
    service_code = None
    stop_usages = []

    @staticmethod
    def set_up():
        for id, name in (
                ('MET', 'Translink Metro'),
                ('ULB', 'Ulsterbus'),
                ('GLE', 'Goldline Express'),
                ('UTS', 'Ulsterbus Town Services'),
                ('FY', 'Ulsterbus Foyle'),
                ('BE', 'Bus Éireann')
        ):
            Operator.objects.update_or_create(id=id, name=name, defaults={
                'region_id': 'NI',
                'vehicle_mode': 'bus'
            })

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

    @classmethod
    def handle_route_description(cls, line):
        assert line[2:3] == 'N'

        operator = line[3:7].strip().upper()
        route_number = line[7:11].strip().upper()
        # route_direction = line[11:12]
        route_description = line[12:].strip()
        if route_description.isupper():
            route_description = titlecase(route_description)

        service_code = route_number + '_' + operator
        cls.service_code = service_code

        if service_code not in cls.services:
            cls.services[service_code] = {'O': {}, 'I': {}}
            defaults = {
                'region_id': 'NI',
                'date': '2016-11-01',
                'line_name': route_number,
                'description': route_description,
                'mode': 'bus',
                'show_timetable': True,
                'current': True
            }
            service = Service.objects.update_or_create(service_code=service_code, defaults=defaults)[0]
            if operator:
                service.operator.set((operator,))

    @classmethod
    def handle_stop(cls, line):
        record_identity = line[:2]
        atco_code = line[2:14]
        if atco_code not in cls.services[cls.service_code][cls.direction]:
            if not StopPoint.objects.filter(atco_code=atco_code).exists():
                if not atco_code.startswith('7'):
                    print(atco_code)
                    return
                cls.deferred_stop_codes.append(atco_code)
            if record_identity == 'QI':
                timing_status = line[26:28]
                order = 1
            else:
                timing_status = line[21:23]
                if record_identity == 'QO':
                    order = 0
                else:
                    order = 2
            stop_usage = StopUsage(
                service_id=cls.service_code,
                stop_id=atco_code,
                direction=('Outbound' if cls.direction == 'O' else 'Inbound'),
                timing_status=('PTP' if timing_status == 'T1' else 'OTH'),
                order=order
            )
            cls.services[cls.service_code][cls.direction][atco_code] = stop_usage
            cls.stop_usages.append(stop_usage)

    @classmethod
    def handle_location(cls, line):
        atco_code = line[3:15]
        if atco_code in cls.deferred_stop_codes:
            common_name = line[15:].strip()
            cls.deferred_stops[atco_code] = StopPoint(
                atco_code=atco_code,
                common_name=common_name
            )

    @classmethod
    def handle_location_additional(cls, line):
        atco_code = line[3:15]
        if atco_code in cls.deferred_stops:
            assert atco_code in cls.deferred_stops
            latlong = Point(
                int(line[15:23].strip()),
                int(line[23:].strip()),
                srid=29902  # Irish Grid
            )
            cls.deferred_stops[atco_code].active = True
            cls.deferred_stops[atco_code].locality_centre = False
            cls.deferred_stops[atco_code].latlong = latlong
            cls.deferred_stops[atco_code].save()

    @classmethod
    def handle_line(cls, line):
        record_identity = line[:2]
        # QS - Journey Header
        if record_identity == 'QS':
            cls.direction = cls.get_journey_header(line)['direction'].strip()
        # QD - Route Description
        elif record_identity == 'QD':
            cls.handle_route_description(line)
        # QO - Journey Origin
        # QI - Journey Intermediate
        # QT - Journey Destination
        elif record_identity in ('QO', 'QI', 'QT'):
            cls.handle_stop(line)
        elif record_identity == 'QL':
            cls.handle_location(line)
        elif record_identity == 'QB':
            cls.handle_location_additional(line)

    @classmethod
    def handle_open_file(cls, open_file):
        for line in open_file:
            cls.handle_line(line)

    @classmethod
    def handle_file(cls, path):
        # detect encoding
        with io.open(path, mode='rb') as raw_file:
            detector = UniversalDetector()
            for line in raw_file.readlines():
                detector.feed(line)
                if detector.done:
                    break
        detector.close()
        encoding = detector.result["encoding"]
        if encoding:
            with io.open(path, encoding=encoding) as open_file:
                cls.handle_open_file(open_file)

    @classmethod
    def create_stop_usages(cls):
        StopUsage.objects.bulk_create(cls.stop_usages)

    @classmethod
    @transaction.atomic
    def handle(cls, *args, **options):
        cls.set_up()

        Service.objects.filter(region_id='NI').update(current=False)
        StopUsage.objects.filter(service__region_id='NI').delete()

        for dirpath in ('metro_data', 'Metro', 'ULB'):
            for dirpath, _, filenames in os.walk(os.path.join(settings.DATA_DIR, dirpath)):
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    cls.handle_file(path)

        cls.create_stop_usages()

        Service.objects.filter(region_id='NI', stops__isnull=True).update(current=False)
