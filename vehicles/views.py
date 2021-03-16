import redis
import json
import xml.etree.cElementTree as ET
import datetime
from haversine import haversine
from django.db.models import Exists, OuterRef
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.gis.db.models import Extent
from django.contrib.postgres.aggregates import StringAgg
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseNotAllowed
from django.views.generic.detail import DetailView
from django.urls import reverse
from django.utils import timezone
from busstops.utils import get_bounding_box
from busstops.models import Operator, Service
from bustimes.models import Garage, Trip, get_trip
from .models import Vehicle, VehicleJourney, VehicleEdit, VehicleEditFeature, VehicleRevision, Livery
from .forms import EditVehiclesForm, EditVehicleForm
from .utils import get_vehicle_edit, do_revision, do_revisions
from .tasks import handle_siri_vm, handle_siri_sx


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


def liveries_css(request):
    styles = []
    liveries = Livery.objects.all()
    for livery in liveries:
        selector = f'.livery-{livery.id}'
        css = f'background:{livery.left_css}'
        if livery.white_text:
            css = f'{css};color:#fff'
        styles.append(f'{selector}{{{css}}}')
        if livery.right_css != livery.left_css:
            styles.append(f'{selector}.right{{background:{livery.right_css}}}')
    return HttpResponse(''.join(styles), content_type='text/css')


def operator_vehicles(request, slug=None, parent=None):
    operators = Operator.objects.select_related('region')
    if slug:
        try:
            operator = operators.get(slug=slug.lower())
        except Operator.DoesNotExist:
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
        vehicles = vehicles.annotate(feature_names=StringAgg('features__name', ', '))
        pending_edits = VehicleEdit.objects.filter(approved=None, vehicle=OuterRef('id')).only('id')
        vehicles = vehicles.annotate(pending_edits=Exists(pending_edits))
        vehicles = vehicles.select_related('latest_journey')

    vehicles = vehicles.select_related('livery', 'vehicle_type')

    submitted = False
    revisions = False
    breadcrumb = [operator.region, operator]

    form = request.path.endswith('/edit')

    if form:
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.trusted is False:
            raise PermissionDenied

        breadcrumb.append(Vehicles(operator))
        initial = {
            'operator': operator,
            'other_colour': '#ffffff',
        }
        if request.method == 'POST':
            form = EditVehiclesForm(request.POST, initial=initial, operator=operator, user=request.user)
            if not form.has_really_changed():
                form.add_error(None, 'You haven\'t changed anything')
            elif form.is_valid():
                data = {key: form.cleaned_data[key] for key in form.changed_data}
                vehicle_ids = request.POST.getlist('vehicle')
                now = timezone.now()

                revisions, changed_fields = do_revisions(vehicle_ids, data, request.user)
                if revisions and changed_fields:
                    Vehicle.objects.bulk_update((revision.vehicle for revision in revisions), changed_fields)
                    for revision in revisions:
                        revision.datetime = now
                    VehicleRevision.objects.bulk_create(revisions)
                    revisions = len(revisions)

                if data:
                    # this will fetch the vehicles list
                    # - slightly important that it occurs before any change of operator
                    ticked_vehicles = [v for v in vehicles if str(v.id) in vehicle_ids]
                    edits = [get_vehicle_edit(vehicle, data, now, request) for vehicle in ticked_vehicles]
                    edits = VehicleEdit.objects.bulk_create(edit for edit in edits if edit)
                    submitted = len(edits)
                    if 'features' in data:
                        for edit in edits:
                            edit.features.set(data['features'])
                form = EditVehiclesForm(initial=initial, operator=operator, user=request.user)
        else:
            form = EditVehiclesForm(initial=initial, operator=operator, user=request.user)

    if operator.name == 'National Express':
        vehicles = sorted(vehicles, key=lambda v: v.notes)

    if not vehicles:
        raise Http404

    if parent:
        paginator = Paginator(vehicles, 1000)
        page = request.GET.get('page')
        vehicles = paginator.get_page(page)
    else:
        paginator = None

    features_column = not parent and any(vehicle.feature_names for vehicle in vehicles)

    columns = set(key for vehicle in vehicles if vehicle.data for key in vehicle.data)
    for vehicle in vehicles:
        vehicle.column_values = [vehicle.data and vehicle.data_get(key) or '' for key in columns]

    if not parent:
        today = timezone.localdate()
        for vehicle in vehicles:
            if vehicle.latest_journey:
                when = vehicle.latest_journey.datetime
                vehicle.last_seen = {
                    'service': vehicle.latest_journey.route_name,
                    'when': when,
                    'today': timezone.localdate(when) == today,
                }

    context = {
        'breadcrumb': breadcrumb,
        'parent': parent,
        'operators': parent and operators,
        'object': operator,
        'map': any(vehicle.latest_location_id for vehicle in vehicles),
        'vehicles': vehicles,
        'paginator': paginator,
        'code_column': any(vehicle.fleet_number_mismatch() for vehicle in vehicles),
        'branding_column': any(vehicle.branding and vehicle.branding != 'None' for vehicle in vehicles),
        'name_column': any(vehicle.name for vehicle in vehicles),
        'notes_column': any(vehicle.notes and vehicle.notes != 'Spare ticket machine' for vehicle in vehicles),
        'features_column': features_column,
        'columns': columns,
        'edits': submitted,
        'revisions': revisions,
        'revision': revisions and revision,
        'form': form,
    }

    if not parent and not form:
        context['map'] = any(vehicle.latest_location_id for vehicle in vehicles)

    return render(request, 'operator_vehicles.html', context)


