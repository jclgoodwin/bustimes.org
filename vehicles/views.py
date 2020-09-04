import redis
import json
import xml.etree.cElementTree as ET
from datetime import timedelta
from requests import Session, exceptions
from ciso8601 import parse_datetime
from django.db.models import Exists, OuterRef, Prefetch, Subquery, Q, Value
from django.db.models.functions import Replace
from django.core.cache import cache
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse, Http404
from django.views.decorators.http import last_modified
from django.views.generic.detail import DetailView
from django.urls import reverse
from django.utils import timezone
# from multidb.pinning import use_primary_db
from busstops.utils import get_bounding_box
from busstops.models import Operator, Service, ServiceCode, SIRISource, DataSource
from bustimes.models import get_calendars, Trip
from .models import Vehicle, VehicleLocation, VehicleJourney, VehicleEdit, VehicleEditFeature, VehicleRevision
from .forms import EditVehiclesForm, EditVehicleForm
from .management.commands import import_sirivm
from .rifkind import rifkind
from .utils import get_vehicle_edit, do_revision, do_revisions
from .tasks import handle_siri_vm, handle_siri_et, handle_siri_sx


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


def vehicles(request):
    return render(request, 'vehicles.html', {
        'operators': Operator.objects.filter(vehicle__withdrawn=False).distinct()
    })


def map(request):
    return render(request, 'map.html')


def operator_vehicles(request, slug=None, parent=None):
    operators = Operator.objects.select_related('region')
    if slug:
        try:
            operator = get_object_or_404(operators, slug=slug.lower())
        except Http404:
            operator = get_object_or_404(operators, operatorcode__code=slug, operatorcode__source__name='slug')
        vehicles = operator.vehicle_set.filter(withdrawn=False)
    elif parent:
        operators = list(operators.filter(parent=parent))
        vehicles = Vehicle.objects.filter(operator__in=operators, withdrawn=False).select_related('operator')
        if not operators:
            raise Http404
        operator = operators[0]

    vehicles = vehicles.order_by('fleet_number', 'fleet_code', 'reg', 'code')
    if not parent:
        latest_journeys = Subquery(VehicleJourney.objects.filter(
            vehicle=OuterRef('pk')
        ).order_by('-datetime').values('pk')[:1])
        latest_journeys = vehicles.filter(latest_location=None).annotate(latest_journey=latest_journeys)
        latest_journeys = VehicleJourney.objects.filter(id__in=latest_journeys.values('latest_journey'))
        prefetch = Prefetch('vehiclejourney_set',
                            queryset=latest_journeys.select_related('service'), to_attr='latest_journeys')
        vehicles = vehicles.prefetch_related(prefetch, 'features')
        pending_edits = VehicleEdit.objects.filter(approved=None, vehicle=OuterRef('id')).only('id')
        vehicles = vehicles.annotate(pending_edits=Exists(pending_edits))
        vehicles = vehicles.select_related('latest_location__journey__service')

    vehicles = vehicles.select_related('livery', 'vehicle_type')

    submitted = False
    revisions = False
    breadcrumb = [operator.region, operator]

    form = request.path.endswith('/edit')

    if form:
        breadcrumb.append(Vehicles(operator))
        initial = {
            'operator': operator,
            'other_colour': '#ffffff',
            'user': request.COOKIES.get('username')
        }
        if request.method == 'POST':
            form = EditVehiclesForm(request.POST, initial=initial, operator=operator)
            if not form.has_really_changed():
                form.add_error(None, 'You haven\'t changed anything')
            elif form.is_valid():
                data = {key: form.cleaned_data[key] for key in form.changed_data}
                vehicle_ids = request.POST.getlist('vehicle')
                now = timezone.now()
                username = form.cleaned_data.get('user')

                revisions, changed_fields = do_revisions(vehicle_ids, data)
                if revisions:
                    Vehicle.objects.bulk_update((revision.vehicle for revision in revisions), changed_fields)
                    for revision in revisions:
                        revision.datetime = now
                        revision.username = username or ''
                        revision.ip_address = request.META['REMOTE_ADDR']
                        if request.user.is_authenticated():
                            revision.user = request.user
                    VehicleRevision.objects.bulk_create(revisions)
                    revisions = len(revisions)

                if 'user' in data:
                    del data['user']

                if data:
                    # this will fetch the vehicles list
                    # - slightly important that it occurs before any change of operator
                    ticked_vehicles = [v for v in vehicles if str(v.id) in vehicle_ids]
                    edits = [get_vehicle_edit(vehicle, data, now, username, request) for vehicle in ticked_vehicles]
                    edits = VehicleEdit.objects.bulk_create(edit for edit in edits if edit)
                    submitted = len(edits)
                    if 'features' in data:
                        for edit in edits:
                            edit.features.set(data['features'])
                form = EditVehiclesForm(initial=initial, operator=operator)
        else:
            form = EditVehiclesForm(initial=initial, operator=operator)

        depots = vehicles.order_by().distinct('data__Depot').values_list('data__Depot', flat=True)

    else:
        depots = None

    if operator.name == 'National Express':
        vehicles = sorted(vehicles, key=lambda v: v.notes)

    if not vehicles:
        raise Http404

    paginator = Paginator(vehicles, 1000)
    page = request.GET.get('page')
    vehicles = paginator.get_page(page)

    features_column = not parent and any(vehicle.features.all() for vehicle in vehicles)

    columns = set(key for vehicle in vehicles if vehicle.data for key in vehicle.data)
    for vehicle in vehicles:
        vehicle.column_values = [vehicle.data and vehicle.data.get(key) for key in columns]

    response = render(request, 'operator_vehicles.html', {
        'breadcrumb': breadcrumb,
        'parent': parent,
        'operators': parent and operators,
        'object': operator,
        'today': timezone.localtime().date(),
        'vehicles': vehicles,
        'paginator': paginator,
        'code_column': any(v.fleet_number_mismatch() for v in vehicles),
        'branding_column': any(vehicle.branding for vehicle in vehicles),
        'name_column': any(vehicle.name for vehicle in vehicles),
        'notes_column': any(vehicle.notes and vehicle.notes != 'Spare ticket machine' for vehicle in vehicles),
        'features_column': features_column,
        'columns': columns,
        'edits': submitted,
        'revisions': revisions,
        'revision': revisions and revision,
        'form': form,
        'depots': depots
    })

    if form and form.is_valid() and form.cleaned_data['user'] != request.COOKIES.get('username', ''):
        response.set_cookie('username', form.cleaned_data['user'], 60 * 60 * 24 * 31, httponly=True, samesite='Strict')

    return response


