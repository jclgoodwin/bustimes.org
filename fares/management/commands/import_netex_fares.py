import io
# import os
import logging
import xml.etree.cElementTree as ET
import requests
import zipfile
from ciso8601 import parse_datetime
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
# from bustimes.utils import write_file
from ... import models


logger = logging.getLogger(__name__)


def get_atco_code(stop):
    ref = stop["@ref"]
    assert ref.startswith("atco:")
    return ref[5:]


def get_user_profile(element):
    return models.UserProfile.objects.get_or_create(
        {
            'name': element.findtext('Name'),
            'min_age': element.findtext('MinimumAge'),
            'max_age': element.findtext('MaximumAge'),
        },
        code=element.attrib["id"]
    )


def get_sales_offer_package(element):
    return models.SalesOfferPackage.objects.get_or_create(
        code=element.attrib["id"],
        name=element.findtext("Name", ""),
        description=element.findtext("Description", "")
    )


class Command(BaseCommand):
    base_url = "https://data.bus-data.dft.gov.uk"

    def handle_file(self, source, open_file, filename=None):
        iterator = ET.iterparse(open_file)

        if not filename:
            filename = open_file.name

        for _, element in iterator:
            if element.tag[:31] == '{http://www.netex.org.uk/netex}':
                element.tag = element.tag[31:]

        user_profiles = {}
        for usage_parameter in element.find("dataObjects/CompositeFrame/frames/FareFrame/usageParameters"):
            user_profile, created = get_user_profile(usage_parameter)
            user_profiles[user_profile.code] = user_profile

        sales_offer_packages = {}
        for sales_offer_package in element.find("dataObjects/CompositeFrame/frames/FareFrame/salesOfferPackages"):
            sales_offer_package, created = get_sales_offer_package(sales_offer_package)
            sales_offer_packages[sales_offer_package.code] = sales_offer_package

        price_groups = {}
        price_group_prices = {}
        price_groups_element = element.find("dataObjects/CompositeFrame/frames/FareFrame/priceGroups")
        if price_groups_element:
            for price_group_element in price_groups_element:
                price_element = price_group_element.find("members/GeographicalIntervalPrice")  # assume only 1 ~
                price_group, created = models.PriceGroup.objects.get_or_create(
                    code=price_group_element.attrib["id"],
                    amount=price_element.findtext("Amount")
                )
                price_groups[price_group.code] = price_group
                price_group_prices[price_element.attrib["id"]] = price_group

        fare_zones = {}
        fare_zones_element = element.find("dataObjects/CompositeFrame/frames/FareFrame/fareZones")
        if fare_zones_element:
            for fare_zone in fare_zones_element:
                fare_zone, created = models.FareZone.objects.get_or_create(
                    code=fare_zone.attrib['id'],
                    name=fare_zone.findtext("Name")
                )
                fare_zones[fare_zone.code] = fare_zone

        tariffs = {}
        distance_matrix_elements = {}
        time_intervals = {}
        for tariff_element in element.find("dataObjects/CompositeFrame/frames/FareFrame/tariffs"):
            fare_structre_elements = tariff_element.find("fareStructureElements")

            user_profile = fare_structre_elements.find(
                "FareStructureElement/GenericParameterAssignment/limitations/UserProfile"
            )
            user_profile, created = get_user_profile(user_profile)
            user_profiles[user_profile.code] = user_profile

            round_trip = fare_structre_elements.find(
                "FareStructureElement/GenericParameterAssignment/limitations/RoundTrip"
            )
            if round_trip:
                trip_type = round_trip.findtext('TripType')
            else:
                trip_type = ''

            tariff = models.Tariff.objects.create(
                code=tariff_element.attrib['id'], name=tariff_element.findtext("Name"),
                source=source, filename=filename,
                trip_type=trip_type, user_profile=user_profile
            )
            tariffs[tariff.code] = tariff

            distance_matrix_element_elements = fare_structre_elements.find(
                "FareStructureElement/distanceMatrixElements"
            )
            if distance_matrix_element_elements:
                for distance_matrix_element in distance_matrix_element_elements:
                    start_zone = distance_matrix_element.find("StartTariffZoneRef").attrib["ref"]
                    end_zone = distance_matrix_element.find("EndTariffZoneRef").attrib["ref"]
                    price_group = distance_matrix_element.find("priceGroups/PriceGroupRef").attrib['ref']
                    distance_matrix_element, created = models.DistanceMatrixElement.objects.get_or_create(
                        code=distance_matrix_element.attrib["id"],
                        start_zone=fare_zones[start_zone],
                        end_zone=fare_zones[end_zone],
                        price_group=price_groups[price_group],
                        tariff=tariff,
                    )
                    distance_matrix_elements[distance_matrix_element.code] = distance_matrix_element

            time_intervals_element = tariff_element.find("timeIntervals")
            if time_intervals_element:
                for time_interval in time_intervals_element:
                    time_interval, _ = models.TimeInterval.objects.get_or_create(
                        code=time_interval.attrib["id"],
                        name=time_interval.findtext("Name"),
                        description=time_interval.findtext("Description")
                    )
                    time_intervals[time_interval.code] = time_interval

        for fare_table_element in element.find("dataObjects/CompositeFrame/frames/FareFrame/fareTables"):
            tariff_ref = fare_table_element.find("usedIn/TariffRef")
            if tariff_ref is None:
                pass
            else:
                tariff_ref = tariff_ref.attrib["ref"]
                tariff = tariffs[tariff_ref]

            user_profile_ref = fare_table_element.find("pricesFor/UserProfileRef")
            if user_profile_ref is not None:
                user_profile_ref = user_profile_ref.attrib["ref"]
                if user_profile_ref not in user_profiles:
                    user_profile_ref = f"fxc:{user_profile}"
                user_profile = user_profiles[user_profile_ref]
            else:
                user_profile = None

            sales_offer_package_ref = fare_table_element.find("pricesFor/SalesOfferPackageRef")
            if sales_offer_package_ref is not None:
                sales_offer_package_ref = sales_offer_package_ref.attrib["ref"]
                sales_offer_package = sales_offer_packages[sales_offer_package_ref]
            else:
                sales_offer_package = None

            columns_element = fare_table_element.find('columns')
            rows_element = fare_table_element.find('rows')

            if columns_element and rows_element:
                table, created = models.FareTable.objects.update_or_create(
                    {
                        "user_profile": user_profile,
                        "sales_offer_package": sales_offer_package,
                        "description": fare_table_element.findtext("Description", "")
                    },
                    tariff=tariff,
                    code=fare_table_element.attrib["id"],
                    name=fare_table_element.findtext("Name", "")
                )

                if not created:
                    table.column_set.all().delete()
                    table.row_set.all().delete()

                columns = {}
                if columns_element:
                    for column in columns_element:
                        column = models.Column.objects.create(
                            table=table,
                            code=column.attrib['id'],
                            name=column.findtext('Name'),
                            order=column.attrib.get('order')
                        )
                        columns[column.code] = column

                rows = {}
                if rows_element:
                    for row in rows_element:
                        row = models.Row.objects.create(
                            table=table,
                            code=row.attrib['id'],
                            name=row.findtext('Name'),
                            order=row.attrib.get('order')
                        )
                        rows[row.code] = row
            else:
                table = None

            for sub_fare_table_element in fare_table_element.find('includes'):  # fare tables within fare tables
                cells_element = sub_fare_table_element.find('cells')
                if cells_element:
                    for cell_element in cells_element:
                        columnn_ref = cell_element.find('ColumnRef').attrib['ref']
                        row_ref = cell_element.find('RowRef').attrib['ref']
                        distance_matrix_element_price = cell_element.find("DistanceMatrixElementPrice")
                        price_ref = distance_matrix_element_price.find("GeographicalIntervalPriceRef")
                        distance_matrix_element_ref = distance_matrix_element_price.find("DistanceMatrixElementRef")

                        if row_ref in rows:
                            row = rows[row_ref]
                        else:
                            # sometimes the RowRef doesn't correspond exactly to a Row id
                            row_ref_suffix = row_ref.split('@')[-1]
                            row_ref_suffix = f'@{row_ref_suffix}'
                            row_refs = [row_ref for row_ref in rows if row_ref.endswith(row_ref_suffix)]
                            assert len(row_refs) == 1
                            row = rows[row_refs[0]]
                        models.Cell.objects.create(
                            column=columns[columnn_ref],
                            row=row,
                            price_group=price_group_prices[price_ref.attrib["ref"]],
                            distance_matrix_element=distance_matrix_elements[distance_matrix_element_ref.attrib["ref"]]
                        )

                sales_offer_package_ref = sub_fare_table_element.find("pricesFor/SalesOfferPackageRef")
                if sales_offer_package_ref is not None:
                    sales_offer_package_ref = sales_offer_package_ref.attrib["ref"]
                    sales_offer_package = sales_offer_packages[sales_offer_package_ref]
                else:
                    sales_offer_package = None

                if sub_fare_table_element.find("includes"):
                    for sub_sub_fare_table_element in sub_fare_table_element.find("includes"):
                        subl_sub_fare_table, created = models.FareTable.objects.update_or_create(
                            {
                                "sales_offer_package": sales_offer_package,
                                "description": sub_fare_table_element.findtext("Description", "")
                            },
                            tariff=tariff,
                            code=sub_fare_table_element.attrib["id"],
                            name=sub_fare_table_element.findtext("Name", "")
                        )
                        if not created:
                            subl_sub_fare_table.column_set.all().delete()
                            subl_sub_fare_table.row_set.all().delete()

                        columns = {}
                        columns_element = sub_sub_fare_table_element.find('columns')
                        if columns_element:
                            for column in columns_element:
                                column = models.Column.objects.create(
                                    table=subl_sub_fare_table,
                                    code=column.attrib['id'],
                                    name=column.findtext('Name'),
                                    order=column.attrib.get('order')
                                )
                                columns[column.code] = column

                        rows = {}
                        rows_element = sub_sub_fare_table_element.find('rows')
                        if rows_element:
                            for row in rows_element:
                                row = models.Row.objects.create(
                                    table=subl_sub_fare_table,
                                    code=row.attrib['id'],
                                    name=row.findtext('Name'),
                                    order=row.attrib.get('order')
                                )
                                rows[row.code] = row

                        cells_element = sub_sub_fare_table_element.find('cells')
                        if cells_element:
                            for cell_element in cells_element:
                                columnn_ref = cell_element.find('ColumnRef').attrib['ref']
                                row_ref = cell_element.find('RowRef').attrib['ref']
                                time_interval_price = cell_element.find("TimeIntervalPrice")
                                if time_interval_price:
                                    time_interval_ref = time_interval_price.find("TimeIntervalRef").attrib['ref']
                                    time_interval_price, created = models.TimeIntervalPrice.objects.get_or_create(
                                        code=time_interval_price.attrib["id"],
                                        amount=time_interval_price.findtext("Amount"),
                                        time_interval=time_intervals[time_interval_ref]
                                    )
                                models.Cell.objects.create(
                                    column=columns[columnn_ref],
                                    row=rows[row_ref],
                                    time_interval_price=time_interval_price
                                )

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle_dataset(self, item):
        dataset_url = f"{self.base_url}/fares/dataset/{item['id']}/"
        modified = parse_datetime(item["modified"])
        try:
            dataset = models.DataSet.objects.get(url=dataset_url)
            if dataset.datetime == modified:
                return
            # has changed
            dataset.tariff_set.all().delete()
        except models.DataSet.DoesNotExist:
            dataset = models.DataSet(name=item["name"], description=item["description"], url=dataset_url)
            dataset.save()
        print(dataset_url)

        try:
            dataset.operators.set(item["noc"])
        except IntegrityError:
            print(item["noc"])

        download_url = f"{dataset_url}download/"
        response = self.session.get(download_url, stream=True)

        if response.headers['Content-Type'] == 'text/xml':
            # maybe not fully RFC 6266 compliant
            filename = response.headers['Content-Disposition'].split('filename', 1)[1][2:-1]
            print(filename)
            try:
                self.handle_file(dataset, response.raw, filename)
            except AttributeError as e:
                logger.error(e, exc_info=True)
                return
        else:
            assert response.headers['Content-Type'] == 'application/zip'
            with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                for filename in archive.namelist():
                    print(' ', filename)
                    try:
                        self.handle_file(dataset, archive.open(filename), filename)
                    except AttributeError as e:
                        logger.error(e, exc_info=True)
                        return

        dataset.datetime = modified
        dataset.save(update_fields=["datetime"])

    def handle(self, api_key=None, **kwargs):
        # url = 'https://data.bus-data.dft.gov.uk/fares/download/bulk_archive'

        # with requests.get(url, stream=True) as response:
        #     # maybe not fully RFC 6266 compliant
        #     filename = response.headers['Content-Disposition'].split('filename', 1)[1][2:-1]

        #     if not os.path.exists(filename):
        #         write_file(filename, response)

        # print(filename)

        # with zipfile.ZipFile(filename) as archive:
        #     for filename in archive.namelist():
        #         print(' ', filename)
        #         # try:
        #         #     self.handle_file(dataset, archive.open(filename))
        #         # except AttributeError as e:
        #         #     logger.error(e, exc_info=True)

        # return

        self.session = requests.Session()

        url = f"{self.base_url}/api/v1/fares/dataset/"
        params = {
            'api_key': api_key,
            'status': 'published'
        }
        while url:
            print(url)
            response = self.session.get(url, params=params)

            data = response.json()

            for item in data['results']:
                self.handle_dataset(item)

            url = data['next']
            params = None
