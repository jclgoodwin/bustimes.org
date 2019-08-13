import ciso8601
from datetime import timedelta
from requests import Session, exceptions
from django.db.models import Exists, OuterRef, Prefetch, Subquery
from django.core.cache import cache
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.http import last_modified
from django.views.generic.detail import DetailView
from django.urls import reverse
from django.utils import timezone
from multidb.pinning import use_primary_db
from busstops.views import get_bounding_box
from busstops.models import Operator, Service, ServiceCode, SIRISource, DataSource, Journey
from .models import Vehicle, VehicleLocation, VehicleJourney, VehicleEdit
from .forms import EditVehiclesForm, EditVehicleForm
from .management.commands import import_sirivm
from .rifkind import rifkind


session = Session()


class Poorly(Exception):
    pass


class Vehicles():
    def __init__(self, operator):
        self.operator = operator

    def __str__(self):
        return 'Vehicles'

    def get_absolute_url(self):
        return reverse('operator_vehicles', args=(self.operator.slug,))


def get_vehicle_edit(vehicle, fields):
    edit = VehicleEdit(vehicle=vehicle)

    for field in ('fleet_number', 'reg', 'vehicle_type', 'notes'):
        if field in fields and str(fields[field]) != str(getattr(vehicle, field)):
            if fields[field]:
                setattr(edit, field, fields[field])
            else:
                setattr(edit, field, f'-{getattr(vehicle, field)}')

    if not edit.vehicle_type:
        edit.vehicle_type = ''

    if fields['colours']:
        if fields['colours'].isdigit():
            edit.livery_id = fields['colours']
        elif fields['colours']:
            edit.colours = fields['colours']

    return edit


def operator_vehicles(request, slug):
    operator = get_object_or_404(Operator.objects.select_related('region'), slug=slug)
    vehicles = operator.vehicle_set
    latest_journeys = Subquery(VehicleJourney.objects.filter(
        vehicle=OuterRef('pk')
    ).order_by('-datetime').values('pk')[:1])
    latest_journeys = vehicles.filter(latest_location=None).annotate(latest_journey=latest_journeys)
    latest_journeys = VehicleJourney.objects.filter(id__in=latest_journeys.values('latest_journey'))
    prefetch = Prefetch('vehiclejourney_set',
                        queryset=latest_journeys.select_related('service'), to_attr='latest_journeys')
    vehicles = vehicles.prefetch_related(prefetch)
    vehicles = vehicles.order_by('fleet_number', 'reg', 'code')
    vehicles = vehicles.select_related('vehicle_type', 'livery', 'latest_location__journey__service')
    if not vehicles:
        raise Http404()
    rowspan_haver = None
    for vehicle in vehicles:
        vehicle.rowspan = 1
        if rowspan_haver and rowspan_haver.vehicle_type == vehicle.vehicle_type:
            rowspan_haver.rowspan += 1
        else:
            rowspan_haver = vehicle

    edit = request.path.endswith('/edit')
    submitted = False
    if edit:
        form = EditVehiclesForm(request.POST, vehicle=vehicle)
        if request.POST and form.is_valid():
            ticked_vehicles = (vehicle for vehicle in vehicles if str(vehicle.id) in request.POST.getlist('vehicle'))
            submitted = len(VehicleEdit.objects.bulk_create(
                get_vehicle_edit(vehicle, form.cleaned_data) for vehicle in ticked_vehicles
            ))
    else:
        form = None

    return render(request, 'operator_vehicles.html', {
        'breadcrumb': [operator.region, operator],
        'object': operator,
        'today': timezone.localtime().date(),
        'vehicles': vehicles,
        'code_column': any(v.code.isdigit() and v.fleet_number and int(v.code) != v.fleet_number for v in vehicles),
        'notes_column': any(vehicle.notes for vehicle in vehicles),
        'edit_url': reverse('admin:vehicles_vehicle_changelist'),
        'edit': edit,
        'submitted': submitted,
        'form': form,
    })


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
    line_name_cache_key = '{}:{}:{}'.format(siri_source.url, siri_source.requestor_ref, code.code)
    service_cache_key = '{}:{}'.format(code.service_id, source)
    if cache.get(line_name_cache_key):
        return 'cached (line name)'
    cached = cache.get(service_cache_key)
    if cached:
        return f'cached ({cached})'
    if siri_source.get_poorly():
        raise Poorly()
    now = timezone.now()
    locations = VehicleLocation.objects.filter(current=True, latest_vehicle__isnull=False,
                                               journey__service=code.service_id)
    current_locations = locations.filter(journey__source__name=source)
    fifteen_minutes_ago = now - timedelta(minutes=15)
    scheduled_journeys = Journey.objects.filter(service=code.service_id, datetime__lt=now + timedelta(minutes=10),
                                                stopusageusage__datetime__gt=now - timedelta(minutes=10))
    if not scheduled_journeys.exists():
        if not current_locations.filter(datetime__gte=fifteen_minutes_ago).exists():
            # no journeys currently scheduled, and no vehicles online recently
            cache.set(service_cache_key, 'nothing scheduled', 300)  # back off for 5 minutes
            return 'nothing scheduled'
    # from a different source
    if locations.filter(datetime__gte=fifteen_minutes_ago).exclude(journey__source__name=source).exists():
        cache.set(service_cache_key, 'different source', 3600)  # back off for for 1 hour
        return 'deferring to a different source'
    cache.set(line_name_cache_key, 'line name', 40)  # cache for 40 seconds
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
    if 'Client.AUTHENTICATION_FAILED' in response.text:
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
                   'Peterborough SIRI', 'Essex SIRI', 'Southampton SIRI', 'Slough SIRI', 'Staffordshire SIRI')
        service_id = request.GET['service']
        codes = ServiceCode.objects.filter(scheme__in=schemes, service=service_id)
        for code in codes:
            try:
                siri_one_shot(code)
                break
            except (SIRISource.DoesNotExist, Poorly, exceptions.RequestException):
                continue
        if Operator.objects.filter(id__in=('KBUS', 'NCTR', 'TBTN', 'NOCT'), service=service_id).exists():
            rifkind(service_id)
    try:
        location = locations.values('datetime').latest('datetime')
        return location['datetime']
    except VehicleLocation.DoesNotExist:
        return