def get_locations(request):
    now = timezone.now()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(latest_vehicle__isnull=False, datetime__gte=fifteen_minutes_ago,
                                               current=True)

    try:
        bounding_box = get_bounding_box(request)
        locations = locations.filter(latlong__within=bounding_box)
    except KeyError:
        pass

    if 'service' in request.GET:
        locations = locations.filter(journey__service=request.GET['service'])

    return locations


# @use_primary_db
def siri_one_shot(code, now):
    source = 'Icarus'
    siri_source = SIRISource.objects.get(name=code.scheme[:-5])
    line_name_cache_key = f'{siri_source.url}:{siri_source.requestor_ref}:{code.code}'
    service_cache_key = f'{code.service_id}:{source}'
    if cache.get(line_name_cache_key):
        return 'cached (line name)'
    cached = cache.get(service_cache_key)
    if cached:
        return f'cached ({cached})'
    if siri_source.get_poorly():
        raise Poorly()
    fifteen_minutes_ago = now - timedelta(minutes=15)
    locations = VehicleLocation.objects.filter(latest_vehicle__isnull=False, journey__service=code.service_id,
                                               datetime__gte=fifteen_minutes_ago, current=True)
    if not locations.filter(journey__source__name=source).exists():
        time_since_midnight = timedelta(hours=now.hour, minutes=now.minute, seconds=now.second,
                                        microseconds=now.microsecond)
        trips = Trip.objects.filter(calendar__in=get_calendars(now), route__service=code.service_id,
                                    start__lte=time_since_midnight + timedelta(minutes=10),
                                    end__gte=time_since_midnight - timedelta(minutes=10))
        if not trips.exists():
            # no journeys currently scheduled, and no vehicles online recently
            cache.set(service_cache_key, 'nothing scheduled', 300)  # back off for 5 minutes
            return 'nothing scheduled'
    # from a different source
    if locations.filter(~Q(journey__source__name=source)).exists():
        cache.set(service_cache_key, 'different source', 3600)  # back off for for 1 hour
        return 'deferring to a different source'
    cache.set(line_name_cache_key, 'line name', 40)  # cache for 40 seconds
    data = f"""<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
<ServiceRequest><RequestorRef>{siri_source.requestor_ref}</RequestorRef>
<VehicleMonitoringRequest version="1.3"><LineRef>{code.code}</LineRef></VehicleMonitoringRequest>
</ServiceRequest></Siri>"""
    url = siri_source.url.replace('StopM', 'VehicleM', 1)
    response = session.post(url, data=data, timeout=5)
    if 'Client.AUTHENTICATION_FAILED' in response.text:
        cache.set(siri_source.get_poorly_key(), True, 3600)  # back off for an hour
        raise Poorly()
    command = import_sirivm.Command()
    command.source = DataSource.objects.get(name='Icarus')
    for item in import_sirivm.items_from_response(response):
        command.handle_item(item, now, code)


