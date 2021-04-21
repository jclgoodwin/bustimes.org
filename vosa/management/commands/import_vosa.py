# from titlecase import titlecase
import os
import csv
from datetime import datetime
from django.conf import settings
from django.core.management import BaseCommand
from bustimes.utils import download_if_changed
from ...models import Licence, Registration, Variation


def parse_date(date_string):
    if date_string:
        return datetime.strptime(date_string, '%d/%m/%y').date()


def download_if_modified(path):
    url = f"https://content.mgmt.dvsacloud.uk/olcs.prod.dvsa.aws/data-gov-uk-export/{path}"
    path = os.path.join(settings.DATA_DIR, path)
    return download_if_changed(path, url)


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('regions', nargs='?', type=str, default="FBCMKGDH")

    def get_rows(self, path):
        path = os.path.join(settings.DATA_DIR, path)
        with open(path) as open_file:
            for line in csv.DictReader(open_file):
                yield line

    def handle(self, regions, **kwargs):
        for region in regions:
            # modified, last_modified = download_if_modified(f"Bus_RegisteredOnly_{region}.csv")
            # print(modified, last_modified)
            # modified, last_modified = download_if_modified(f"Bus_Variation_{region}.csv")
            # print(modified, last_modified)
            self.handle_region(region)

    def handle_region(self, region):
        lics = Licence.objects.filter(traffic_area=region)
        lics = lics.in_bulk(field_name="licence_number")
        lics_to_update = []
        lics_to_create = []

        regs = Registration.objects.filter(registration_number__startswith=f"P{region}")
        regs = regs.in_bulk(field_name="registration_number")
        regs_to_update = []
        regs_to_create = []

        variations = Variation.objects.filter(registration__registration_number__startswith=f"P{region}")
        variations = variations.select_related('registration').all()
        variations_dict = {}
        for variation in variations:
            if variation.registration.registration_number in variations_dict:
                variations_dict[variation.registration.registration_number][variation.variation_number] = variation
            else:
                variations_dict[variation.registration.registration_number] = {variation.variation_number: variation}

        vars_to_create = []
        vars_to_update = []

        previous_line = None
        cardinals = set()

        for line in self.get_rows(f"Bus_Variation_{region}.csv"):
            reg_no = line["Reg_No"]
            var_no = int(line["Variation Number"])

            lic_no = line["Lic_No"]

            if lic_no in lics:
                licence = lics[lic_no]
                if licence.id and licence not in lics_to_update:
                    licence.trading_name = ''
                    lics_to_update.append(licence)
            else:
                licence = Licence(licence_number=lic_no)
                lics_to_create.append(licence)
                lics[lic_no] = licence

            licence.name = line['Op_Name']

            if line['trading_name'] not in licence.trading_name:
                if licence.trading_name:
                    licence.trading_name = f"{licence.trading_name}\n{line['trading_name']}"
                else:
                    licence.trading_name = line['trading_name']

            licence.address = line['Address']
            licence.traffic_area = line['Current Traffic Area']
            licence.discs = line['Discs in Possession'] or 0
            licence.authorised_discs = line['AUTHDISCS'] or 0
            licence.description = line['Description']
            licence.granted_date = parse_date(line['Granted_Date'])
            licence.expiry_date = parse_date(line['Exp_Date'])

            if reg_no in regs:
                registration = regs[reg_no]
                if registration.id and registration not in regs_to_update:
                    regs_to_update.append(registration)
            else:
                registration = Registration(
                    registration_number=reg_no,
                )
                regs_to_create.append(registration)
                regs[reg_no] = registration
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

            # if previous_line:
            #     if previous_line["Reg_No"] == reg_no:
            #         if int(previous_line["Variation Number"]) == var_no:
            #             for key in line:
            #                 prev = previous_line[key]
            #                 value = line[key]
            #                 if prev != value:
            #                     # print(line, previous_line)
            #                     # if key not in (
            #                     #     'Service_Type_Description', 'Auth_Description', 'TAO Covered BY Area',
            #                     #     'trading_name', 'Pub_Text', 'Registration Status', 'end_date', 'received_date'
            #                     # ):
            #                     #     print(key, prev, value)
            #                     cardinals.add(key)

            if reg_no not in regs:
                registration = Registration(
                    registration_number=reg_no,
                )

                variation = Variation(registration=regs[reg_no], variation_number=var_no)
                if reg_no in variations_dict:
                    if var_no in variations_dict[reg_no]:
                        continue
                    else:
                        variations_dict[reg_no][var_no] = variation
                else:
                    variation = Variation(registration=regs[reg_no], variation_number=var_no)
                    variations_dict[reg_no] = {var_no: variation}

                variation.effective_date = parse_date(line['effective_date'])
                variation.date_received = parse_date(line['received_date'])
                variation.end_date = parse_date(line['end_date'])
                variation.service_type_other_details = line['Service_Type_Other_Details']
                variation.registration_status = line['Registration Status']
                variation.publication_text = line['Pub_Text']
                variation.short_notice = line['Short Notice']
                variation.authority_description = line['Auth_Description']

                if not variation.id:
                    vars_to_create.append(variation)
            # previous_line = line

        print(len(lics_to_create))
        print(len(lics_to_update))
        Licence.objects.bulk_update(
            lics_to_update,
            ["name", "trading_name", "traffic_area", "licence_number", "discs", "authorised_discs", "description",
             "granted_date", "expiry_date", "address"]
        )
        Licence.objects.bulk_create(lics_to_create)

        # print(cardinals)

        # previous_line = None
        # cardinals = set()

        # for line in self.get_rows(f"Bus_RegisteredOnly_{region}.csv"):
        #     reg_no = line["Reg_No"]

        #     if previous_line and previous_line["Reg_No"] == reg_no:
        #         for key in line:
        #             prev = previous_line[key]
        #             value = line[key]
        #             if prev != value:
        #                 cardinals.add(key)

        #     previous_line = line

        # print(cardinals)

        for registration in regs_to_create:
            registration.licence = registration.licence

        Registration.objects.bulk_update(
            regs_to_update,
            ["start_point", "finish_point", "via",
             "subsidies_description", "subsidies_details", "traffic_area_office_covered_by_area",
             "service_number", "service_type_description", "registration_status"]
        )
        Registration.objects.bulk_create(regs_to_create)

        Variation.objects.bulk_create(vars_to_create)
        Variation.objects.bulk_update(
            vars_to_update,
            ['date_received', 'end_date', 'service_type_other_details', 'registration_status', 'publication_text',
             'short_notice', 'authority_description'])
