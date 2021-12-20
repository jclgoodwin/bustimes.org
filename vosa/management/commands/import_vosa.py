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
    return download_if_changed(settings.DATA_DIR / path, url)


class Command(BaseCommand):
    @staticmethod
    def add_arguments(parser):
        parser.add_argument('regions', nargs='?', type=str, default="FBCMKGDH")

    def get_rows(self, path):
        with open(settings.DATA_DIR / path) as open_file:
            yield from csv.DictReader(open_file)

    def handle(self, regions, **kwargs):
        for region in regions:
            modified_1, last_modified_1 = download_if_modified(f"Bus_RegisteredOnly_{region}.csv")
            modified_2, last_modified_2 = download_if_modified(f"Bus_Variation_{region}.csv")
            if modified_1 or modified_2:
                print(region, last_modified_1, last_modified_2)
                self.handle_region(region)

    def handle_region(self, region):
        lics = Licence.objects.filter(traffic_area=region)
        lics = lics.in_bulk(field_name="licence_number")
        lics_to_update = set()
        lics_to_create = []

        regs = Registration.objects.filter(licence__traffic_area=region)
        regs = regs.in_bulk(field_name="registration_number")
        regs_to_update = set()
        regs_to_create = []

        variations = Variation.objects.filter(registration__licence__traffic_area=region)
        variations = variations.select_related('registration').all()
        variations_dict = {}
        for variation in variations:
            reg_no = variation.registration.registration_number
            if reg_no in variations_dict:
                variations_dict[reg_no][variation.variation_number] = variation
            else:
                variations_dict[reg_no] = {
                    variation.variation_number: variation
                }

        # vars_to_update = set()
        vars_to_create = []

        # previous_line = None
        # cardinals = set()

        for line in self.get_rows(f"Bus_Variation_{region}.csv"):
            reg_no = line["Reg_No"]
            var_no = int(line["Variation Number"])

            lic_no = line["Lic_No"]

            if lic_no in lics:
                licence = lics[lic_no]
                if licence.id and licence not in lics_to_update:
                    licence.trading_name = ''
                    lics_to_update.add(licence)
            else:
                licence = Licence(licence_number=lic_no)
                lics_to_create.append(licence)
                lics[lic_no] = licence

            licence.name = line['Op_Name']

            # a licence can have multiple trading names
            if line['trading_name'] not in licence.trading_name:
                if licence.trading_name:
                    licence.trading_name = f"{licence.trading_name}\n{line['trading_name']}"
                else:
                    licence.trading_name = line['trading_name']

            if licence.address != line['Address']:
                if licence.address:
                    print(licence.address, line['Address'])
                licence.address = line['Address']

            if licence.traffic_area:
                assert licence.traffic_area == line['Current Traffic Area']
            else:
                licence.traffic_area = line['Current Traffic Area']

            licence.discs = line['Discs in Possession'] or 0
            licence.authorised_discs = line['AUTHDISCS'] or 0
            licence.description = line['Description']
            licence.granted_date = parse_date(line['Granted_Date'])
            licence.expiry_date = parse_date(line['Exp_Date'])

            if len(reg_no) > 20:
                # PK0000098/PK0000098/364
                parts = reg_no.split('/')
                assert parts[0] == parts[1]
                reg_no = f'{parts[1]}/{parts[2]}'

            if reg_no in regs:
                registration = regs[reg_no]
                if registration.id and registration not in regs_to_update:
                    regs_to_update.add(registration)
            else:
                registration = Registration(
                    registration_number=reg_no,
                    registered=False
                )
                regs_to_create.append(registration)
                regs[reg_no] = registration
            registration.licence = licence

            status = line['Registration Status']
            registration.registration_status = status

            if var_no == 0 and status == 'New':
                registration.registered = True
            elif status == 'Registered':
                registration.registered = True
            elif status == 'Cancelled' or status == 'Admin Cancelled' or status == 'Cancellation':
                registration.registered = False

            registration.start_point = line['start_point']
            registration.finish_point = line['finish_point']
            registration.via = line['via']
            registration.subsidies_description = line['Subsidies_Description']
            registration.subsidies_details = line['Subsidies_Details']
            registration.traffic_area_office_covered_by_area = line['TAO Covered BY Area']

            # a registration can have multiple numbers
            if registration.service_number:
                if line['Service Number'] not in registration.service_number:
                    registration.service_number = f"{registration.service_number}\n{line['Service Number']}"
            else:
                registration.service_number = line['Service Number']

            # a registration can have multiple types
            if registration.service_type_description:
                if line['Service_Type_Description'] not in registration.service_type_description:
                    registration.service_type_description += f"\n{line['Service_Type_Description']}"
            else:
                registration.service_type_description = line['Service_Type_Description']

            if registration.authority_description:
                if line['Auth_Description'] not in registration.authority_description:
                    registration.authority_description += f"\n{line['Auth_Description']}"
                    if len(registration.authority_description) > 255:
                        # some National Express coach services cover many authorities
                        # print(reg_no)
                        registration.authority_description = registration.authority_description[:255]
            else:
                registration.authority_description = line['Auth_Description']

            # if previous_line:
            #     if previous_line["Reg_No"] == reg_no:
            #         if int(previous_line["Variation Number"]) == var_no:
            #             for key in line:
            #                 prev = previous_line[key]
            #                 value = line[key]
            #                 if prev != value:
            #                     if key not in (
            #                         'Auth_Description', 'TAO Covered BY Area',
            #                         'trading_name', 'Pub_Text', 'Registration Status', 'end_date', 'received_date'
            #                         'effective_date', 'short_notice', 'Service_Type_Description'
            #                     ):
            #                         print(reg_no)
            #                         print(f"'{key}': '{prev}', '{value}'")
            #                         cardinals.add(key)
            #                         # print(line)

            variation = Variation(registration=registration, variation_number=var_no)
            if reg_no in variations_dict:
                if var_no in variations_dict[reg_no]:
                    continue  # ?
                else:
                    variations_dict[reg_no][var_no] = variation
            else:
                variations_dict[reg_no] = {var_no: variation}

            variation.effective_date = parse_date(line['effective_date'])
            variation.date_received = parse_date(line['received_date'])
            variation.end_date = parse_date(line['end_date'])
            variation.service_type_other_details = line['Service_Type_Other_Details']
            variation.registration_status = line['Registration Status']
            variation.publication_text = line['Pub_Text']
            variation.short_notice = line['Short Notice']

            assert not variation.id

            if not variation.id:
                vars_to_create.append(variation)

            # previous_line = line

        # previous_line = None
        # cardinals = set()

        # use this file to work out if a registration has not been cancelled/expired
        for line in self.get_rows(f"Bus_RegisteredOnly_{region}.csv"):
            reg_no = line["Reg_No"]
            reg = regs[reg_no]
            if reg.registration_status != line["Registration Status"]:
                reg.registration_status = line["Registration Status"]
            reg.registered = True

            # if previous_line and previous_line["Reg_No"] == reg_no:
            #     for key in line:
            #         prev = previous_line[key]
            #         value = line[key]
            #         if prev != value:
            #             cardinals.add(key)
            #             if key == 'TAO Covered BY Area':
            #                 print(prev, value)

        #     previous_line = line

        # print(cardinals)

        Licence.objects.bulk_update(
            lics_to_update,
            ["name", "trading_name", "traffic_area", "discs", "authorised_discs",
             "description", "granted_date", "expiry_date", "address"]
        )
        Licence.objects.bulk_create(lics_to_create)

        for registration in regs_to_create:
            registration.licence = registration.licence

        Registration.objects.bulk_update(
            regs_to_update,
            ["start_point", "finish_point", "via",
             "subsidies_description", "subsidies_details",
             "traffic_area_office_covered_by_area",
             "service_number", "service_type_description",
             "registration_status", "authority_description",
             "registered"],
            batch_size=1000
        )
        Registration.objects.bulk_create(regs_to_create)

        Variation.objects.bulk_create(vars_to_create)
        # Variation.objects.bulk_update(
        #     vars_to_update,
        #     ['date_received', 'end_date', 'service_type_other_details', 'registration_status', 'publication_text',
        #      'short_notice']
        # )