def operator_map(request, slug):
    operator = get_object_or_404(Operator.objects.select_related('region'), slug=slug)

    services = operator.service_set.filter(current=True)
    extent = services.aggregate(Extent('geometry'))['geometry__extent']
    if not extent:
        extent = operator.vehicle_set.aggregate(Extent('latest_location__latlong'))['latest_location__latlong__extent']
    if not extent:
        raise Http404

    return render(request, 'operator_map.html', {
        'object': operator,
        'operator': operator,
        'breadcrumb': [operator.region, operator],
        'operator_id': operator.id,
        'extent': extent
    })


def vehicles_json(request):
    r = redis.from_url(settings.REDIS_URL)

    try:
        bounds = get_bounding_box(request)
    except KeyError:
        bounds = None

    if bounds is not None:
        # ids of vehicles within box
        xmin, ymin, xmax, ymax = bounds.extent

        # convert to kilometres (only for redis to convert back to degrees)
        width = haversine((ymin, xmax), (ymin, xmin))
        height = haversine((ymin, xmax), (ymax, xmax))

        vehicle_ids = r.execute_command(
            'GEOSEARCH',
            'vehicle_location_locations',
            'FROMLONLAT', (xmax + xmin) / 2, (ymax + ymin) / 2,
            'BYBOX', width, height, 'km'
        )

    else:
        if 'service' in request.GET:
            vehicle_ids = Vehicle.objects.filter(
                latest_journey__service__in=request.GET['service'].split(',')
            ).values_list('id', flat=True)
        elif 'operator' in request.GET:
            vehicle_ids = Vehicle.objects.filter(
                operator__in=request.GET['operator'].split(',')
            ).values_list('id', flat=True)
        else:
            # ids of all vehicles
            vehicle_ids = r.zrange('vehicle_location_locations', 0, -1)

    pipeline = r.pipeline(transaction=False)
    for vehicle_id in vehicle_ids:
        pipeline.get(f'vehicle{int(vehicle_id)}')
    vehicle_locations = pipeline.execute()

    locations = []
    service_ids = set()
    for item in vehicle_locations:
        if item:
            item = json.loads(item)
            locations.append(item)
            if 'service_id' in item and item['service_id']:
                service_ids.add(item['service_id'])

    services = Service.objects.only('line_name', 'line_brand', 'slug').in_bulk(service_ids)
    for item in locations:
        if 'service_id' in item:
            if item['service_id']:
                service = services[item['service_id']]
                item['service'] = {
                    'line_name': service.line_name,
                    'url': service.get_absolute_url()
                }
            del item['service_id']

    return JsonResponse(locations, safe=False)


def get_dates(journeys, vehicle=None, service=None):
    if vehicle:
        key = f'vehicle:{vehicle.id}:dates'
    else:
        key = f'service:{service.id}:dates'

    dates = cache.get(key)

    if not dates:
        dates = list(journeys.values_list('datetime__date', flat=True).distinct().order_by('datetime__date'))
        if dates:
            now = timezone.localtime()
            if dates[-1] == now.date():
                time_to_midnight = (
                    datetime.timedelta(days=1)
                    - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
                ).total_seconds()
                if time_to_midnight > 0:
                    cache.set(key, dates, time_to_midnight)

    return dates


def journeys_list(request, journeys, service=None, vehicle=None):
    dates = get_dates(journeys, service=service, vehicle=vehicle)
    if service and not dates:
        raise Http404

    context = {}

    if dates:
        context['dates'] = dates
        date = request.GET.get('date')
        if date:
            try:
                date = datetime.date.fromisoformat(date)
            except ValueError:
                date = None
        if not date:
            date = context['dates'][-1]
        context['date'] = date

        journeys = journeys.filter(datetime__date=date).select_related('trip').order_by('datetime')

        try:
            r = redis.from_url(settings.REDIS_URL)
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


