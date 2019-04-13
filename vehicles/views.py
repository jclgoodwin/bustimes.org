import ciso8601
from datetime import timedelta
from requests import Session
from django.db.models import Exists, OuterRef, Prefetch, Count
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import last_modified
from django.views.generic.detail import DetailView
from django.utils import timezone
from multidb.pinning import use_primary_db
from busstops.views import get_bounding_box
from busstops.models import Operator, Service, ServiceCode, SIRISource, DataSource, Journey
from .models import Vehicle, VehicleLocation, VehicleJourney
from .management.commands import import_sirivm

session = Session()


class Poorly(Exception):
    pass


def operator_vehicles(request, slug):
    operator = get_object_or_404(Operator, slug=slug)
    vehicles = operator.vehicle_set.order_by('fleet_number')
    vehicles = vehicles.select_related('vehicle_type', 'livery', 'latest_location__journey__service')
    if not vehicles:
        raise Http404()
    return render(request, 'operator_vehicles.html', {
        'breadcrumb': [operator.region, operator],
        'object': operator,
        'today': timezone.now().date(),
        'vehicles': vehicles,
        'code_column': any(v.code.isdigit() and int(v.code) != v.fleet_number for v in vehicles)
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
        locations = locations.using('default').filter(journey__service=request.GET['service'])

    return locations


@use_primary_db
def siri_one_shot(code):
    source = 'Icarus'
    siri_source = SIRISource.objects.get(name=code.scheme[:-5])
    cache_key = '{}:{}:{}'.format(siri_source.url, siri_source.requestor_ref, code.code)
    if cache.get(cache_key):
        return
    if siri_source.get_poorly():
        raise Poorly()
    now = timezone.now()
    locations = VehicleLocation.objects.filter(current=True)
    current_locations = locations.filter(journey__service=code.service_id, journey__source__name=source,
                                         latest_vehicle__isnull=False)
    if not Journey.objects.filter(service=code.service_id, datetime__lt=now, stopusageusage__datetime__gt=now).exists():
        fifteen_minutes_ago = timezone.now() - timedelta(minutes=15)
        if not current_locations.filter(datetime__gte=fifteen_minutes_ago).exists():
            cache.set(cache_key, True, 600)  # cache for 10 minutes
            return
    if locations.filter(journey__service=code.service_id).exclude(journey__source__name=source).exists():
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
    if 'Client.AUTHENTICATION_FAILED' in response.text or not response.ok:
        cache.set(siri_source.get_poorly_key(), True, 3600)  # back off for an hour
        raise Poorly()
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='Icarus')
    for item in import_sirivm.items_from_response(response):
        command.handle_item(item, now, code)
    # current_locations.exclude(id__in=command.current_location_ids).update(current=False)


def vehicles_last_modified(request):
    locations = get_locations(request)

    if 'service' in request.GET:
        schemes = ('Cornwall SIRI', 'Devon SIRI', 'Highland SIRI', 'Dundee SIRI', 'Bristol SIRI',
                   'Leicestershire SIRI', 'Dorset SIRI', 'Hampshire SIRI', 'West Sussex SIRI', 'Bucks SIRI',
                   'Peterborough SIRI')
        codes = ServiceCode.objects.filter(scheme__in=schemes, service=request.GET['service'])
        for code in codes:
            try:
                siri_one_shot(code)
                break
            except (SIRISource.DoesNotExist, Poorly):
                continue
    try:
        location = locations.values('datetime').latest('datetime')
        return location['datetime']
    except VehicleLocation.DoesNotExist:
        return


@last_modified(vehicles_last_modified)
def vehicles_json(request):
    locations = get_locations(request).order_by()

    locations = locations.select_related('journey__vehicle__livery')

    if 'service' in request.GET:
        extended = False
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
    today = timezone.now().date()
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
            date = today
    locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
    journeys = journeys.filter(datetime__date=date).select_related('vehicle').annotate(locations=Exists(locations))
    operator = service.operator.select_related('region').first()
    return render(request, 'vehicles/vehicle_detail.html', {
        'breadcrumb': [operator.region, operator, service],
        'date': date,
        'today': today,
        'object': service,
        'journeys': journeys,
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region', 'vehicle_type', 'livery')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.operator:
            context['breadcrumb'] = [self.object.operator.region, self.object.operator]
        date = self.request.GET.get('date')
        context['today'] = timezone.now().date()
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
                date = context['today']
        context['date'] = date
        journeys = journeys.filter(datetime__date=date)
        locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
        context['journeys'] = journeys.select_related('service').annotate(locations=Exists(locations))
        return context


def dashboard(request):
    week_ago = timezone.now() - timedelta(days=7)
    tracking = VehicleJourney.objects.filter(datetime__gt=week_ago).exclude(source__name='Stagecoach')
    operators = Operator.objects.filter(
        service__vehiclejourney__in=tracking.annotate(operators=Count('service__operator')).filter(operators=1)
    )
    tracking = tracking.filter(service=OuterRef('pk'))
    full_tracking = tracking.exclude(source__name='Icarus')
    services = Service.objects.filter(current=True).annotate(tracking=Exists(tracking),
                                                             full_tracking=Exists(full_tracking)).defer('geometry')
    prefetch = Prefetch('service_set', queryset=services)
    operators = operators.prefetch_related(prefetch).distinct()
    return render(request, 'vehicles/dashboard.html', {
        'operators': operators
    })


def journey_json(request, pk):
    return JsonResponse([{
        'coordinates': tuple(location.latlong),
        'delta': location.early,
        'direction': location.heading,
        'datetime': location.datetime,
    } for location in VehicleLocation.objects.filter(journey=pk)], safe=False)
