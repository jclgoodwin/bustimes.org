import zipfile

from django.conf import settings
from django.core.management import BaseCommand
from django.contrib.gis.geos import GEOSGeometry

from bustimes.utils import download_if_changed
from bustimes.management.commands.import_gtfs import read_file
from ...models import Region, District, AdminArea, Locality


class Command(BaseCommand):

    def handle_file(self, archive, model, filename, pk_field, mapping, convert_pk_to_int=False):
        existing = model.objects.in_bulk()

        to_create = []
        to_update = []

        for row in read_file(archive, filename):
            print(row)
            pk = row[pk_field]

            if convert_pk_to_int:
                pk = int(pk)  # convert '071' to 71 (AdministrativeAreaCode)

            if pk not in existing:
                thing = model(pk=pk)
                to_create.append(thing)
            else:
                thing = existing[pk]
                to_update.append(thing)
            for csv_field, field in mapping.items():
                setattr(thing, field, row[csv_field])

        model.objects.bulk_create(to_create)
        model.objects.bulk_update(to_update, fields=mapping.values())

    def do_regions(self, archive):
        self.handle_file(archive, Region, 'Regions.csv', 'RegionCode', {
            'RegionName': 'name'
        })

    def do_admin_areas(self, archive):
        self.handle_file(archive, AdminArea, 'AdminAreas.csv', 'AdministrativeAreaCode', {
            'AtcoAreaCode': 'atco_code',
            'AreaName': 'name',
            'ShortName': 'short_name',
            'Country': 'country',
            'RegionCode': 'region_id',
        }, True)

    def do_districts(self, archive):
        self.handle_file(archive, District, 'Districts.csv', 'DistrictCode', {
            'DistrictName': 'name',
            'AdministrativeAreaCode': 'admin_area_id'
        }, True)

    def do_localities(self, archive):
        existing_localities = Locality.objects.in_bulk()
        to_update = []
        to_create = []

        for row in read_file(archive, 'Localities.csv'):
            locality_code = row['NptgLocalityCode']
            if locality_code in existing_localities:
                locality = existing_localities[locality_code]
                to_update.append(locality)
            else:
                locality = Locality(id=locality_code)
                to_create.append(locality)

            locality.name = row['LocalityName']
            locality.qualifier_name = row['QualifierName']
            locality.admin_area_id = row['AdministrativeAreaCode']
            locality.latlong = GEOSGeometry(f"SRID=27700;POINT({row['Easting']} {row['Northing']})")

            # if row['NptgDistrictCode'] != '310':
            #         locality.district_id = row['NptgDistrictCode']

        Locality.objects.bulk_update(
            to_update,
            fields=['name', 'qualifier_name', 'admin_area', 'latlong', 'district'],
            batch_size=1000
        )
        Locality.objects.bulk_create(to_create)

    def handle(self, **kwargs):

        url = "https://naptan.app.dft.gov.uk/datarequest/nptg.ashx?format=csv"
        path = settings.DATA_DIR / 'NPTG.zip'
        modified, last_modified = download_if_changed(path, url)

        if not modified:
            return

        with zipfile.ZipFile(path) as archive:
            self.do_regions(archive)

            self.do_admin_areas(archive)

            self.do_districts(archive)

            self.do_localities(archive)
