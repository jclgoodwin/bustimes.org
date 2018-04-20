# import requests
# from titlecase import titlecase
# from django.core.exceptions import MultipleObjectsReturned
from datetime import datetime
from ..import_from_csv import ImportFromCSVCommand
from ...models import Variation


def parse_date(date_string):
    if date_string:
        return datetime.strptime(date_string, '%d/%m/%y').date()


class Command(ImportFromCSVCommand):
    def handle_row(self, row):
        print(row)
        Variation.objects.update_or_create(
            {
                'discs': row['Discs in Possession'] or 0,
                'authorised_discs': row['AUTHDISCS'] or 0,
                'granted_date': parse_date(row['Granted_Date']),
                'expiry_date': parse_date(row['Exp_Date']),
                'description': row['Description'],
                # 'operator': row['Op_ID'],
                'start_point': row['start_point'],
                'finish_point': row['finish_point'],
                'via': row['via'],
                'effective_date': parse_date(row['effective_date']),
                'date_received': parse_date(row['received_date']),
                'end_date': parse_date(row['end_date']),
                'service_type_other_details': row['Service_Type_Other_Details'],
                'licence_status': row['Licence Status'],
                'registration_status': row['Registration Status'],
                'publication_text': row['Pub_Text'],
                'service_type_description': row['Service_Type_Description'],
                'short_notice': row['Short Notice'],
                'subsidies_description': row['Subsidies_Description'],
                'subsidies_details': row['Subsidies_Details'],
                'traffic_area_office_covered_by_area': row['TAO Covered BY Area'],
            },
            registration_number=row['Reg_No'],
            variation_number=row['Variation Number'],
            service_number=row['Service Number'],
            traffic_area=row['Current Traffic Area'],
            licence_number=row['Lic_No'],
            authoritiy_description=row['Auth_Description']
        )