@last_modified(vehicles_last_modified)
def vehicles_json(request):
    locations = get_locations(request).order_by()

    locations = locations.select_related('journey__vehicle__livery', 'journey__vehicle__vehicle_type')

    if 'service' in request.GET:
        extended = False
    else:
        extended = True
        locations = locations.select_related('journey__service', 'journey__vehicle__operator'
                                             ).defer('journey__service__geometry')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [location.get_json(extended=extended) for location in locations]
    })


def service_vehicles_history(request, slug=None, operator=None, route=None):
    if slug:
        service = get_object_or_404(Service, slug=slug)
        journeys = service.vehiclejourney_set
    else:
        service = None
        operator = get_object_or_404(Operator, slug=operator)
        journeys = VehicleJourney.objects.filter(vehicle__operator=operator, route_name=route)
    date = request.GET.get('date')
    if date:
        try:
            date = ciso8601.parse_datetime(date).date()
        except ValueError:
            date = None
    dates = journeys.values_list('datetime__date', flat=True).distinct().order_by('datetime__date')
    if not date:
        date = dates.last()
        if not date:
            raise Http404()
    locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
    journeys = journeys.filter(datetime__date=date).select_related('vehicle').annotate(locations=Exists(locations))
    if slug:
        operator = service.operator.select_related('region').first()
    return render(request, 'vehicles/vehicle_detail.html', {
        'breadcrumb': [operator.region, operator, service or Vehicles(operator)],
        'date': date,
        'dates': dates,
        'object': service or route,
        'journeys': journeys.order_by('datetime'),
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region', 'vehicle_type', 'livery')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journeys = self.object.vehiclejourney_set
        context['dates'] = journeys.values_list('datetime__date', flat=True).distinct().order_by('datetime__date')
        if not context['dates']:
            raise Http404()
        if self.object.operator:
            context['breadcrumb'] = [self.object.operator, Vehicles(self.object.operator)]
        date = self.request.GET.get('date')
        if date:
            try:
                date = ciso8601.parse_datetime(date).date()
            except ValueError:
                date = None
        if not date:
            date = context['dates'].last()
        context['date'] = date
        journeys = journeys.filter(datetime__date=date).order_by('datetime')
        locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
        context['journeys'] = journeys.select_related('service').annotate(locations=Exists(locations))
        return context


def edit_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle.objects.select_related('vehicle_type', 'livery', 'operator'), id=vehicle_id)
    submitted = False
    initial = {
        'fleet_number': vehicle.fleet_number,
        'reg': vehicle.reg,
        'vehicle_type': vehicle.vehicle_type,
        'colours': str(vehicle.livery_id or vehicle.colours),
        'notes': vehicle.notes
    }
    if request.method == 'POST':
        form = EditVehicleForm(request.POST, initial=initial, vehicle=vehicle)
        if not form.has_changed():
            form.add_error(None, 'You haven\'t changed anything')
        elif form.is_valid():
            edit = VehicleEdit(vehicle=vehicle, **form.cleaned_data)
            if not edit.vehicle_type:
                edit.vehicle_type = ''
            if form.cleaned_data['colours'] and form.cleaned_data['colours'].isdigit():
                edit.livery_id = form.cleaned_data['colours']
                edit.colours = ''
            edit.save()
            submitted = True
    else:
        form = EditVehicleForm(initial=initial, vehicle=vehicle)
    if vehicle.operator:
        breadcrumb = [vehicle.operator, Vehicles(vehicle.operator), vehicle]
    else:
        breadcrumb = [vehicle]
    return render(request, 'edit_vehicle.html', {
        'breadcrumb': breadcrumb,
        'form': form,
        'vehicle': vehicle,
        'submitted': submitted
    })


def tracking_report(request):
    week_ago = timezone.now() - timedelta(days=7)
    full_tracking = VehicleJourney.objects.filter(datetime__gt=week_ago)
    full_tracking = full_tracking.filter(service=OuterRef('pk')).exclude(source__name='Icarus')

    services = Service.objects.filter(current=True).annotate(full_tracking=Exists(full_tracking)).defer('geometry')
    prefetch = Prefetch('service_set', queryset=services)
    operators = Operator.objects.filter(
        service__current=True,
        service__tracking=True
    ).prefetch_related(prefetch).distinct()

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
