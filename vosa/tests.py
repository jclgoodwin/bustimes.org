import os
from django.test import TestCase
from .management.commands import import_variations


class VariationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        command = import_variations.Command()

        data = {
            'Reg_No': 'PH1020951/PH1020951/284',
            'Variation Number': '0',
            'Service Number': '122',
            'Current Traffic Area': 'H',
            'Lic_No': 'PH1020951',
            'Discs in Possession': '475',
            'AUTHDISCS': '475',
            'Granted_Date': '18/06/03',
            'Exp_Date': '31/05/18',
            'Description': 'Standard National',
            'Op_ID': '161105',
            'Op_Name': 'STAGECOACH DEVON LTD',
            'trading_name': 'STAGECOACH SOUTH WEST',
            'Address': 'Matford Park Depot, Stagecoach South West, Matford Park Road, Exeter, EX2 8FD, GB',
            'start_point': 'St Marychurch',
            'finish_point': 'Paignton Zoo',
            'via': '',
            'effective_date': '29/04/17',
            'received_date': '03/03/17',
            'end_date': '',
            'Service_Type_Other_Details': 'Daily Service Every Twenty Minutes',
            'Licence Status': 'Valid',
            'Registration Status': 'Registered',
            'Pub_Text': """From: St Marychurch
To: Paignton Zoo
Via:
Name or No.: 122 / 122
Service type: Normal Stopping
Effective date: 29 April 2017
Other details: Daily Service Every Twenty Minutes""",
            'Service_Type_Description': 'Normal Stopping',
            'Short Notice': 'No',
            'Subsidies_Description': 'No',
            'Subsidies_Details': '',
            'Auth_Description': 'Torbay Borough Council',
            'TAO Covered BY Area': 'West of England',
            'reg_code': '284'
        }
        command.handle_row(data)

    def test_licence_view(self):
        response = self.client.get('/licences/PH1020951')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<a href="/registrations/PH1020951/284">')

    def test_beestons(self):
        command = import_variations.Command()
        command.input = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'Bus_Variation_F.csv')

        with self.assertNumQueries(296):
            command.handle()
        with self.assertNumQueries(142):
            command.handle()

        response = self.client.get('/licences/PF0000003')
        self.assertEqual(2, len(response.context_data['registrations']))
        self.assertEqual(10, len(response.context_data['cancelled']))

    def test_licence_rss(self):
        response = self.client.get('/licences/PH1020951/rss')
        self.assertEqual(response.status_code, 200)

    def test_licence_404(self):
        response = self.client.get('/licences/PH102095')
        self.assertEqual(response.status_code, 404)

    def test_registration_view(self):
        response = self.client.get('/registrations/PH1020951/284')
        self.assertEqual(response.status_code, 200)

    def test_registration_404(self):
        response = self.client.get('/registrations/PH1020951/d')
        self.assertEqual(response.status_code, 404)
