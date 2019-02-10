import ciso8601
from datetime import timedelta
from requests import Session
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import last_modified
from django.views.generic.detail import DetailView
from django.utils import timezone
from busstops.views import get_bounding_box
from busstops.models import Operator, Service, ServiceCode, SIRISource, DataSource, Journey
from .models import Vehicle, VehicleLocation, VehicleJourney
from .management.commands import import_sirivm

session = Session()


def operator_vehicles(request, slug):
    operator = get_object_or_404(Operator, slug=slug)
    vehicles = operator.vehicle_set.order_by('fleet_number')
    vehicles = vehicles.select_related('vehicle_type', 'latest_location__journey__service')
    if not vehicles:
        raise Http404()
    return render(request, 'operator_vehicles.html', {
        'breadcrumb': [operator.region, operator],
        'object': operator,
        'today': timezone.now().date(),
        'vehicles': vehicles
    })


def vehicles(request):
    return render(request, 'vehicles.html')


def get_locations(request):
    fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(current=True, datetime__gte=fifteen_minutes_ago)

    try:
        bounding_box = get_bounding_box(request)
        locations = locations.filter(latlong__within=bounding_box)
    except KeyError:
        pass

    if 'service' in request.GET:
        locations = locations.filter(journey__service=request.GET['service'])

    return locations


def siri_one_shot(code):
    source = 'Icarus'
    siri_source = SIRISource.objects.get(name=code.scheme[:-5])
    cache_key = '{}:{}:{}'.format(siri_source.url, siri_source.requestor_ref, code.code)
    if cache.get(cache_key):
        return
    now = timezone.now()
    current_locations = VehicleLocation.objects.filter(journey__service=code.service_id, journey__source__name=source,
                                                       latest_vehicle__isnull=False)
    if not Journey.objects.filter(service=code.service_id, datetime__lt=now, stopusageusage__datetime__gt=now).exists():
        if not current_locations.exists():
            cache.set(cache_key, True, 600)  # cache for 10 minutes
            return
    if VehicleLocation.objects.filter(journey__service=code.service_id,
                                      current=True).exclude(journey__source__name=source).exists():
        cache.set(cache_key, True, 3600)  # cache for 1 hour
        return
    cache.set(cache_key, True, 40)  # cache for 40 seconds
    data = """
        <Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
            <ServiceRequest>
                <RequestorRef>{}</RequestorRef>
                <VehicleMonitoringRequest version="1.3">
                    <LineRef>{}</LineRef>
                </VehicleMonitoringRequest>
            </ServiceRequest>
        </Siri>
    """.format(siri_source.requestor_ref, code.code)
    url = siri_source.url.replace('StopM', 'VehicleM', 1)
    response = session.post(url, data=data, timeout=5)
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='Icarus')
    for item in import_sirivm.items_from_response(response):
        command.handle_item(item, now)
    current_locations.exclude(id__in=command.current_location_ids).update(current=False)


def vehicles_last_modified(request):
    locations = get_locations(request)

    if 'service' in request.GET:
        schemes = ('Cornwall SIRI', 'Devon SIRI', 'Highland SIRI', 'Dundee SIRI', 'Bristol SIRI',
                   'Leicestershire SIRI', 'Dorset SIRI', 'Hampshire SIRI', 'West Sussex SIRI', 'Bucks SIRI',
                   'Peterborough SIRI')
        codes = ServiceCode.objects.filter(scheme__in=schemes, service=request.GET['service'])
        code = codes.first()
        if code:
            siri_one_shot(code)

    try:
        location = locations.values('datetime').latest('datetime')
        return location['datetime']
    except VehicleLocation.DoesNotExist:
        return


@last_modified(vehicles_last_modified)
def vehicles_json(request):
    locations = get_locations(request).order_by()

    if 'service' in request.GET:
        extended = False
        locations = locations.select_related('journey__vehicle')
    else:
        extended = True
        locations = locations.select_related('journey__service', 'journey__vehicle__operator',
                                             'journey__vehicle__vehicle_type').defer('journey__service__geometry')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [location.get_json(extended=extended) for location in locations]
    })


def service_vehicles_history(request, slug):
    service = get_object_or_404(Service, slug=slug)
    date = request.GET.get('date')
    if date:
        try:
            date = ciso8601.parse_datetime(date).date()
        except ValueError:
            date = None
    journeys = service.vehiclejourney_set
    if not date:
        try:
            date = journeys.values_list('datetime', flat=True).latest('datetime').date()
        except VehicleJourney.DoesNotExist:
            date = timezone.now().date()
    journeys = journeys.filter(datetime__date=date).select_related('vehicle').prefetch_related('vehiclelocation_set')
    operator = service.operator.select_related('region').first()
    return render(request, 'vehicles/vehicle_detail.html', {
        'breadcrumb': [operator.region, operator, service],
        'date': date,
        'object': service,
        'journeys': journeys
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region', 'vehicle_type')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.operator:
            context['breadcrumb'] = [self.object.operator.region, self.object.operator]
        date = self.request.GET.get('date')
        if date:
            try:
                date = ciso8601.parse_datetime(date).date()
            except ValueError:
                date = None
        journeys = self.object.vehiclejourney_set
        if not date:
            try:
                date = journeys.values_list('datetime', flat=True).latest('datetime').date()
            except VehicleJourney.DoesNotExist:
                date = timezone.now().date()
        context['date'] = date
        journeys = journeys.filter(datetime__date=date)
        context['journeys'] = journeys.select_related('service').prefetch_related('vehiclelocation_set')
        return context
