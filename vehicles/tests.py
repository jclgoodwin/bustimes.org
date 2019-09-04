from freezegun import freeze_time
from django.test import TestCase
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from busstops.models import DataSource, Region, Operator, Service
from .models import Vehicle, VehicleType, VehicleFeature, Livery, VehicleJourney, VehicleLocation, VehicleEdit
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

        cls.vehicle_1 = Vehicle.objects.create(fleet_number=1, reg='FD54JYA', vehicle_type=tempo, colours='#FF0000',
                                               notes='Trent Barton', operator=lynx)
        livery = Livery.objects.create(colours='#FF0000 #0000FF')
        cls.vehicle_2 = Vehicle.objects.create(code='99', fleet_number=50, reg='UWW2X', livery=livery,
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
        self.assertContains(response, '<td>99</td>')

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

        self.vehicle_1.livery = livery
        self.vehicle_1.livery.horizontal = False
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
        self.assertFalse(response.context['form'].has_changed())
        self.assertNotContains(response, 'already')

        self.assertEqual(0, VehicleEdit.objects.count())

        with self.assertNumQueries(7):
            response = self.client.post(url, {
                'fleet_number': '50',
                'reg': 'UWW 2X',
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
        self.assertEqual('50 - UWW\xa02X', str(edit))
        self.assertEqual(self.vehicle_2.get_absolute_url(), edit.get_absolute_url())

        self.assertTrue(admin.VehicleEditAdmin.flickr(None, edit))
        self.assertEqual(admin.fleet_number(edit), '50')
        self.assertEqual(admin.reg(edit), 'UWW2X')
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

        with freeze_time(self.datetime):
            with self.assertNumQueries(2):
                response = self.client.get('/vehicles.json')
        vehicle = response.json()['features'][0]['properties']['vehicle']
        self.assertEqual(vehicle['name'], '1 - FD54\xa0JYA')
        self.assertEqual(response.get('last-modified'), 'Tue, 25 Dec 2018 19:47:00 GMT')

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
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>83</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_R0831817</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">83</PublishedLineName>
         <DirectionName xml:lang="EN">Rhyl Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-674</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>5110AWD72211</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Rhyl Trellewelyn Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5110AWA03914</StopPointRef>
             <VisitNumber>21</VisitNumber>
             <StopPointName xml:lang="EN">Rhyl Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Bay F</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>6</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ATS_80061080</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">6</PublishedLineName>
         <DirectionName xml:lang="EN">CMK &amp; Wolverton</DirectionName>
         <OperatorRef>ATS</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ATS-3614</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>049004305520</StopPointRef>
             <VisitNumber>27</VisitNumber>
             <StopPointName xml:lang="EN">Eaglestone Roundabout North</StopPointName>
             <AimedArrivalTime>2019-09-02T16:24:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:24:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003030901</StopPointRef>
             <VisitNumber>30</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Xscape</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:41:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A5</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:29:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:41:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A5</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003030949</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Theatre District</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003030953</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes The Point</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop J4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop J4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003020957</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Central Business Exchange</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:48:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop Q4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:48:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop Q4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003020961</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Santander House</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:50:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop W4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:50:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop W4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049000000919</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Central Railway Station</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop Z3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:43:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop Z3</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>5</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ATS_80051076</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">5</PublishedLineName>
         <DirectionName xml:lang="EN">CMK &amp; Wolverton</DirectionName>
         <OperatorRef>ATS</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ATS-3876</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>049000000919</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Central Railway Station</StopPointName>
             <DestinationDisplay xml:lang="EN">Wolverton</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:34:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop Z3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop Z3</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>300</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ATS_83001065</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">300</PublishedLineName>
         <DirectionName xml:lang="EN">Magna Park via CMK</DirectionName>
         <OperatorRef>ATS</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ATS-3328</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>049003030941</StopPointRef>
             <VisitNumber>14</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes The Point</StopPointName>
             <DestinationDisplay xml:lang="EN">Magna Park</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop J3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop J3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003030905</StopPointRef>
             <VisitNumber>15</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Theatre District</StopPointName>
             <DestinationDisplay xml:lang="EN">Magna Park</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop D3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop D3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049004505434</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Brook Furlong Milton Keynes Coachway</StopPointName>
             <DestinationDisplay xml:lang="EN">Magna Park</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:49:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:48:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Bay 9</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:49:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:49:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Bay 9</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>30</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ATS_50301059</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">30</PublishedLineName>
         <DirectionName xml:lang="EN">Downley</DirectionName>
         <OperatorRef>ATS</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ATS-3700</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>040000003280</StopPointRef>
             <VisitNumber>21</VisitNumber>
             <StopPointName xml:lang="EN">Downley Hithercroft Road</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">o/s 9</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">o/s 9</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000003278</StopPointRef>
             <VisitNumber>22</VisitNumber>
             <StopPointName xml:lang="EN">Downley Tinkers Wood Road</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">o/s 70</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">o/s 70</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000003274</StopPointRef>
             <VisitNumber>24</VisitNumber>
             <StopPointName xml:lang="EN">High Wycombe The Pastures</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">o/s 241</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">o/s 241</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000003270</StopPointRef>
             <VisitNumber>26</VisitNumber>
             <StopPointName xml:lang="EN">High Wycombe Brunel Road</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">o/s 15</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">o/s 15</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000003266</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">High Wycombe Telford Way</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">o/s 26</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">o/s 26</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000003056</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">High Wycombe Frogmoor</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop M</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop M</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000003061</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">High Wycombe Oxford Street</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop K</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop K</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000002962</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">High Wycombe Bus Station</StopPointName>
             <DestinationDisplay xml:lang="EN">Bus Station</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:50:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:50:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Bay 12</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>508</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_508_1143</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">508</PublishedLineName>
         <DirectionName xml:lang="EN">Stansted Airport</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-4078</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>210021307485</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Bishop&apos;s Stortford Riverside</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:29:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1500IM187T</StopPointRef>
             <VisitNumber>52</VisitNumber>
             <StopPointName xml:lang="EN">Stansted Airport Coach Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:58:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:58:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Bay 18</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>509</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_509_1124</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">509</PublishedLineName>
         <DirectionName xml:lang="EN">Harlow</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-4082</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>210021308080</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Sawbridgeworth White Lion PH</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:31:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>210021308085</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Sawbridgeworth High Wych Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1500IM780</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Old Harlow Post Office</StopPointName>
             <AimedArrivalTime>2019-09-02T16:45:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:45:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>150035031005</StopPointRef>
             <VisitNumber>47</VisitNumber>
             <StopPointName xml:lang="EN">Harlow Town Centre Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:55:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:55:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 3</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>2</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_2___1060</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">2</PublishedLineName>
         <DirectionName xml:lang="EN">Highwoods</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-4261</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>1500DGK079</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">Colchester Anthony Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>150033101007</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Colchester St. Christopher Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1500IM2456</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Highwoods Highwood Square</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop 2</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>1</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_1___1145</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">1</PublishedLineName>
         <DirectionName xml:lang="EN">Shrub End</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-3415</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>150033064003</StopPointRef>
             <VisitNumber>30</VisitNumber>
             <StopPointName xml:lang="EN">Shrub End Winston Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1500IM327B</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Shrub End Walnut Tree Way</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>13</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_C0131027</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">13</PublishedLineName>
         <DirectionName xml:lang="EN">Mold Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2518</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>5120WDB22250</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Penymynydd Old Horse and Jockey</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5120WDB21524</StopPointRef>
             <VisitNumber>53</VisitNumber>
             <StopPointName xml:lang="EN">Mold Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:55:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>B</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_B___1106</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">B</PublishedLineName>
         <DirectionName xml:lang="EN">Gravesend</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-4110</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2400100075</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Northfleet Springhead Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:29:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018660A</StopPointRef>
             <VisitNumber>38</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend Overcliffe</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop X</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop X</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018670A</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend Garrick Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>X5</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_B0X51037</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">X5</PublishedLineName>
         <DirectionName xml:lang="EN">Bangor Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3165</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>5130AWD71180</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Deganwy Railway Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5130AWD70301</StopPointRef>
             <VisitNumber>23</VisitNumber>
             <StopPointName xml:lang="EN">Llandudno Junction New Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand Z</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand Z</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5130AWD70298</StopPointRef>
             <VisitNumber>24</VisitNumber>
             <StopPointName xml:lang="EN">Llandudno Junction Flyover</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop W</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop W</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5130AWD70289</StopPointRef>
             <VisitNumber>25</VisitNumber>
             <StopPointName xml:lang="EN">Conwy Railway Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop M</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop M</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5400GYX17358</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Bangor Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:11:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:14:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand B</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>62</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_B0621041</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">62</PublishedLineName>
         <DirectionName xml:lang="EN">Amlwch Recreation Grounds</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-687</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>5400AWF80881</StopPointRef>
             <VisitNumber>9</VisitNumber>
             <StopPointName xml:lang="EN">Bangor Antelope Inn</StopPointName>
             <AimedArrivalTime>2019-09-02T16:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>X4</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_B0X41045</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">X4</PublishedLineName>
         <DirectionName xml:lang="EN">Holyhead Summer Hill</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2573</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>5410AWD70540</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Penrhos Toll House</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>5410WDB47858</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Penrhos Morrisons</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>X60</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ATS_87601039</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">X60</PublishedLineName>
         <DirectionName xml:lang="EN">Milton Keynes Fast</DirectionName>
         <OperatorRef>ATS</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ATS-3875</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>040000004513</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Buckingham High Street</StopPointName>
             <DestinationDisplay xml:lang="EN">Milton Keynes</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:32:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049000000911</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Central Railway Station</StopPointName>
             <DestinationDisplay xml:lang="EN">Milton Keynes</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:04:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop Y1</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:03:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:04:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop Y1</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003020932</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Santander House</StopPointName>
             <DestinationDisplay xml:lang="EN">Milton Keynes</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T17:06:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:07:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop X3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:06:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:07:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop X3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003020936</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes Central Business Exchange</StopPointName>
             <DestinationDisplay xml:lang="EN">Milton Keynes</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T17:08:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:09:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:08:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:09:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>049003030942</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Central Milton Keynes The Point</StopPointName>
             <DestinationDisplay xml:lang="EN">Milton Keynes</DestinationDisplay>
             <AimedArrivalTime>2019-09-02T17:13:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:14:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop H3</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>280</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ATS_280_1080</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">280</PublishedLineName>
         <DirectionName xml:lang="EN">Aylesbury Bus Stn</DirectionName>
         <OperatorRef>ATS</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ATS-5460</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>340001309OPP</StopPointRef>
             <VisitNumber>12</VisitNumber>
             <StopPointName xml:lang="EN">Headington Shops</StopPointName>
             <AimedArrivalTime>2019-09-02T16:23:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop HS6</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:23:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop HS6</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>340000009LRE</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Sandhills Thornhill Park and Ride</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>340000749TH</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Thame Town Hall</StopPointName>
             <AimedArrivalTime>2019-09-02T16:59:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:13:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T17:02:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:13:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000004914</StopPointRef>
             <VisitNumber>61</VisitNumber>
             <StopPointName xml:lang="EN">Aylesbury Friarage Road</StopPointName>
             <AimedArrivalTime>2019-09-02T17:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">opp 79</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">opp 79</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>040000004661</StopPointRef>
             <VisitNumber>62</VisitNumber>
             <StopPointName xml:lang="EN">Aylesbury Bus Stn</StopPointName>
             <AimedArrivalTime>2019-09-02T17:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Bay 11</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>89</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_89__1059</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">89</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool John Lennon Airport</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2984</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S50002A</StopPointRef>
             <VisitNumber>48</VisitNumber>
             <StopPointName xml:lang="EN">Belle Vale Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:25:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:25:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S50020B</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Belle Vale Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48016F</StopPointRef>
             <VisitNumber>62</VisitNumber>
             <StopPointName xml:lang="EN">Hunts Cross Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:41:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48016D</StopPointRef>
             <VisitNumber>63</VisitNumber>
             <StopPointName xml:lang="EN">Hunts Cross Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48089G</StopPointRef>
             <VisitNumber>80</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool John Lennon Airport</StopPointName>
             <AimedArrivalTime>2019-09-02T16:54:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:05:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop 1</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>89</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_89__1060</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">89</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Hall Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4596</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S50005C</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Belle Vale Runton Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S50016B</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Belle Vale Broomhill Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44188B</StopPointRef>
             <VisitNumber>44</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:48:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:48:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44041B</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Police Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:48:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop H</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:48:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop H</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S51066D</StopPointRef>
             <VisitNumber>54</VisitNumber>
             <StopPointName xml:lang="EN">Prescot Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:58:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:59:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:58:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:59:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S51044A</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Prescot Bridge Road</StopPointName>
             <AimedArrivalTime>2019-09-02T17:01:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:02:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:01:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:02:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S14033A</StopPointRef>
             <VisitNumber>64</VisitNumber>
             <StopPointName xml:lang="EN">Eccleston Park Rail Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:06:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:07:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:06:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:07:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>89</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_89__1056</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">89</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Hall Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4613</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S16018A</StopPointRef>
             <VisitNumber>75</VisitNumber>
             <StopPointName xml:lang="EN">West Park Underhill Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16017A</StopPointRef>
             <VisitNumber>76</VisitNumber>
             <StopPointName xml:lang="EN">St Helens Tullis Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>86A</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_86A_1206</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">86A</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool ONE</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4461</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S43038A</StopPointRef>
             <VisitNumber>27</VisitNumber>
             <StopPointName xml:lang="EN">Mossley Hill Nicander Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S41086C</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">Sefton Park Gresford Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>86A</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_86A_1198</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">86A</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool ONE</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4564</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42037B</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Newington</StopPointName>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:29:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>86</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_86__1183</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">86</PublishedLineName>
         <DirectionName xml:lang="EN">Garston Church Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4114</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41086D</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Wavertree Borrowdale Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>82</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_82__1147</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">82</PublishedLineName>
         <DirectionName xml:lang="EN">Speke Morrisons</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4811</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S48022B</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Speke Evans Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:24:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:24:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48002B</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Speke Woodend Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:25:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:25:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48190D</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">Speke Morrisons</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>81A</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_81A_1047</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">81A</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool John Lennon Airport</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4125</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S48025B</StopPointRef>
             <VisitNumber>50</VisitNumber>
             <StopPointName xml:lang="EN">Speke Tarbock Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48004B</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">Speke Stapleton Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48089F</StopPointRef>
             <VisitNumber>54</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool John Lennon Airport</StopPointName>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop 2</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>81</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_81__1060</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">81</PublishedLineName>
         <DirectionName xml:lang="EN">Bootle New Strand Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4115</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S49004B</StopPointRef>
             <VisitNumber>25</VisitNumber>
             <StopPointName xml:lang="EN">Woolton Manor Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S47072B</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Bootle Oriel Road Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:24:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:29:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:24:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:29:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>81</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_81__1053</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">81</PublishedLineName>
         <DirectionName xml:lang="EN">Speke Morrisons</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4107</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S43088B</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Woolton Rockbourne Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48016C</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Hunts Cross Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:49:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop F</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:44:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:49:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop F</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48190B</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Speke Morrisons</StopPointName>
             <AimedArrivalTime>2019-09-02T17:02:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:07:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 2</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>81</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_81__1051</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">81</PublishedLineName>
         <DirectionName xml:lang="EN">Speke Morrisons</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4117</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S48005B</StopPointRef>
             <VisitNumber>55</VisitNumber>
             <StopPointName xml:lang="EN">Speke Central Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48090A</StopPointRef>
             <VisitNumber>57</VisitNumber>
             <StopPointName xml:lang="EN">Speke Conleach Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48190B</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Speke Morrisons</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 2</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>80</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_80__1062</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">80</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool ONE</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4814</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41057B</StopPointRef>
             <VisitNumber>52</VisitNumber>
             <StopPointName xml:lang="EN">Toxteth Princes Gate West</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>80</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_80__1053</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">80</PublishedLineName>
         <DirectionName xml:lang="EN">Speke Morrisons</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S43125B</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Aigburth Stairhaven Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S43126B</StopPointRef>
             <VisitNumber>30</VisitNumber>
             <StopPointName xml:lang="EN">Aigburth Shirley Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S43201E</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Garston Liverpool South Parkway</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 5</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 5</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S48190C</StopPointRef>
             <VisitNumber>60</VisitNumber>
             <StopPointName xml:lang="EN">Speke Morrisons</StopPointName>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:04:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 3</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>7</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_7___1046</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">7</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Queen Square Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3057</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S50040A</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Whitefield Lane End Bardley Crescent</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S50039A</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Whitefield Lane End Manley Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44188G</StopPointRef>
             <VisitNumber>47</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 7</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44041C</StopPointRef>
             <VisitNumber>48</VisitNumber>
             <StopPointName xml:lang="EN">Knowsley Archway Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop J</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop J</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>87</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>7</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_7___1043</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">7</PublishedLineName>
         <DirectionName xml:lang="EN">Warrington Bus Interchange</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3052</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>069000024070</StopPointRef>
             <VisitNumber>73</VisitNumber>
             <StopPointName xml:lang="EN">Great Sankey Penketh Lane Ends</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>069000024080</StopPointRef>
             <VisitNumber>74</VisitNumber>
             <StopPointName xml:lang="EN">Sankey Bridges Georges Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>0690WNA02859</StopPointRef>
             <VisitNumber>83</VisitNumber>
             <StopPointName xml:lang="EN">Warrington Bus Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:45:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 9</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>79</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_79__1223</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">79</PublishedLineName>
         <DirectionName xml:lang="EN">Halewood Shopping Centre</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4453</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41075B</StopPointRef>
             <VisitNumber>14</VisitNumber>
             <StopPointName xml:lang="EN">Wavertree Hey Green Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:13:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:33:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:13:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S50002B</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Belle Vale Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:56:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:56:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>79D</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_79D_1229</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">79D</PublishedLineName>
         <DirectionName xml:lang="EN">Woodlands Winster Drive</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4475</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41069G</StopPointRef>
             <VisitNumber>9</VisitNumber>
             <StopPointName xml:lang="EN">Kensington Towerlands Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S50002B</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Belle Vale Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:56:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:05:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:56:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:05:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>75</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_75__1114</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">75</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool ONE</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4859</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S43025C</StopPointRef>
             <VisitNumber>25</VisitNumber>
             <StopPointName xml:lang="EN">Calderstones Park Cromptons Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S43024A</StopPointRef>
             <VisitNumber>26</VisitNumber>
             <StopPointName xml:lang="EN">Calderstones Park Calder Drive</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S41086E</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Sefton Park Lathbury Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:43:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S41099F</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Sefton Park Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:46:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:46:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>629</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>YTG_629_2117</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">629</PublishedLineName>
         <DirectionName xml:lang="EN">Smiddles Lane</DirectionName>
         <OperatorRef>YTG</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>YTG-1008</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450024687</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Bankfoot Smiddles Lane Manchester Rd</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>53</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_53__1114</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">53</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Queen Square Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2668</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>53</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_53__1109</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">53</PublishedLineName>
         <DirectionName xml:lang="EN">Great Crosby Crosby Village</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2921</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S47029B</StopPointRef>
             <VisitNumber>18</VisitNumber>
             <StopPointName xml:lang="EN">Bootle Marsh Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S47030B</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Bootle Melling Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S47022B</StopPointRef>
             <VisitNumber>24</VisitNumber>
             <StopPointName xml:lang="EN">Seaforth Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:41:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:41:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S47059A</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">Waterloo Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:50:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:51:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:50:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:51:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S54012F</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Great Crosby Crosby Village</StopPointName>
             <AimedArrivalTime>2019-09-02T16:59:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:00:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>49</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_49__1092</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">49</PublishedLineName>
         <DirectionName xml:lang="EN">Crossens Preston New Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2633</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S63002M</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Southport Nevill Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:32:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop CD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop CD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S60001B</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Southport Bold Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop FA</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop FA</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S60002B</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Southport Leicester Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop GA</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop GA</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S60003A</StopPointRef>
             <VisitNumber>38</VisitNumber>
             <StopPointName xml:lang="EN">Southport Thistleton Mews</StopPointName>
             <AimedArrivalTime>2019-09-02T16:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:41:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S60010B</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Churchtown Bibby Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>49</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_49__1091</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">49</PublishedLineName>
         <DirectionName xml:lang="EN">Ainsdale Vale Crescent</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3045</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S62003B</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Hillside George Drive</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S62035A</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Ainsdale Mill Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:29:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S62006B</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Ainsdale Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>481</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_481_1042</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">481</PublishedLineName>
         <DirectionName xml:lang="EN">Bluewater</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-1622</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2400A016730A</StopPointRef>
             <VisitNumber>24</VisitNumber>
             <StopPointName xml:lang="EN">Perry Street All Saints Church</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A016670A</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Northfleet Hall Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:48:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:49:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">opp 49</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:49:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">opp 49</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400100072</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Ebbsfleet International Railway Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:55:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:56:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:55:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:56:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A070040A</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Bluewater Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:11:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:12:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop 5</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>490</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ASC_490_1138</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">490</PublishedLineName>
         <DirectionName xml:lang="EN">Valley Drive</DirectionName>
         <OperatorRef>ASC</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ASC-4330</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2400A018630A</StopPointRef>
             <VisitNumber>14</VisitNumber>
             <StopPointName xml:lang="EN">Northfleet Arriva Depot</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018640A</StopPointRef>
             <VisitNumber>15</VisitNumber>
             <StopPointName xml:lang="EN">Northfleet Burch Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018650A</StopPointRef>
             <VisitNumber>16</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend Lennox Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018660A</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend Overcliffe</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop X</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop X</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018680A</StopPointRef>
             <VisitNumber>18</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend Garrick Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2400A018300A</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend West Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>240082423</StopPointRef>
             <VisitNumber>20</VisitNumber>
             <StopPointName xml:lang="EN">Gravesend Clock Tower</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop G</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:44:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop G</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>471</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_471_1054</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">471</PublishedLineName>
         <DirectionName xml:lang="EN">Heswall Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4526</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S26014B</StopPointRef>
             <VisitNumber>22</VisitNumber>
             <StopPointName xml:lang="EN">Landican Cemetery</StopPointName>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:29:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S29001B</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Heswall Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:46:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>472</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_472_1057</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">472</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Castle Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4527</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S26014A</StopPointRef>
             <VisitNumber>12</VisitNumber>
             <StopPointName xml:lang="EN">Arrowe Park Landican Cemetery</StopPointName>
             <AimedArrivalTime>2019-09-02T16:24:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:24:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S26042A</StopPointRef>
             <VisitNumber>13</VisitNumber>
             <StopPointName xml:lang="EN">Arrowe Park Hospital Internal Grounds</StopPointName>
             <AimedArrivalTime>2019-09-02T16:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018A</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Crosshall Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:57:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:09:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DB</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:57:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:09:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DB</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>437</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_437_1118</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">437</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Castle Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4532</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S21083A</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Bidston Noctorum Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21084A</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">Bidston Boundary Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21053B</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Brassey Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:41:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:44:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21093A</StopPointRef>
             <VisitNumber>38</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Park Asquith Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S22043E</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:54:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:54:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:54:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:54:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 7</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018A</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Crosshall Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:06:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:06:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DB</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:06:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:06:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DB</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>437</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_437_1116</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">437</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Castle Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4531</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S21053B</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Brassey Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:34:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21093A</StopPointRef>
             <VisitNumber>38</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Park Asquith Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S22043E</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:44:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 7</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018A</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Crosshall Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:56:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:58:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DB</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:56:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:58:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DB</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>425</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_425_5300</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">425</PublishedLineName>
         <DirectionName xml:lang="EN">Wakefield</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1713</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450025617</StopPointRef>
             <VisitNumber>54</VisitNumber>
             <StopPointName xml:lang="EN">Tingley Syke Rd Syke Gardens</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450016084</StopPointRef>
             <VisitNumber>56</VisitNumber>
             <StopPointName xml:lang="EN">Tingley Westerton Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450028194</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Westerton Frosts Corner</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030200</StopPointRef>
             <VisitNumber>83</VisitNumber>
             <StopPointName xml:lang="EN">Wakefield City Centre Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:03:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 20</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>414</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_414_1042</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">414</PublishedLineName>
         <DirectionName xml:lang="EN">Woodside Interchange</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3006</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S23028D</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Wallasey Village</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S23027B</StopPointRef>
             <VisitNumber>18</VisitNumber>
             <StopPointName xml:lang="EN">Wallasey Village Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S25024A</StopPointRef>
             <VisitNumber>27</VisitNumber>
             <StopPointName xml:lang="EN">Leasowe Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S26042A</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Arrowe Park Hospital Internal Grounds</StopPointName>
             <AimedArrivalTime>2019-09-02T16:59:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:04:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:59:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:04:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S22008C</StopPointRef>
             <VisitNumber>63</VisitNumber>
             <StopPointName xml:lang="EN">Woodside Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T17:25:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:30:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>413</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_413_1039</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">413</PublishedLineName>
         <DirectionName xml:lang="EN">Seacombe Ferry Terminal</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2954</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S26002B</StopPointRef>
             <VisitNumber>15</VisitNumber>
             <StopPointName xml:lang="EN">Prenton Grainger Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S26003B</StopPointRef>
             <VisitNumber>16</VisitNumber>
             <StopPointName xml:lang="EN">Prenton Ennerdale Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S26042A</StopPointRef>
             <VisitNumber>20</VisitNumber>
             <StopPointName xml:lang="EN">Arrowe Park Hospital Internal Grounds</StopPointName>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:43:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S25024B</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Leasowe Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:00:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:01:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:00:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:01:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S23027A</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Wallasey Village Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:11:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:12:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:11:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:12:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S24003B</StopPointRef>
             <VisitNumber>50</VisitNumber>
             <StopPointName xml:lang="EN">Liscard Conway Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:18:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:19:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:18:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:19:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21009A</StopPointRef>
             <VisitNumber>62</VisitNumber>
             <StopPointName xml:lang="EN">Seacombe Ferry Terminal</StopPointName>
             <AimedArrivalTime>2019-09-02T17:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:29:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>411</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_411_1057</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">411</PublishedLineName>
         <DirectionName xml:lang="EN">New Brighton Kings Parade</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2993</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S21007B</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Seacombe Brougham Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>410</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_410W1119</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">410</PublishedLineName>
         <DirectionName xml:lang="EN">Woodside Interchange</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2989</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S24005G</StopPointRef>
             <VisitNumber>12</VisitNumber>
             <StopPointName xml:lang="EN">Liscard Rullerton Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21034A</StopPointRef>
             <VisitNumber>13</VisitNumber>
             <StopPointName xml:lang="EN">Liscard Eric Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21035B</StopPointRef>
             <VisitNumber>14</VisitNumber>
             <StopPointName xml:lang="EN">Liscard Thorncliffe Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21017B</StopPointRef>
             <VisitNumber>20</VisitNumber>
             <StopPointName xml:lang="EN">St Anne Birkenhead Park Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S22008C</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Woodside Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:49:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:57:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>410</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_410_1109</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">410</PublishedLineName>
         <DirectionName xml:lang="EN">Clatterbridge Hosp Outpatients</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3007</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S27001B</StopPointRef>
             <VisitNumber>48</VisitNumber>
             <StopPointName xml:lang="EN">Bebington Parkside Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:19:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:19:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S27002B</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Lower Bebington The Grove</StopPointName>
             <AimedArrivalTime>2019-09-02T16:20:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:20:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S27003B</StopPointRef>
             <VisitNumber>50</VisitNumber>
             <StopPointName xml:lang="EN">Lower Bebington Civic Way</StopPointName>
             <AimedArrivalTime>2019-09-02T16:21:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:21:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S27010B</StopPointRef>
             <VisitNumber>57</VisitNumber>
             <StopPointName xml:lang="EN">Clatterbridge Hospital</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S27013A</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Clatterbridge Hosp Outpatients</StopPointName>
             <AimedArrivalTime>2019-09-02T16:30:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>409</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_409_1037</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">409</PublishedLineName>
         <DirectionName xml:lang="EN">Wallasey St Johns Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3010</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S22044A</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">St Anne Dover Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21009B</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Seacombe Ferry Terminal</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S24011A</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Liscard Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:48:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:51:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:51:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S24003E</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Liscard Dominick House</StopPointName>
             <AimedArrivalTime>2019-09-02T16:49:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop J</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:49:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop J</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>407</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_407_1060</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">407</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Castle Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4525</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S25123B</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Bidston Compton Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S25048B</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">Bidston Hurrell Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21053B</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Brassey Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:44:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S21093A</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Park Asquith Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:46:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:46:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S22043E</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Birkenhead Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:52:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:52:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 7</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018A</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Crosshall Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:03:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DB</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:03:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:03:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DB</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>385</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_385_1044</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">385</PublishedLineName>
         <DirectionName xml:lang="EN">Southport Wellington Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4578</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>1800WK04681</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Orrell Post Heyes Rd</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>25001983</StopPointRef>
             <VisitNumber>23</VisitNumber>
             <StopPointName xml:lang="EN">Hall Green Victoria Hotel</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:41:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2500LA00192</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Skelmersdale Concourse</StopPointName>
             <AimedArrivalTime>2019-09-02T16:55:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:55:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:58:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:58:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2500IMG1162</StopPointRef>
             <VisitNumber>66</VisitNumber>
             <StopPointName xml:lang="EN">Ormskirk Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:27:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:32:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S63004A</StopPointRef>
             <VisitNumber>100</VisitNumber>
             <StopPointName xml:lang="EN">Southport Princes Street</StopPointName>
             <AimedArrivalTime>2019-09-02T18:02:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T18:02:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop EC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T18:02:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T18:02:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop EC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S63001F</StopPointRef>
             <VisitNumber>101</VisitNumber>
             <StopPointName xml:lang="EN">Southport Eastbank Street</StopPointName>
             <AimedArrivalTime>2019-09-02T18:02:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T18:02:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop BE</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T18:02:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T18:02:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop BE</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S61015B</StopPointRef>
             <VisitNumber>102</VisitNumber>
             <StopPointName xml:lang="EN">Southport Wellington Street</StopPointName>
             <AimedArrivalTime>2019-09-02T18:04:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T18:04:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop AB</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>375</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_375_1045</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">375</PublishedLineName>
         <DirectionName xml:lang="EN">Wigan Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4576</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2500MEO00002</StopPointRef>
             <VisitNumber>12</VisitNumber>
             <StopPointName xml:lang="EN">Pool Hey Meols View Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:18:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:18:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>25001522</StopPointRef>
             <VisitNumber>38</VisitNumber>
             <StopPointName xml:lang="EN">Ormskirk Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:46:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:05:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 1</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:46:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:05:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 1</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2500IMG1164</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Ormskirk Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:12:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:53:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:12:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2500LA00194</StopPointRef>
             <VisitNumber>68</VisitNumber>
             <StopPointName xml:lang="EN">Skelmersdale Concourse</StopPointName>
             <AimedArrivalTime>2019-09-02T17:18:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 5</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:22:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 5</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1800WK04591</StopPointRef>
             <VisitNumber>90</VisitNumber>
             <StopPointName xml:lang="EN">Orrell Post</StopPointName>
             <AimedArrivalTime>2019-09-02T17:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:57:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:57:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1800WK02141</StopPointRef>
             <VisitNumber>105</VisitNumber>
             <StopPointName xml:lang="EN">Wigan Wallgate Stn</StopPointName>
             <AimedArrivalTime>2019-09-02T17:57:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T18:12:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:57:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T18:12:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1800WNBS0D1</StopPointRef>
             <VisitNumber>106</VisitNumber>
             <StopPointName xml:lang="EN">Wigan Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:59:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T18:14:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand D</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>360</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>YTG_360_3591</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">360</PublishedLineName>
         <DirectionName xml:lang="EN">HRI</DirectionName>
         <OperatorRef>unknown operator</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>YTG-666</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450027909</StopPointRef>
             <VisitNumber>30</VisitNumber>
             <StopPointName xml:lang="EN">Edgerton Thornhill Rd Sunny Bank Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450022776</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Huddersfield Royal Infirmary Occupation Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>352</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_352_1085</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">352</PublishedLineName>
         <DirectionName xml:lang="EN">Wigan Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4616</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>1800WK05661</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Wigan Pier</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1800WK08121</StopPointRef>
             <VisitNumber>50</VisitNumber>
             <StopPointName xml:lang="EN">Wigan Clayton St</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1800WK02141</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">Wigan Wallgate Stn</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>1800WNBS0C1</StopPointRef>
             <VisitNumber>52</VisitNumber>
             <StopPointName xml:lang="EN">Wigan Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand C</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>34</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_34__1114</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">34</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2967</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S10054A</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Crow Lane Silverdale Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S10106D</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Earlestown Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16002B</StopPointRef>
             <VisitNumber>55</VisitNumber>
             <StopPointName xml:lang="EN">St Helens Central Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:57:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:57:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:57:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:57:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16001I</StopPointRef>
             <VisitNumber>56</VisitNumber>
             <StopPointName xml:lang="EN">St Helens Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:58:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:58:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 5</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>345</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_345_1034</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">345</PublishedLineName>
         <DirectionName xml:lang="EN">Waddicar Andrew Avenue</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2497</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S46060A</StopPointRef>
             <VisitNumber>22</VisitNumber>
             <StopPointName xml:lang="EN">Warbreck Park Church Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:34:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S46087B</StopPointRef>
             <VisitNumber>23</VisitNumber>
             <StopPointName xml:lang="EN">Aintree Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S53037D</StopPointRef>
             <VisitNumber>26</VisitNumber>
             <StopPointName xml:lang="EN">Old Roan Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop F</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop F</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>33</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_33__1083</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">33</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-2692</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S16016B</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">St Helens Eccleston Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:16:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:16:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16001E</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">St Helens Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:30:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:50:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 9</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>281</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_281_2674</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">281</PublishedLineName>
         <DirectionName xml:lang="EN">Birstall Retail Pk</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1495</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450023494</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Birstall Lowood Lane Haworth Rd</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450027826</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Birstall Lowood Ln Dark Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>27</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_27__1139</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">27</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool ONE Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-7006</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S40055A</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">Anfield Liverpool FC</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S40126A</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Anfield Venice Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S40053B</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Everton St Domingo Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018B</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Cumberland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:53:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42019A</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool North John Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DE</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:53:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DE</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42020A</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Fenwick Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:54:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:54:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop WA</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:54:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:54:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop WA</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42098F</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool ONE Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:57:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:57:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 6</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>268</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_268_1607</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">268</PublishedLineName>
         <DirectionName xml:lang="EN">Bradford</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1904</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450015052</StopPointRef>
             <VisitNumber>38</VisitNumber>
             <StopPointName xml:lang="EN">Heckmondwike High Street Lobley St</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450015027</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Heckmondwike High St Cawley Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450015025</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Heckmondwike High Street Church Ln</StopPointName>
             <AimedArrivalTime>2019-09-02T16:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:41:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450029321</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Heckmondwike Hub</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop H1</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:46:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop H1</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450015022</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Heckmondwike Westgate</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop H9</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop H9</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025887</StopPointRef>
             <VisitNumber>52</VisitNumber>
             <StopPointName xml:lang="EN">Cleckheaton Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:58:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:58:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand F</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:00:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:00:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand F</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030012</StopPointRef>
             <VisitNumber>85</VisitNumber>
             <StopPointName xml:lang="EN">Bradford City Centre Interchange</StopPointName>
             <AimedArrivalTime>2019-09-02T17:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:35:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand H</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>229</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_229_1258</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">229</PublishedLineName>
         <DirectionName xml:lang="EN">Huddersfield</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1524</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450010362</StopPointRef>
             <VisitNumber>23</VisitNumber>
             <StopPointName xml:lang="EN">Gildersome Town Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450023505</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Birstall Market Place</StopPointName>
             <AimedArrivalTime>2019-09-02T16:55:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:54:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:55:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:55:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450029323</StopPointRef>
             <VisitNumber>44</VisitNumber>
             <StopPointName xml:lang="EN">Heckmondwike Hub</StopPointName>
             <AimedArrivalTime>2019-09-02T17:10:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:10:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop H4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:17:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:17:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop H4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450017205</StopPointRef>
             <VisitNumber>82</VisitNumber>
             <StopPointName xml:lang="EN">Huddersfield Town Centre Northumberland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:56:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:56:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop P2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:56:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:56:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop P2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030165</StopPointRef>
             <VisitNumber>83</VisitNumber>
             <StopPointName xml:lang="EN">Huddersfield Town Centre Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T18:00:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T18:00:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 1</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>203</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_203_2304</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">203</PublishedLineName>
         <DirectionName xml:lang="EN">Leeds</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1551</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450015163</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Mirfield Huddersfield Rd Church Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450015139</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Ravensthorpe Huddersfield Rd Fir Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450015137</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Ravensthorpe Huddersfield Road Fir Parade</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030135</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Dewsbury Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:50:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 8</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:55:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:55:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 8</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025311</StopPointRef>
             <VisitNumber>71</VisitNumber>
             <StopPointName xml:lang="EN">White Rose Centre White Rose Ctr</StopPointName>
             <AimedArrivalTime>2019-09-02T17:22:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:22:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:25:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:25:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450013210</StopPointRef>
             <VisitNumber>84</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Bridgewater Place</StopPointName>
             <AimedArrivalTime>2019-09-02T17:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:41:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop Z4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:41:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:41:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop Z4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025321</StopPointRef>
             <VisitNumber>85</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Infirmary Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:45:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop F</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:45:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop F</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450010687</StopPointRef>
             <VisitNumber>86</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Boar Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T17:48:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:48:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop T2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:48:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop T2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025323</StopPointRef>
             <VisitNumber>87</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Corn Exchange</StopPointName>
             <AimedArrivalTime>2019-09-02T17:49:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:49:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand K5</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:49:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:49:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand K5</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030227</StopPointRef>
             <VisitNumber>88</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:52:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 8</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>203</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_203_2295</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">203</PublishedLineName>
         <DirectionName xml:lang="EN">Huddersfield</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1549</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450016722</StopPointRef>
             <VisitNumber>75</VisitNumber>
             <StopPointName xml:lang="EN">Deighton Leeds Rd Neptune Way</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450016725</StopPointRef>
             <VisitNumber>76</VisitNumber>
             <StopPointName xml:lang="EN">Deighton Leeds Rd Whitacre Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450017205</StopPointRef>
             <VisitNumber>88</VisitNumber>
             <StopPointName xml:lang="EN">Huddersfield Town Centre Northumberland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:48:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:51:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop P2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:51:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop P2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030165</StopPointRef>
             <VisitNumber>89</VisitNumber>
             <StopPointName xml:lang="EN">Huddersfield Town Centre Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:54:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 1</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>201</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_201_1091</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">201</PublishedLineName>
         <DirectionName xml:lang="EN">Leeds</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1106</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450024359</StopPointRef>
             <VisitNumber>14</VisitNumber>
             <StopPointName xml:lang="EN">Upper Batley Batley Field Hill Chinewood Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450012144</StopPointRef>
             <VisitNumber>15</VisitNumber>
             <StopPointName xml:lang="EN">Upper Batley Blenhiem House Hotel</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450050051</StopPointRef>
             <VisitNumber>16</VisitNumber>
             <StopPointName xml:lang="EN">Upper Batley Scotchman Lane Blenheim Hill</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450011083</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">Morley Queensway</StopPointName>
             <AimedArrivalTime>2019-09-02T16:49:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:50:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop H</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:49:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:50:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop H</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450010340</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Morley Town Hall</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop C</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:51:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop C</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025311</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">White Rose Centre White Rose Ctr</StopPointName>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:04:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:03:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:04:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450013210</StopPointRef>
             <VisitNumber>56</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Bridgewater Place</StopPointName>
             <AimedArrivalTime>2019-09-02T17:19:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:20:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop Z4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:19:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:20:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop Z4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025321</StopPointRef>
             <VisitNumber>57</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Infirmary Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:23:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:24:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop F</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:23:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:24:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop F</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450010687</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Boar Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T17:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:27:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop T2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:27:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop T2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025323</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Corn Exchange</StopPointName>
             <AimedArrivalTime>2019-09-02T17:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:28:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand K5</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:28:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand K5</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030227</StopPointRef>
             <VisitNumber>60</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:30:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:31:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 8</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>200</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_200_1085</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">200</PublishedLineName>
         <DirectionName xml:lang="EN">Leeds</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-4162</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450013258</StopPointRef>
             <VisitNumber>64</VisitNumber>
             <StopPointName xml:lang="EN">Holbeck Meadow Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450013210</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Bridgewater Place</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop Z4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop Z4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025321</StopPointRef>
             <VisitNumber>66</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Infirmary Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop F</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop F</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450010687</StopPointRef>
             <VisitNumber>67</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Boar Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop T2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop T2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450025323</StopPointRef>
             <VisitNumber>68</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Centre Corn Exchange</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand K5</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand K5</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030227</StopPointRef>
             <VisitNumber>69</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:48:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 8</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>18</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_18__1127</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">18</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Georges Pier Head</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-7003</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S46085A</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Croxteth Park Kents Bank</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S46037A</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">West Derby Kerman Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>56</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:55:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:58:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:55:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:58:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:59:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:02:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:59:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:02:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42055A</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Dale Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:01:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:04:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop CHS</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:01:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:04:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop CHS</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>60</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:06:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:03:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:06:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42022E</StopPointRef>
             <VisitNumber>61</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Derby Square</StopPointName>
             <AimedArrivalTime>2019-09-02T17:05:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:08:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop LC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:05:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:08:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop LC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42021G</StopPointRef>
             <VisitNumber>62</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool James Street Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:06:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:09:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop JE</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:06:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:09:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop JE</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42009A</StopPointRef>
             <VisitNumber>63</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Georges Pier Head</StopPointName>
             <AimedArrivalTime>2019-09-02T17:08:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:11:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>18</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_18__1123</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">18</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Georges Pier Head</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4842</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42024A</StopPointRef>
             <VisitNumber>57</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Lord Nelson Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>58</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42055A</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Dale Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop CHS</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:42:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop CHS</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>60</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:44:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42022E</StopPointRef>
             <VisitNumber>61</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Derby Square</StopPointName>
             <AimedArrivalTime>2019-09-02T16:44:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop LC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:44:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop LC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42021G</StopPointRef>
             <VisitNumber>62</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool James Street Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:45:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop JE</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:45:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop JE</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42009A</StopPointRef>
             <VisitNumber>63</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Georges Pier Head</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:49:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>189</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_189_3605</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">189</PublishedLineName>
         <DirectionName xml:lang="EN">Castleford</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1958</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450019421</StopPointRef>
             <VisitNumber>17</VisitNumber>
             <StopPointName xml:lang="EN">Normanton Wakefield Rd Goosehill Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450017792</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Normanton Wakefield Rd Mill Hill</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450015586</StopPointRef>
             <VisitNumber>21</VisitNumber>
             <StopPointName xml:lang="EN">Normanton Market Place</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop N2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop N2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450019428</StopPointRef>
             <VisitNumber>22</VisitNumber>
             <StopPointName xml:lang="EN">Normanton High Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop N3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop N3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030340</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Castleford Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stand J</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>174</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_174_5044</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">174</PublishedLineName>
         <DirectionName xml:lang="EN">Wakefield</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1029</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450012886</StopPointRef>
             <VisitNumber>69</VisitNumber>
             <StopPointName xml:lang="EN">Little Preston Goody Cross Lane Whitehouse Ln</StopPointName>
             <AimedArrivalTime>2019-09-02T16:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030183</StopPointRef>
             <VisitNumber>120</VisitNumber>
             <StopPointName xml:lang="EN">Wakefield City Centre Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:10:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:15:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 3</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>15</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_15__1161</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">15</PublishedLineName>
         <DirectionName xml:lang="EN">Huyton Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4647</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S44088B</StopPointRef>
             <VisitNumber>29</VisitNumber>
             <StopPointName xml:lang="EN">Page Moss Windsor Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:22:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:22:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44089B</StopPointRef>
             <VisitNumber>30</VisitNumber>
             <StopPointName xml:lang="EN">Page Moss Beechburn Crescent</StopPointName>
             <AimedArrivalTime>2019-09-02T16:23:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:23:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44090B</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Page Moss Woodlands Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:24:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:24:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44188A</StopPointRef>
             <VisitNumber>36</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:42:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 1</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>14</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_14__1132</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">14</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Georges Pier Head</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4804</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S40031B</StopPointRef>
             <VisitNumber>20</VisitNumber>
             <StopPointName xml:lang="EN">Richmond Belmont Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S40030A</StopPointRef>
             <VisitNumber>21</VisitNumber>
             <StopPointName xml:lang="EN">Everton Queens Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:47:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>30</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:51:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:51:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:51:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018B</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Cumberland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:53:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>32</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:53:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42022E</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Derby Square</StopPointName>
             <AimedArrivalTime>2019-09-02T16:56:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:56:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop LC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:56:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:56:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop LC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42021G</StopPointRef>
             <VisitNumber>34</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool James Street Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:56:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:56:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop JE</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:56:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:56:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop JE</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42009A</StopPointRef>
             <VisitNumber>35</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Georges Pier Head</StopPointName>
             <AimedArrivalTime>2019-09-02T16:58:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:58:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>14</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_14__1121</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">14</PublishedLineName>
         <DirectionName xml:lang="EN">Gillmoss Petherick Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4838</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42016F</StopPointRef>
             <VisitNumber>6</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Gildart Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:25:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:25:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42027D</StopPointRef>
             <VisitNumber>7</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Shaw Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>14</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_14__1117</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">14</PublishedLineName>
         <DirectionName xml:lang="EN">Gillmoss Petherick Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4841</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S46005A</StopPointRef>
             <VisitNumber>26</VisitNumber>
             <StopPointName xml:lang="EN">Norris Green Cottesbrook Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:30:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:30:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>13</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_13__1099</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">13</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool North John Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4593</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S40023A</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Kensington Sheil Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S40022A</StopPointRef>
             <VisitNumber>60</VisitNumber>
             <StopPointName xml:lang="EN">Kensington Conwy Drive</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:45:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:44:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:45:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>67</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:49:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:49:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:49:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:49:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42055A</StopPointRef>
             <VisitNumber>68</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Dale Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:51:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop CHS</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:51:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:51:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop CHS</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>69</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T16:52:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:52:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42019A</StopPointRef>
             <VisitNumber>70</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool North John Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DE</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>13</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_13__1097</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">13</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool North John Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4622</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42016A</StopPointRef>
             <VisitNumber>64</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Epworth Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:30:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:30:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:39:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>67</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:43:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:43:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42055A</StopPointRef>
             <VisitNumber>68</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Dale Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:39:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop CHS</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:39:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop CHS</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>69</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42019A</StopPointRef>
             <VisitNumber>70</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool North John Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:47:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DE</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>13</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_13__1095</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">13</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool North John Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4677</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42055A</StopPointRef>
             <VisitNumber>68</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Dale Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop CHS</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop CHS</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>69</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T16:28:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:28:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42019A</StopPointRef>
             <VisitNumber>70</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool North John Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:29:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:39:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DE</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>127</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_127_2127</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">127</PublishedLineName>
         <DirectionName xml:lang="EN">Dewsbury</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1523</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450022275</StopPointRef>
             <VisitNumber>18</VisitNumber>
             <StopPointName xml:lang="EN">Horbury Cluntergate Walker Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Opp 45A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Opp 45A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450020155</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Horbury High Street Queen St</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450026126</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Ossett Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:46:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:46:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030133</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Dewsbury Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:03:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:03:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 6</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>127</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_127_2123</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">127</PublishedLineName>
         <DirectionName xml:lang="EN">Dewsbury</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1511</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450020460</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Chickenley Princess Rd Walnut Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:33:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:33:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450020459</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Chickenley Princess Lane Princess Rd</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030133</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Dewsbury Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 6</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>110</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_110_4573</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">110</PublishedLineName>
         <DirectionName xml:lang="EN">Leeds</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1939</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450011974</StopPointRef>
             <VisitNumber>81</VisitNumber>
             <StopPointName xml:lang="EN">Crown Point Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:37:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop A2</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:37:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop A2</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450026789</StopPointRef>
             <VisitNumber>82</VisitNumber>
             <StopPointName xml:lang="EN">Crown Point Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">stop A3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">stop A3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>450030226</StopPointRef>
             <VisitNumber>83</VisitNumber>
             <StopPointName xml:lang="EN">Leeds City Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:41:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:40:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 7</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10B</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10B_1123</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10B</PublishedLineName>
         <DirectionName xml:lang="EN">Huyton Elizabeth Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4672</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41025A</StopPointRef>
             <VisitNumber>33</VisitNumber>
             <StopPointName xml:lang="EN">Kensington Hawkins Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:35:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:35:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>37</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:43:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:43:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:45:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>39</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:48:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:50:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:50:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018B</StopPointRef>
             <VisitNumber>40</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Cumberland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:50:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:50:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42069A</StopPointRef>
             <VisitNumber>41</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Moorefields</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DD</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:51:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DD</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42079A</StopPointRef>
             <VisitNumber>42</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Princes Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:53:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:55:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop VA</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:53:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:55:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop VA</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023H</StopPointRef>
             <VisitNumber>43</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:57:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:59:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 3</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:57:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:59:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 3</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015E</StopPointRef>
             <VisitNumber>45</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Pembroke Place</StopPointName>
             <AimedArrivalTime>2019-09-02T17:04:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:06:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:04:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:06:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44040A</StopPointRef>
             <VisitNumber>76</VisitNumber>
             <StopPointName xml:lang="EN">Knowsley Huyton Town Centre</StopPointName>
             <AimedArrivalTime>2019-09-02T17:48:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:50:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop N</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:48:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:50:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop N</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44188D</StopPointRef>
             <VisitNumber>78</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:53:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:51:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:53:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 4</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10B</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10B_1111</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10B</PublishedLineName>
         <DirectionName xml:lang="EN">Huyton Elizabeth Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4667</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41028B</StopPointRef>
             <VisitNumber>52</VisitNumber>
             <StopPointName xml:lang="EN">Newsham Park Holland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:17:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:17:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S41029A</StopPointRef>
             <VisitNumber>53</VisitNumber>
             <StopPointName xml:lang="EN">Fairfield Prescot Drive</StopPointName>
             <AimedArrivalTime>2019-09-02T16:18:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:18:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44040A</StopPointRef>
             <VisitNumber>76</VisitNumber>
             <StopPointName xml:lang="EN">Knowsley Huyton Town Centre</StopPointName>
             <AimedArrivalTime>2019-09-02T16:47:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:05:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop N</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:47:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:05:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop N</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44188D</StopPointRef>
             <VisitNumber>78</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:50:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:08:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:50:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:08:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 4</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10B</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10B_1105</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10B</PublishedLineName>
         <DirectionName xml:lang="EN">Huyton Elizabeth Road</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-3058</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S51036B</StopPointRef>
             <VisitNumber>80</VisitNumber>
             <StopPointName xml:lang="EN">Huyton Quarry Wilson Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:23:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:23:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10__1176</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool Queen Square Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4441</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S51011A</StopPointRef>
             <VisitNumber>25</VisitNumber>
             <StopPointName xml:lang="EN">Knowsley Lyme Cross Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:36:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:36:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44020A</StopPointRef>
             <VisitNumber>26</VisitNumber>
             <StopPointName xml:lang="EN">Knowsley Longview Lane</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44123B</StopPointRef>
             <VisitNumber>31</VisitNumber>
             <StopPointName xml:lang="EN">Fincham Page Moss Avenue</StopPointName>
             <AimedArrivalTime>2019-09-02T16:46:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:45:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:46:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:46:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>53</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:16:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:16:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:16:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:16:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>55</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:22:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:22:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10A</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10A_1170</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10A</PublishedLineName>
         <DirectionName xml:lang="EN">Liverpool ONE Bus Station</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4601</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41031A</StopPointRef>
             <VisitNumber>48</VisitNumber>
             <StopPointName xml:lang="EN">Old Swan Herrick Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:38:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:35:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:38:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S41142B</StopPointRef>
             <VisitNumber>49</VisitNumber>
             <StopPointName xml:lang="EN">Stanley Barrymore Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:40:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:40:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:40:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015C</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Greek Street</StopPointName>
             <AimedArrivalTime>2019-09-02T16:54:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:54:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop R</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:54:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:54:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop R</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42023J</StopPointRef>
             <VisitNumber>61</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:59:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:59:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:59:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:59:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42018B</StopPointRef>
             <VisitNumber>62</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Cumberland Street</StopPointName>
             <AimedArrivalTime>2019-09-02T17:02:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:02:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop DC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:02:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:02:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop DC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42022E</StopPointRef>
             <VisitNumber>63</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Derby Square</StopPointName>
             <AimedArrivalTime>2019-09-02T17:05:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:05:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop LC</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:05:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:05:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop LC</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42021G</StopPointRef>
             <VisitNumber>64</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool James Street Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:06:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:06:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop JE</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:06:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:06:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop JE</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42098F</StopPointRef>
             <VisitNumber>65</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool ONE Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:09:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:09:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 6</ArrivalPlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10A</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10A_1163</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10A</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Hall Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4618</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S42023A</StopPointRef>
             <VisitNumber>4</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Queen Square Bus Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:21:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:33:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stand 4</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:21:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stand 4</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S42015E</StopPointRef>
             <VisitNumber>6</VisitNumber>
             <StopPointName xml:lang="EN">Liverpool Pembroke Place</StopPointName>
             <AimedArrivalTime>2019-09-02T16:26:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:41:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop D</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:26:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:41:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop D</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S51044A</StopPointRef>
             <VisitNumber>44</VisitNumber>
             <StopPointName xml:lang="EN">Prescot Bridge Road</StopPointName>
             <AimedArrivalTime>2019-09-02T17:16:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:31:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:16:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:31:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S14008A</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">St Anns Brandreth Close</StopPointName>
             <AimedArrivalTime>2019-09-02T17:23:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:38:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:23:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:38:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16052A</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Thatto Heath Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:31:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:46:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:31:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:46:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10A</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10A_1155</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10A</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Hall Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4435</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S41033C</StopPointRef>
             <VisitNumber>19</VisitNumber>
             <StopPointName xml:lang="EN">Old Swan Fitzgerald Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:22:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:38:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:22:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:38:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S51044A</StopPointRef>
             <VisitNumber>44</VisitNumber>
             <StopPointName xml:lang="EN">Prescot Bridge Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:51:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:07:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:51:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:07:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S14008A</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">St Anns Brandreth Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:58:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:14:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:58:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:14:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16052A</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Thatto Heath Station</StopPointName>
             <AimedArrivalTime>2019-09-02T17:06:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:22:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T17:06:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:22:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>10A</LineRef>
         <DirectionRef>OUTBOUND</DirectionRef>
         <DatedVehicleJourneyRef>ANW_10A_1149</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">10A</PublishedLineName>
         <DirectionName xml:lang="EN">St Helens Hall Street</DirectionName>
         <OperatorRef>ANW</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>ANW-4609</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>2800S44143A</StopPointRef>
             <VisitNumber>27</VisitNumber>
             <StopPointName xml:lang="EN">Dovecot Taurus Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:10:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:10:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S44007A</StopPointRef>
             <VisitNumber>28</VisitNumber>
             <StopPointName xml:lang="EN">Fincham Lordens Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:11:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:36:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:11:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:36:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S51044A</StopPointRef>
             <VisitNumber>44</VisitNumber>
             <StopPointName xml:lang="EN">Prescot Bridge Road</StopPointName>
             <AimedArrivalTime>2019-09-02T16:27:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:52:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop E</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:27:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:52:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop E</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S14008A</StopPointRef>
             <VisitNumber>51</VisitNumber>
             <StopPointName xml:lang="EN">St Anns Brandreth Close</StopPointName>
             <AimedArrivalTime>2019-09-02T16:34:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:59:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop B</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:34:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:59:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop B</DeparturePlatformName>
           </EstimatedCall>
           <EstimatedCall>
             <StopPointRef>2800S16052A</StopPointRef>
             <VisitNumber>59</VisitNumber>
             <StopPointName xml:lang="EN">Thatto Heath Station</StopPointName>
             <AimedArrivalTime>2019-09-02T16:42:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T17:07:00+01:00</ExpectedArrivalTime>
             <ArrivalPlatformName xml:lang="EN">Stop A</ArrivalPlatformName>
             <AimedDepartureTime>2019-09-02T16:42:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T17:07:00+01:00</ExpectedDepartureTime>
             <DeparturePlatformName xml:lang="EN">Stop A</DeparturePlatformName>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
     <EstimatedJourneyVersionFrame>
       <RecordedAtTime>2019-09-02T16:36:00+01:00</RecordedAtTime>
       <EstimatedVehicleJourney>
         <LineRef>102</LineRef>
         <DirectionRef>INBOUND</DirectionRef>
         <DatedVehicleJourneyRef>AYK_102_4138</DatedVehicleJourneyRef>
         <VehicleMode>bus</VehicleMode>
         <PublishedLineName xml:lang="EN">102</PublishedLineName>
         <DirectionName xml:lang="EN">Eastmoor</DirectionName>
         <OperatorRef>AYK</OperatorRef>
         <Monitored>true</Monitored>
         <VehicleRef>AYK-1014</VehicleRef>
         <EstimatedCalls>
           <EstimatedCall>
             <StopPointRef>450018444</StopPointRef>
             <VisitNumber>23</VisitNumber>
             <StopPointName xml:lang="EN">East Moor Park Lodge Lane Back Mount Pleasant</StopPointName>
             <AimedArrivalTime>2019-09-02T16:32:00+01:00</AimedArrivalTime>
             <ExpectedArrivalTime>2019-09-02T16:37:00+01:00</ExpectedArrivalTime>
             <AimedDepartureTime>2019-09-02T16:32:00+01:00</AimedDepartureTime>
             <ExpectedDepartureTime>2019-09-02T16:37:00+01:00</ExpectedDepartureTime>
           </EstimatedCall>
         </EstimatedCalls>
       </EstimatedVehicleJourney>
     </EstimatedJourneyVersionFrame>
   </EstimatedTimetableDelivery>
 </ServiceDelivery>
</Siri>
        """
        Operator.objects.bulk_create([
            Operator(region_id='EA', id='ANWE'),
            Operator(region_id='EA', id='WRAY'),
            Operator(region_id='EA', id='YTIG'),
            Operator(region_id='EA', id='ARBB'),
            Operator(region_id='EA', id='ANEA'),
            Operator(region_id='EA', id='ARHE')
        ])

        response = self.client.post('/siri', xml, content_type='text/xml')

        self.assertFalse(response.content)
