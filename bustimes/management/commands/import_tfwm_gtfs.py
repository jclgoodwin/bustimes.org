import zipfile
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models import Exists, OuterRef
from busstops.models import DataSource, Service, Operator, ServiceCode
from vehicles.models import JourneyCode
from ...utils import download_if_changed
from .import_gtfs import read_file


class Command(BaseCommand):
    def handle(self, *args, **options):
        source = DataSource.objects.get(name='TfWM')
        url = 'http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip'

        print(download_if_changed('tfwm_gtfs.zip', url, source.settings))

        operators = {}
        current_operators = Operator.objects.filter(
            Exists(Service.objects.filter(current=True, operator=OuterRef('pk'))))

        services = {}

        # trips = {}

        # source.journeycode_set.all().delete()

        with zipfile.ZipFile('tfwm_gtfs.zip') as archive:

            for line in read_file(archive, 'agency.txt'):
                name = line['agency_name'].replace("'", "’")
                if name == 'Thandi Transport Ltd':
                    name = 'Thandi Coaches'
                try:
                    operators[line['agency_id']] = current_operators.get(name=name)
                except (Operator.DoesNotExist, Operator.MultipleObjectsReturned) as e:
                    print(line, e)

            for line in read_file(archive, 'routes.txt'):
                operator = operators.get(line['agency_id'])
                if not operator:
                    continue

                try:
                    service = operator.service_set.get(current=True, line_name__iexact=line['route_short_name'])
                except (Service.DoesNotExist, Service.MultipleObjectsReturned):
                    continue

                services[line['route_id']] = service
                try:
                    ServiceCode.objects.create(
                        service=service, scheme=source.name, code=line['route_id']
                    )
                except IntegrityError:
                    pass

            for line in read_file(archive, 'trips.txt'):
                service = services.get(line['route_id'])

                try:
                    JourneyCode.objects.create(
                        service=service, data_source=source, destination=line['trip_headsign'], code=line['trip_id']
                    )
                except IntegrityError:
                    pass