schemes = ('Cornwall SIRI', 'Devon SIRI', 'Highland SIRI', 'Dundee SIRI', 'Bristol SIRI',
           'Leicestershire SIRI', 'Dorset SIRI', 'Hampshire SIRI', 'West Sussex SIRI', 'Bucks SIRI',
           'Peterborough SIRI', 'Bracknell Siri')
# ('Essex SIRI', 'Southampton SIRI', 'Slough SIRI', 'Staffordshire SIRI')


def vehicles_last_modified(request):
    request.nothing = False

    if 'service' in request.GET:
        service_id = request.GET['service']
        now = timezone.localtime()

        last_modified = cache.get(f'{service_id}:vehicles_last_modified')
        if last_modified and (now - last_modified).total_seconds() < 40:
            return last_modified

        operators = Operator.objects.filter(service=service_id)
        if not any(operator.id in {'CTNY', 'SCBD'} for operator in operators):
            codes = ServiceCode.objects.filter(scheme__in=schemes, service=service_id)
            codes = codes.annotate(source_name=Replace('scheme', Value(' SIRI')))
            siri_sources = SIRISource.objects.filter(name=OuterRef('source_name'))
            codes = codes.filter(Exists(siri_sources))

            for code in codes:
                try:
                    siri_one_shot(code, now)
                    break
                except (Poorly, exceptions.RequestException):
                    continue

            if any(operator.id in {'KBUS', 'TBTN', 'NOCT'} for operator in operators):
                rifkind(service_id)

        last_modified = cache.get(f'{service_id}:vehicles_last_modified')
        if last_modified and (now - last_modified).total_seconds() > 900:  # older than 15 minutes
            request.nothing = True
        return last_modified


@last_modified(vehicles_last_modified)
def vehicles_json(request):
    if request.nothing:
        locations = ()
    else:
        locations = get_locations(request).order_by()
        locations = locations.select_related('journey__vehicle__livery', 'journey__vehicle__vehicle_type')

        if 'service' in request.GET:
            extended = False
            locations = locations.prefetch_related('journey__vehicle__features')
        else:
            extended = True
            locations = locations.select_related('journey__service', 'journey__vehicle__operator')
            locations = locations.defer('journey__service__geometry', 'journey__service__search_vector')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [location.get_json(extended=extended) for location in locations]
    })


def get_dates(journeys, vehicle=None, service=None):
    if vehicle:
        key = f'vehicle:{vehicle.id}:dates'
    else:
        key = f'service:{service.id}:dates'

    dates = cache.get(key)

    if not dates:
        dates = list(journeys.values_list('datetime__date', flat=True).distinct().order_by('datetime__date'))
        if dates:
            now = timezone.now()
            if dates[-1] == now.date():
                time_until_midnight = timedelta(days=1)
                time_until_midnight -= timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
                time_until_midnight = time_until_midnight.total_seconds()
                if time_until_midnight > 0:
                    cache.set(key, dates, time_until_midnight)

    return dates