def service_vehicles_history(request, slug):
    service = get_object_or_404(Service, slug=slug)

    context = journeys_list(
        request,
        service.vehiclejourney_set.select_related('vehicle'),
        service=service
    )

    operator = service.operator.select_related('region').first()
    return render(request, 'vehicles/vehicle_detail.html', {
        **context,
        'garages': Garage.objects.filter(Exists(Trip.objects.filter(route__service=service, garage=OuterRef('id')))),
        'breadcrumb': [operator, service],
        'object': service,
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region',
                                            'vehicle_type', 'livery').prefetch_related('features')
    slug_field = 'reg__iexact'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context = {
            **context,
            **journeys_list(
                self.request,
                self.object.vehiclejourney_set.select_related('service'),
                vehicle=self.object
            )
        }

        if 'journeys' in context:
            garages = set(journey.trip.garage_id for journey in context['journeys']
                          if journey.trip and journey.trip.garage_id)
            if len(garages) == 1:
                context['garage'] = Garage.objects.get(id=garages.pop())

        context['pending_edits'] = self.object.vehicleedit_set.filter(approved=None).exists()

        if self.object.operator:
            context['breadcrumb'] = [self.object.operator, Vehicles(self.object.operator)]

            context['previous'] = self.object.get_previous()
            context['next'] = self.object.get_next()

        return context


@login_required
def edit_vehicle(request, vehicle_id):
    if request.user.trusted is False:
        raise PermissionDenied
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
        'withdrawn': vehicle.withdrawn
    }
    if vehicle.fleet_code:
        initial['fleet_number'] = vehicle.fleet_code
    elif vehicle.fleet_number is not None:
        initial['fleet_number'] = str(vehicle.fleet_number)

    if request.method == 'POST':
        form = EditVehicleForm(request.POST,
                               initial=initial, operator=vehicle.operator, vehicle=vehicle, user=request.user)
        if not form.has_really_changed():
            form.add_error(None, 'You haven\'t changed anything')
        elif form.is_valid():
            data = {key: form.cleaned_data[key] for key in form.changed_data}
            now = timezone.now()
            revision = do_revision(vehicle, data, request.user)
            if revision:
                revision.datetime = now
                revision.save()

            form = None

            if data:
                edit = get_vehicle_edit(vehicle, data, now, request)
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
        form = EditVehicleForm(initial=initial, operator=vehicle.operator, vehicle=vehicle, user=request.user)

    if vehicle.operator:
        breadcrumb = [vehicle.operator, Vehicles(vehicle.operator), vehicle]
    else:
        breadcrumb = [vehicle]

    response = render(request, 'edit_vehicle.html', {
        'breadcrumb': breadcrumb,
        'form': form,
        'object': vehicle,
        'vehicle': vehicle,
        'previous': vehicle.get_previous(),
        'next': vehicle.get_next(),
        'submitted': submitted,
        'revision': revision,
        'pending_edits': form and vehicle.vehicleedit_set.filter(approved=None).exists()
    })

    return response


def vehicle_history(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    revisions = vehicle.vehiclerevision_set.select_related(
        'vehicle', 'from_livery', 'to_livery', 'from_type', 'to_type', 'user'
    ).order_by('-id')
    return render(request, 'vehicle_history.html', {
        'breadcrumb': [vehicle.operator, vehicle.operator and Vehicles(vehicle.operator), vehicle],
        'vehicle': vehicle,
        'revisions': revisions
    })


def vehicles_history(request):
    revisions = VehicleRevision.objects.all().select_related(
        'vehicle', 'from_livery', 'to_livery', 'from_type', 'to_type', 'user'
    )
    revisions = revisions.order_by('-id')
    paginator = Paginator(revisions, 100)
    page = request.GET.get('page')
    return render(request, 'vehicle_history.html', {
        'revisions': paginator.get_page(page)
    })


def journey_json(request, pk):
    data = {}

    journey = get_object_or_404(VehicleJourney, pk=pk)

    trip = None
    if journey.trip_id:
        try:
            trip = journey.trip
        except ObjectDoesNotExist:
            pass
    if not trip and journey.service_id and journey.code and '_' not in journey.code:
        trip = get_trip(journey.service_id, journey.code, journey.datetime)

    if trip:
        data['stops'] = [{
            'name': stop_time.stop.get_name_for_timetable() if stop_time.stop else stop_time.stop_code,
            'aimed_arrival_time': stop_time.arrival_time(),
            'aimed_departure_time': stop_time.departure_time(),
            'minor': stop_time.is_minor(),
            'coordinates': stop_time.stop and stop_time.stop.latlong and stop_time.stop.latlong.coords
        } for stop_time in trip.stoptime_set.select_related('stop__locality')]

    try:
        r = redis.from_url(settings.REDIS_URL)
        locations = r.lrange(f'journey{pk}', 0, -1)
        if locations:
            locations = (json.loads(location) for location in locations)
            data['locations'] = [{
                'coordinates': location[1],
                'delta': location[3],
                'direction': location[2],
                'datetime': location[0]
            } for location in locations if location[1][0] and location[1][1]]
            data['locations'].sort(key=lambda location: location['datetime'])
    except redis.exceptions.ConnectionError:
        pass

    return JsonResponse(data)


def journey_debug(request, pk):
    journey = get_object_or_404(VehicleJourney, id=pk)
    return JsonResponse(journey.data or {})


def siri(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
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
    else:
        assert 'SituationElement' in body
        handle_siri_sx.delay(body)
    return HttpResponse(f"""<?xml version="1.0" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
  <DataReceivedAcknowledgement>
    <ResponseTimestamp>{timezone.now().isoformat()}</ResponseTimestamp>
    <Status>true</Status>
  </DataReceivedAcknowledgement>
</Siri>""", content_type='text/xml')
