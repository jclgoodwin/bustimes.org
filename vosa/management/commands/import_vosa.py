# from titlecase import titlecase
import os
import csv
from datetime import datetime
from django.conf import settings
from django.core.management import BaseCommand
from bustimes.utils import download_if_changed
from ...models import Licence, Registration  # , Variation


def parse_date(date_string):
    if date_string:
        return datetime.strptime(date_string, '%d/%m/%y').date()


def download_if_modified(path):
    url = f"https://content.mgmt.dvsacloud.uk/olcs.prod.dvsa.aws/data-gov-uk-export/{path}"
    path = os.path.join(settings.DATA_DIR, path)
    return download_if_changed(path, url)


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        regions = "FBCMKGDH"
        for region in regions:
            modified, last_modified = download_if_modified(f"Bus_RegisteredOnly_{region}.csv")
            self.handle_registered(region)
            # print(modified, last_modified)
            modified, last_modified = download_if_modified(f"Bus_Variation_{region}.csv")
            # print(modified, last_modified)
            # self.handle_variations(region)

    def handle_registered(self, region):
        path = os.path.join(settings.DATA_DIR, f"Bus_RegisteredOnly_{region}.csv")

        licences = Licence.objects.filter(traffic_area=region)
        licences = licences.in_bulk(field_name="licence_number")
        licences_to_update = []
        licences_to_create = []

        registrations = Registration.objects.filter(registration_number__startswith=f"P{region}")
        registrations = registrations.in_bulk(field_name="registration_number")
        to_update = []
        to_create = []
        with open(path) as open_file:
            previous_line = None
            cardinals = set()
            for line in csv.DictReader(open_file):
                reg_no = line["Reg_No"]
                assert reg_no.startswith(f"P{region}")
                if previous_line and previous_line["Reg_No"] == reg_no:
                    for key in line:
                        if line[key] != previous_line[key]:
                            cardinals.add(key)
                previous_line = line

                if reg_no in registrations:
                    registration = registrations[reg_no]
                    if registration not in to_update:
                        to_update.append(registration)
                else:
                    registration = Registration(
                        registration_number=reg_no,
                    )
                    to_create.append(registration)
                    registrations[reg_no] = registration

                lic_no = line["Lic_No"]
                if lic_no in licences:
                    licence = licences[lic_no]
                    if licence not in licences_to_update:
                        licences_to_update.append(licence)
                else:
                    licence = Licence(licence_number=lic_no)
                    licences_to_create.append(licence)
                    licences[lic_no] = licence

                licence.name = line['Op_Name']
                licence.trading_name = line['trading_name']
                licence.address = line['Address']
                licence.traffic_area = line['Current Traffic Area']
                licence.discs = line['Discs in Possession'] or 0
                licence.authorised_discs = line['AUTHDISCS'] or 0
                licence.description = line['Description']
                licence.granted_date = parse_date(line['Granted_Date'])
                licence.expiry_date = parse_date(line['Exp_Date'])
                registration.licence = licence

                registration.start_point = line['start_point']
                registration.finish_point = line['finish_point']
                registration.via = line['via']
                registration.subsidies_description = line['Subsidies_Description']
                registration.subsidies_details = line['Subsidies_Details']
                registration.traffic_area_office_covered_by_area = line['TAO Covered BY Area']
                registration.service_number = line['Service Number']
                registration.service_type_description = line['Service_Type_Description']
                registration.registration_status = line['Registration Status']

        print(len(licences_to_create))
        print(len(licences_to_update))
        Licence.objects.bulk_create(licences_to_create)
        Licence.objects.bulk_update(
            licences_to_update,
            ["name", "trading_name", "traffic_area", "licence_number", "discs", "authorised_discs", "description",
             "granted_date", "expiry_date", "address"]
        )

        for registration in to_create:
            registration.licence = registration.licence

        Registration.objects.bulk_create(to_create)
        Registration.objects.bulk_update(
            to_update,
            ["start_point", "finish_point", "via",
             "subsidies_description", "subsidies_details", "traffic_area_office_covered_by_area",
             "service_number", "service_type_description", "registration_status"]
        )

    # def handle_variations(region):
    #     path = os.path.join(settings.DATA_DIR, f"Bus_Variation_{region}.csv")

    # def handle_variation(self, row):
    #     defaults = {
    #         'granted_date': parse_date(row['Granted_Date']),
    #         'expiry_date': parse_date(row['Exp_Date']),
    #         'effective_date': parse_date(row['effective_date']),
    #         'date_received': parse_date(row['received_date']),
    #         'end_date': parse_date(row['end_date']),
    #         'service_type_other_details': row['Service_Type_Other_Details'],
    #         'registration_status': row['Registration Status'],
    #         'publication_text': row['Pub_Text'],
    #         'short_notice': row['Short Notice'],
    #         'authority_description': row['Auth_Description'],
    #     }
    #     variation, created = Variation.objects.get_or_create(defaults, registration=self.registration,
    #                                                          variation_number=row['Variation Number'])
    #     if not created:
    #         maybe_update(variation, defaults)

    # def handle_row(self, row):
    #     if len(row['Reg_No']) > 20 and row['Reg_No'].count('/'):
    #         parts = row['Reg_No'].split('/')
    #         if parts[0] == parts[1]:
    #             row['Reg_No'] = '/'.join(parts[1:])

    #     for key in ('start_point', 'finish_point', 'via'):
    #         if row[key].isupper() or row[key].islower():
    #             row[key] = titlecase(row[key])

    #     if not self.licence or self.licence.licence_number != row['Lic_No']:
    #         self.handle_licence(row)

    #     self.handle_registration(row)

    #     self.handle_variation(row)

    #     self.previous_row = row