def service_vehicles_history(request, slug):
    service = get_object_or_404(Service, slug=slug)
    journeys = service.vehiclejourney_set
    date = request.GET.get('date')
    if date:
        try:
            date = parse_datetime(date).date()
        except ValueError:
            date = None
    dates = get_dates(journeys, service=service)
    if not dates:
        raise Http404()
    if not date:
        date = dates[-1]
    # calls = Call.objects.filter(journey=OuterRef('pk'))
    # journeys = journeys.annotate(calls=Exists(calls))
    journeys = journeys.filter(datetime__date=date).select_related('vehicle').order_by('datetime')
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        pipe = r.pipeline()
        for journey in journeys:
            pipe.exists(f'journey{journey.id}')
        locations = pipe.execute()
        previous = None
        for i, journey in enumerate(journeys):
            journey.locations = locations[i]
            if journey.locations:
                if previous:
                    previous.next = journey
                    journey.previous = previous
                previous = journey
    except redis.exceptions.ConnectionError:
        pass

    operator = service.operator.select_related('region').first()
    return render(request, 'vehicles/vehicle_detail.html', {
        'breadcrumb': [operator, service],
        'date': date,
        'dates': dates,
        'object': service,
        'journeys': journeys,
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region',
                                            'vehicle_type', 'livery').prefetch_related('features')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        journeys = self.object.vehiclejourney_set
        context['pending_edits'] = self.object.vehicleedit_set.filter(approved=None).exists()
        dates = get_dates(journeys, vehicle=self.object)
        if self.object.operator:
            context['breadcrumb'] = [self.object.operator, Vehicles(self.object.operator)]

            context['previous'] = self.object.get_previous()
            context['next'] = self.object.get_next()

        if dates:
            context['dates'] = dates
            date = self.request.GET.get('date')
            if date:
                try:
                    date = parse_datetime(date).date()
                except ValueError:
                    date = None
            if not date:
                date = context['dates'][-1]
            context['date'] = date

            journeys = journeys.filter(datetime__date=date).order_by('datetime')
            # calls = Call.objects.filter(journey=OuterRef('pk'))
            # locations = VehicleLocation.objects.filter(journey=OuterRef('pk'))
            journeys = journeys.select_related('service')

            try:
                r = redis.from_url(settings.CELERY_BROKER_URL)
                pipe = r.pipeline()
                for journey in journeys:
                    pipe.exists(f'journey{journey.id}')
                locations = pipe.execute()
                previous = None
                for i, journey in enumerate(journeys):
                    journey.locations = locations[i]
                    if journey.locations:
                        if previous:
                            previous.next = journey
                            journey.previous = previous
                        previous = journey
            except redis.exceptions.ConnectionError:
                pass

            context['journeys'] = journeys

        return context


def edit_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle.objects.select_related('vehicle_type', 'livery', 'operator'), id=vehicle_id)
    if not vehicle.editable():
        raise Http404
    submitted = False
    revision = None
    initial = {
        'operator': vehicle.operator,
        'reg': vehicle.reg,
        'vehicle_type': vehicle.vehicle_type,
        'features': vehicle.features.all(),
        'colours': str(vehicle.livery_id or vehicle.colours),
        'other_colour': '#ffffff',
        'branding': vehicle.branding,
        'name': vehicle.name,
        'previous_reg': vehicle.data and vehicle.data.get('Previous reg') or None,
        'depot': vehicle.data and vehicle.data.get('Depot') or None,
        'notes': vehicle.notes,
        'user': request.COOKIES.get('username'),
        'withdrawn': vehicle.withdrawn
    }
    if vehicle.fleet_code:
        initial['fleet_number'] = vehicle.fleet_code
    elif vehicle.fleet_number is not None:
        initial['fleet_number'] = str(vehicle.fleet_number)

    username = None

    if request.method == 'POST':
        form = EditVehicleForm(request.POST, initial=initial, operator=vehicle.operator, vehicle=vehicle)
        if not form.has_really_changed():
            form.add_error(None, 'You haven\'t changed anything')
        elif form.is_valid():
            data = {key: form.cleaned_data[key] for key in form.changed_data}
            now = timezone.now()
            username = form.cleaned_data.get('user')
            ip_address = request.META['REMOTE_ADDR']
            revision = do_revision(vehicle, data)
            if revision:
                revision.datetime = now
                if username:
                    revision.username = username
                if request.user.is_authenticated():
                    revision.user = request.user
                revision.ip_address = ip_address
                revision.save()

            form = None

            if 'user' in data:
                del data['user']

            if data:
                edit = get_vehicle_edit(vehicle, data, now, username, request)
                edit.save()
                if 'features' in data:
                    for feature in vehicle.features.all():
                        if feature not in data['features']:
                            VehicleEditFeature.objects.create(
                                edit=edit,
                                feature=feature,
                                add=False
                            )
                    for feature in data['features']:
                        edit.features.add(feature)
                submitted = True
    else:
        form = EditVehicleForm(initial=initial, operator=vehicle.operator, vehicle=vehicle)

    if vehicle.operator:
        depots = vehicle.operator.vehicle_set.distinct('data__Depot').values_list('data__Depot', flat=True)
    else:
        depots = ()

    if vehicle.operator:
        breadcrumb = [vehicle.operator, Vehicles(vehicle.operator), vehicle]
    else:
        breadcrumb = [vehicle]

    response = render(request, 'edit_vehicle.html', {
        'breadcrumb': breadcrumb,
        'form': form,
        'depots': depots,
        'object': vehicle,
        'vehicle': vehicle,
        'previous': vehicle.get_previous(),
        'next': vehicle.get_next(),
        'submitted': submitted,
        'revision': revision,
        'pending_edits': form and vehicle.vehicleedit_set.filter(approved=None).exists()
    })

    if username and username != initial['user']:
        response.set_cookie('username', username, 60 * 60 * 24 * 31, httponly=True, samesite='Strict')

    return response


