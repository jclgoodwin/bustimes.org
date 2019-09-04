from freezegun import freeze_time
from django.test import TestCase
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from busstops.models import DataSource, Region, Operator, Service
from .models import Vehicle, VehicleType, VehicleFeature, Livery, VehicleJourney, VehicleLocation, VehicleEdit
from .siri_et import siri_et
from . import admin


class VehiclesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.datetime = '2018-12-25 19:47+00:00'

        source = DataSource.objects.create(name='HP', datetime=cls.datetime)

        ea = Region.objects.create(id='EA', name='East Anglia')

        Operator.objects.create(region=ea, name='Bova and Over', id='BOVA', slug='bova-and-over')
        lynx = Operator.objects.create(region=ea, name='Lynx', id='LYNX', slug='lynx')

        tempo = VehicleType.objects.create(name='Optare Tempo', coach=False, double_decker=False)
        spectra = VehicleType.objects.create(name='Optare Spectra', coach=False, double_decker=True)

        service = Service.objects.create(service_code='49', region=ea, date='2018-12-25', tracking=True,
                                         description='Spixworth - Hunworth - Happisburgh')
        service.operator.add(lynx)

        cls.vehicle_1 = Vehicle.objects.create(code='2', fleet_number=1, reg='FD54JYA', vehicle_type=tempo,
                                               colours='#FF0000', notes='Trent Barton', operator=lynx)
        livery = Livery.objects.create(colours='#FF0000 #0000FF')
        cls.vehicle_2 = Vehicle.objects.create(code='50', fleet_number=50, reg='UWW2X', livery=livery,
                                               vehicle_type=spectra, operator=lynx)

        journey = VehicleJourney.objects.create(vehicle=cls.vehicle_1, datetime=cls.datetime, source=source,
                                                service=service, route_name='2')

        location = VehicleLocation.objects.create(datetime=cls.datetime, latlong=Point(0, 51),
                                                  journey=journey)
        cls.vehicle_1.latest_location = location
        cls.vehicle_1.save()

    def test_vehicle(self):
        vehicle = Vehicle(reg='3990ME')
        self.assertEqual(str(vehicle), '3990\xa0ME')
        self.assertIn('search/?text=3990ME%20or%20%223990%20ME%22&sort', vehicle.get_flickr_url())

        vehicle.reg = 'J122018'
        self.assertEqual(str(vehicle), 'J122018')

        vehicle = Vehicle(code='RML2604')
        self.assertIn('search/?text=RML2604&sort', vehicle.get_flickr_url())

        vehicle.operator = Operator(name='Lynx')
        self.assertIn('search/?text=Lynx%20RML2604&sort', vehicle.get_flickr_url())

        vehicle.operator.name = 'Stagecoach Oxenholme'
        self.assertIn('search/?text=Stagecoach%20RML2604&sort', vehicle.get_flickr_url())

    def test_vehicle_views(self):
        with self.assertNumQueries(2):
            response = self.client.get('/operators/bova-and-over/vehicles')
        self.assertEqual(404, response.status_code)
        self.assertFalse(str(response.context['exception']))

        with self.assertNumQueries(3):
            response = self.client.get('/operators/lynx/vehicles')
        self.assertTrue(response.context['code_column'])
        self.assertContains(response, '<td>2</td>')

        with self.assertNumQueries(6):
            response = self.client.get(self.vehicle_1.get_absolute_url() + '?date=poop')
        self.assertContains(response, 'Optare Tempo')
        self.assertContains(response, 'Trent Barton')
        self.assertContains(response, '#FF0000')

        with self.assertNumQueries(2):
            response = self.client.get(self.vehicle_2.get_absolute_url())
        self.assertEqual(404, response.status_code)
        self.assertFalse(str(response.context['exception']))

        with self.assertNumQueries(1):
            response = self.client.get('/journeys/1.json')
        self.assertEqual([], response.json())

    def test_feature(self):
        self.assertEqual('Wi-Fi', str(VehicleFeature(name='Wi-Fi')))

    def test_livery(self):
        livery = Livery(name='Go-Coach')
        self.assertEqual('Go-Coach', str(livery))
        self.assertIsNone(livery.preview())

        livery.colours = '#7D287D #FDEE00 #FDEE00'
        livery.horizontal = True
        self.assertEqual('<div style="height:1.5em;width:4em;background:linear-gradient' +
                         '(to top,#7D287D 34%,#FDEE00 34%)" title="Go-Coach"></div>', livery.preview())
        livery.horizontal = False
        livery.angle = 45
        self.assertEqual('linear-gradient(45deg,#7D287D 34%,#FDEE00 34%)', livery.get_css())
        self.assertEqual('linear-gradient(315deg,#7D287D 34%,#FDEE00 34%)', livery.get_css(10))
        self.assertEqual('linear-gradient(45deg,#7D287D 34%,#FDEE00 34%)', livery.get_css(300))

        livery.angle = None
        self.vehicle_1.livery = livery
        self.assertEqual('linear-gradient(to left,#7D287D 34%,#FDEE00 34%)',
                         self.vehicle_1.get_livery(179))
        self.assertIsNone(self.vehicle_1.get_text_colour())

        self.vehicle_1.livery.colours = '#c0c0c0'
        self.assertEqual('#c0c0c0', self.vehicle_1.get_livery(200))

        livery.css = 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)'
        self.assertEqual(livery.get_css(), 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(0), 'linear-gradient(315deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(10), 'linear-gradient(315deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(180), 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')
        self.assertEqual(livery.get_css(181), 'linear-gradient(45deg,#ED1B23 35%,#fff 35%,#fff 45%,#ED1B23 45%)')

    def test_vehicle_edit_1(self):
        url = self.vehicle_1.get_absolute_url() + '/edit'

        with self.assertNumQueries(7):
            response = self.client.get(url)
        self.assertNotContains(response, 'already')

        with self.assertNumQueries(8):
            response = self.client.post(url, {
                'fleet_number': '1',
                'reg': 'FD54JYA',
                'vehicle_type': self.vehicle_1.vehicle_type_id,
                'colours': '#FF0000',
                'notes': 'Trent Barton'
            })
        self.assertFalse(response.context['form'].has_changed())

    def test_vehicle_edit_2(self):
        url = self.vehicle_2.get_absolute_url() + '/edit'

        with self.assertNumQueries(8):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': 'UWW2X',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'colours': self.vehicle_2.livery_id,
                'notes': ''
            })
        self.assertTrue(response.context['form'].fields['fleet_number'].disabled)
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        self.assertEqual(0, VehicleEdit.objects.count())

        with self.assertNumQueries(7):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': '',
                'vehicle_type': self.vehicle_2.vehicle_type_id,
                'colours': self.vehicle_2.livery_id,
                'notes': 'Ex Ipswich Buses'
            })
        self.assertContains(response, 'Thank you')
        self.assertTrue(response.context['form'].has_changed())

        with self.assertNumQueries(7):
            response = self.client.get(url)

        self.assertContains(response, 'already')

        edit = VehicleEdit.objects.get()
        self.assertEqual(edit.get_changes(), {'notes': 'Ex Ipswich Buses', 'reg': '-UWW2X'})

        self.assertEqual('50 - UWW\xa02X', str(edit))
        self.assertEqual(self.vehicle_2.get_absolute_url(), edit.get_absolute_url())

        self.assertTrue(admin.VehicleEditAdmin.flickr(None, edit))
        self.assertEqual(admin.fleet_number(edit), '50')
        self.assertEqual(admin.reg(edit), '<del>UWW2X</del>')
        self.assertEqual(admin.notes(edit), '<ins>Ex Ipswich Buses</ins>')

        self.assertEqual(str(admin.vehicle_type(edit)), 'Optare Spectra')
        edit.vehicle_type = 'Ford Transit'
        self.assertEqual(str(admin.vehicle_type(edit)), '<del>Optare Spectra</del><br><ins>Ford Transit</ins>')
        edit.vehicle.vehicle_type = None
        self.assertEqual(admin.vehicle_type(edit), '<ins>Ford Transit</ins>')

    def test_vehicles_edit(self):
        with self.assertNumQueries(8):
            response = self.client.post('/operators/lynx/vehicles/edit')
        self.assertContains(response, 'Select vehicles to update')
        self.assertFalse(VehicleEdit.objects.all())

        with self.assertNumQueries(9):
            response = self.client.post('/operators/lynx/vehicles/edit', {
                'vehicle': self.vehicle_1.id,
                'notes': 'foo'
            })
        self.assertContains(response, 'Thank you')
        self.assertContains(response, '(1 vehicle) shortly')
        edit = VehicleEdit.objects.get()
        self.assertEqual(edit.vehicle_type, '')
        self.assertEqual(edit.notes, 'foo')

    def test_vehicles_json(self):
        with freeze_time(self.datetime):
            with self.assertNumQueries(1):
                response = self.client.get('/vehicles.json?ymax=52&xmax=2&ymin=51&xmin=1')
            self.assertEqual(200, response.status_code)
            self.assertEqual({'type': 'FeatureCollection', 'features': []}, response.json())
            self.assertIsNone(response.get('last-modified'))

            with self.assertNumQueries(2):
                response = self.client.get('/vehicles.json')
            features = response.json()['features']
            self.assertEqual(features[0]['properties']['vehicle']['name'], '1 - FD54\xa0JYA')
            self.assertEqual(features[0]['properties']['service'],
                             {'line_name': '', 'url': '/services/spixworth-hunworth-happisburgh'})

            self.assertEqual(response.get('last-modified'), 'Tue, 25 Dec 2018 19:47:00 GMT')

            VehicleJourney.objects.update(service=None)
            with self.assertNumQueries(2):
                response = self.client.get('/vehicles.json')
            features = response.json()['features']
            self.assertEqual(features[0]['properties']['vehicle']['name'], '1 - FD54\xa0JYA')
            self.assertEqual(features[0]['properties']['service'], {'line_name': '2'})

    def test_location_json(self):
        location = VehicleLocation.objects.get()
        location.journey.vehicle = self.vehicle_2
        properties = location.get_json()['properties']
        vehicle = properties['vehicle']
        self.assertEqual(vehicle['name'], '50 - UWW\xa02X')
        self.assertEqual(vehicle['text_colour'], '#fff')
        self.assertFalse(vehicle['coach'])
        self.assertTrue(vehicle['decker'])
        self.assertEqual(vehicle['livery'], 'linear-gradient(to right,#FF0000 50%,#0000FF 50%)')
        self.assertNotIn('type', vehicle)
        self.assertNotIn('operator', properties)

        properties = location.get_json(True)['properties']
        vehicle = properties['vehicle']
        self.assertEqual(vehicle['type'], 'Optare Spectra')
        self.assertNotIn('decker', vehicle)
        self.assertNotIn('coach', vehicle)
        self.assertNotIn('operator', vehicle)
        self.assertEqual(properties['operator'], 'Lynx')

    def test_validation(self):
        vehicle = Vehicle(colours='ploop')
        with self.assertRaises(ValidationError):
            vehicle.clean()

        vehicle.colours = ''
        vehicle.clean()

    def test_big_map(self):
        with self.assertNumQueries(0):
            response = self.client.get('/vehicles')
        self.assertContains(response, 'bigmap.min.js')

    def test_dashboard(self):
        with self.assertNumQueries(2):
            response = self.client.get('/vehicle-tracking-report')
        self.assertContains(response, 'Vehicle tracking report')
        self.assertContains(response, '<a href="/services/spixworth-hunworth-happisburgh/vehicles">Yes</a>*')

    def test_siri_et(self):
        xml = """<?xml version="1.0" encoding="utf-8" ?>
<Siri xmlns:ns1="http://www.siri.org.uk/siri" xmlns="http://www.siri.org.uk/siri"
xmlns:xml="http://www.w3.org/XML/1998/namespace" version="1.3">
 <ServiceDelivery>
   <ResponseTimestamp>2019-09-02T16:36:40+01:00</ResponseTimestamp>
   <ProducerRef>HAConTest</ProducerRef>
   <MoreData>false</MoreData>
   <EstimatedTimetableDelivery version="1.3">
     <ResponseTimestamp>2019-09-02T16:36:39+01:00</ResponseTimestamp>
     <SubscriberRef>HAConToBusTimesET</SubscriberRef>
     <SubscriptionRef>HAConToBusTimesET</SubscriptionRef>
     <Status>true</Status>
     <ValidUntil>2019-09-02T17:17:08+01:00</ValidUntil>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>37</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_F0371039</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">37</PublishedLineName>
         <DirectionName xml:lang="EN">Winsford Guildhall</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2934</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>0600CR372</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Winterley Pool</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0600CR375</StopPointRef>
             <VisitNumber>18</VisitNumber>
             <StopPointName xml:lang="EN">Wheelock Heath Foresters Arms PH</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0600CO053</StopPointRef>
             <VisitNumber>20</VisitNumber>
             <StopPointName xml:lang="EN">Wheelock Crewe Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">o/s 597</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">o/s 597</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0600CO069</StopPointRef>
             <VisitNumber>27</VisitNumber>
             <StopPointName xml:lang="EN">Sandbach Common</StopPointName>
             <AimedArrivalTime>2019-09-02T16:45:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:48:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>500</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_500_1086</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">500</PublishedLineName>
         <DirectionName xml:lang="EN">Murdishaw Cen.</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-5017</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>068000000142</StopPointRef>
             <VisitNumber>64</VisitNumber>
             <StopPointName xml:lang="EN">Ditton Crossway</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>110</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_N1101083</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">110</PublishedLineName>
         <DirectionName xml:lang="EN">Warrington Bus Interchange</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-5006</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>069000023592</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Cuerdley Cross Golf Centre</StopPointName>
             <AimedArrivalTime>2019-09-02T16:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0690WNA02877</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Doe Green Tannery Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0690WNA02861</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">Warrington Bus Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
   </EstimatedTimetableDelivery>
 </ServiceDelivery>
</Siri>
        """

        DataSource.objects.create(name='Arriva')
        Operator.objects.create(region_id='EA', id='ANWE')

        siri_et(xml)

        self.assertFalse(self.client.get('/siri').content)

        self.assertIsNone(DataSource.objects.get(name='Arriva').datetime)

        response = self.client.post('/siri', 'HeartbeatNotification>', content_type='text/xml')
        self.assertTrue(response.content)
        self.assertTrue(DataSource.objects.get(name='Arriva').datetime)
