import io
import xml.etree.cElementTree as ET
import requests
import zipfile
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from ... import models


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


class Command(BaseCommand):
    def handle_file(self, source, open_file):
        iterator = ET.iterparse(open_file)

        for _, element in iterator:
            if element.tag[:31] == '{http://www.netex.org.uk/netex}':
                element.tag = element.tag[31:]

        user_profiles = {}
        for usage_parameter in element.find("dataObjects/CompositeFrame/frames/FareFrame/usageParameters"):
            user_profile, created = get_user_profile(usage_parameter)
            user_profiles[user_profile.code] = user_profile

        sales_offer_packages = {}
        for sales_offer_package in element.find("dataObjects/CompositeFrame/frames/FareFrame/salesOfferPackages"):
            sales_offer_package, created = models.SalesOfferPackage.objects.get_or_create(
                code=sales_offer_package.attrib["id"],
                name=sales_offer_package.findtext("Name", ""),
                description=sales_offer_package.findtext("Description", "")
            )
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
                    code=fare_zone.attrib['id'], name=fare_zone.findtext("Name")
                )
                fare_zones[fare_zone.code] = fare_zone

        tariffs = {}
        distance_matrix_elements = {}
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
                source=source, trip_type=trip_type, user_profile=user_profile
            )

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

            tariffs[tariff.code] = tariff

        for fare_table_element in element.find("dataObjects/CompositeFrame/frames/FareFrame/fareTables"):
            tariff_ref = fare_table_element.find("usedIn/TariffRef")
            if tariff_ref is None:
                continue
            tariff_ref = tariff_ref.attrib["ref"]
            user_profile_ref = fare_table_element.find("pricesFor/UserProfileRef").attrib["ref"]
            if user_profile_ref not in user_profiles:
                user_profile_ref = f"fxc:{user_profile_ref}"
            sales_offer_package_ref = fare_table_element.find("pricesFor/SalesOfferPackageRef").attrib["ref"]
            table, created = models.FareTable.objects.update_or_create(
                {
                    "user_profile": user_profiles[user_profile_ref],
                    "sales_offer_package": sales_offer_packages[sales_offer_package_ref],
                    "description": fare_table_element.findtext("Description")
                },
                tariff=tariffs[tariff_ref],
                code=fare_table_element.attrib["id"],
                name=fare_table_element.findtext("Name")
            )

            if not created:
                table.column_set.all().delete()
                table.row_set.all().delete()

            columns = {}
            for column in fare_table_element.find('columns'):
                column = models.Column.objects.create(
                    table=table,
                    code=column.attrib['id'],
                    name=column.findtext('Name'),
                    order=column.attrib['order']
                )
                columns[column.code] = column

            rows = {}
            for row in fare_table_element.find('rows'):
                row = models.Row.objects.create(
                    table=table,
                    code=row.attrib['id'],
                    name=row.findtext('Name'),
                    order=row.attrib['order']
                )
                rows[row.code] = row

            for table in fare_table_element.find('includes'):
                for cell_element in table.find('cells'):
                    columnn_ref = cell_element.find('ColumnRef').attrib['ref']
                    row_ref = cell_element.find('RowRef').attrib['ref']
                    distance_matrix_element_price = cell_element.find("DistanceMatrixElementPrice")
                    price_ref = distance_matrix_element_price.find("GeographicalIntervalPriceRef")
                    distance_matrix_element_ref = distance_matrix_element_price.find("DistanceMatrixElementRef")

                    if row_ref in rows:
                        row = rows[row_ref]
                    else:
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

    @staticmethod
    def add_arguments(parser):
        parser.add_argument('api_key', type=str)

    def handle(self, api_key, **kwargs):
        session = requests.Session()

        url = 'https://data.bus-data.dft.gov.uk/api/v1/fares/dataset/'
        params = {
            'api_key': api_key,
            'status': 'published'
        }
        while url:
            response = session.get(url, params=params)
            data = response.json()

            for item in data['results']:
                dataset_url = f"https://data.bus-data.dft.gov.uk/fares/dataset/{item['id']}/"
                print(dataset_url)
                try:
                    dataset = models.DataSet.objects.get(url=dataset_url)
                    dataset.tariff_set.all().delete()
                except models.DataSet.DoesNotExist:
                    dataset = models.DataSet(name=item["name"], description=item["description"], url=dataset_url)
                    dataset.save()
                try:
                    dataset.operators.set(item["noc"])
                except IntegrityError:
                    print(item["noc"])
                download_url = f"{dataset_url}download/"
                response = session.get(download_url, stream=True)

                if response.headers['Content-Type'] == 'text/xml':
                    self.handle_file(dataset, response.raw)
                else:
                    assert response.headers['Content-Type'] == 'application/zip'
                    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                        for filename in archive.namelist():
                            print(' ', filename)
                            self.handle_file(dataset, archive.open(filename))

            url = data['next']