def vehicle_history(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    revisions = vehicle.vehiclerevision_set.select_related('from_operator', 'to_operator').order_by('-id')
    return render(request, 'vehicle_history.html', {
        'breadcrumb': [vehicle.operator, Vehicles(vehicle.operator), vehicle],
        'vehicle': vehicle,
        'revisions': revisions
    })


def vehicles_history(request):
    revisions = VehicleRevision.objects.all().select_related('vehicle', 'from_operator', 'to_operator')
    revisions = revisions.order_by('-id')
    paginator = Paginator(revisions, 100)
    page = request.GET.get('page')
    return render(request, 'vehicle_history.html', {
        'revisions': paginator.get_page(page)
    })


class JourneyDetailView(DetailView):
    model = VehicleJourney
    queryset = model.objects.select_related('vehicle', 'service')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['breadcrumb'] = [self.object.service]
        context['calls'] = self.object.call_set.order_by('visit_number').select_related('stop__locality')

        return context


def journey_json(request, pk):
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        locations = r.lrange(f'journey{pk}', 0, -1)
        if locations:
            locations = [json.loads(location) for location in locations]
        else:
            locations = ()
    except redis.exceptions.ConnectionError:
        locations = ()
    return JsonResponse([{
        'coordinates': location[1],
        'delta': location[3],
        'direction': location[2],
        'datetime': location[0]
    } for location in locations], safe=False)


def location_detail(request, location_id):
    locations = VehicleLocation.objects.select_related('journey__vehicle', 'journey__service')
    locations = locations.defer('journey__service__geometry', 'journey__service__search_vector')
    location = get_object_or_404(locations, id=location_id)
    return render(request, 'location_detail.html', {
        'location': location
    })


def journey_debug(request, pk):
    journey = get_object_or_404(VehicleJourney, id=pk)
    return JsonResponse(journey.data or {})


def siri(request):
    body = request.body.decode()
    if not body:
        return HttpResponse()
    if 'HeartbeatNotification' in body:
        for _, element in ET.iterparse(request):
            if element.tag == '{http://www.siri.org.uk/siri}ProducerRef':
                cache.set(f'Heartbeat:{element.text}', True, 300)  # 5 minutes
                break
    elif 'VehicleLocation' in body:
        handle_siri_vm.delay(body)
    elif 'SituationElement' in body:
        handle_siri_sx.delay(body)
    else:
        handle_siri_et.delay(body)
    return HttpResponse(f"""<?xml version="1.0" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
  <DataReceivedAcknowledgement>
    <ResponseTimestamp>{timezone.localtime().isoformat()}</ResponseTimestamp>
    <Status>true</Status>
  </DataReceivedAcknowledgement>
</Siri>""", content_type='text/xml')
