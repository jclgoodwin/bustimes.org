import redis
import json
import xml.etree.cElementTree as ET
import datetime
import xmltodict
from urllib.parse import urlencode
from ciso8601 import parse_datetime
from haversine import haversine, haversine_vector, Unit

from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Min, Max, F, Case, When, Q
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.postgres.aggregates import StringAgg
from django.forms import BooleanField
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseBadRequest
from django.views.generic.detail import DetailView
from django.views.decorators.http import require_GET, require_POST
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from sql_util.utils import SubqueryCount

from buses.utils import varnish_ban
from busstops.utils import get_bounding_box
from busstops.models import Operator, Service
from bustimes.models import Garage, Trip, StopTime
from disruptions.views import siri_sx
from .models import Vehicle, VehicleJourney, VehicleEdit, VehicleEditFeature, VehicleRevision, Livery, VehicleEditVote
from .filters import VehicleEditFilter
from .forms import EditVehiclesForm, EditVehicleForm
from .utils import redis_client, get_vehicle_edit, do_revision, do_revisions
from .management.commands import import_bod_avl


class Vehicles:
    def __init__(self, operator):
        self.operator = operator

    def __str__(self):
        return 'Vehicles'

    def get_absolute_url(self):
        return reverse('operator_vehicles', args=(self.operator.slug,))


@require_GET
def vehicles(request):
    operators = Operator.objects.filter(
        Exists(Vehicle.objects.filter(operator=OuterRef('pk'), withdrawn=False))
    ).only('name', 'slug')

    new_operators = operators.annotate(
        min=Min('vehicle__id'),
    ).order_by('-min')[:36]

    operator_journeys = VehicleJourney.objects.filter(latest_vehicle__operator=OuterRef('id'))
    day_ago = timezone.now() - datetime.timedelta(days=1)
    status = operators.filter(
        Exists(operator_journeys),
        ~Exists(operator_journeys.filter(datetime__gte=day_ago))
    ).annotate(
        last_seen=Max('vehicle__latest_journey__datetime'),
    ).order_by(
        '-last_seen'
    )

    return render(request, 'vehicles.html', {
        'status': list(status),
        'new_operators': list(new_operators),
        'operators': list(operators)
    })


@require_GET
def map(request):
    return render(request, 'map.html', {
        'liveries_css_version': cache.get('liveries_css_version', 0)
    })


@require_GET
def liveries_css(request, version=None):
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

    vehicles = vehicles.annotate(
        vehicle_type_name=F('vehicle_type__name'),
        garage_name=Case(
            When(garage__name='', then='garage__code'),
            default='garage__name',
        )
    ).select_related('livery')

    submitted = False
    revisions = False
    breadcrumb = [operator.region, operator]

    form = request.path.endswith('/edit')

    now = timezone.localtime()

    if form:
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.trusted is False:
            raise PermissionDenied

        breadcrumb.append(Vehicles(operator))
        initial = {
            'operator': operator,
        }
        if request.method == 'POST':
            form = EditVehiclesForm(request.POST, initial=initial, operator=operator, user=request.user)
            vehicle_ids = request.POST.getlist('vehicle')
            if not vehicle_ids:
                form.add_error(None, 'Select some vehicles to change')
            if not form.has_really_changed():
                form.add_error(None, 'You haven\'t changed anything')
            elif form.is_valid():
                data = {key: form.cleaned_data[key] for key in form.changed_data}

                revisions, changed_fields = do_revisions(
                    Vehicle.objects.filter(id__in=vehicle_ids),
                    data,
                    request.user
                )
                revisions = [revision for revision in revisions if str(revision)]

                if revisions and changed_fields:
                    Vehicle.objects.bulk_update((revision.vehicle for revision in revisions), changed_fields)
                    for revision in revisions:
                        revision.datetime = now
                    VehicleRevision.objects.bulk_create(revisions)
                    revisions = len(revisions)
                    varnish_ban('/vehicles/history')

                if data:
                    # this will fetch the vehicles list
                    # - slightly important that it occurs before any change of operator
                    ticked_vehicles = [v for v in vehicles if str(v.id) in vehicle_ids]
                    edits = [get_vehicle_edit(vehicle, data, now, request) for vehicle in ticked_vehicles]
                    edits = VehicleEdit.objects.bulk_create(edit for edit, changed in edits if changed)
                    submitted = len(edits)
                    if 'features' in data:
                        for edit in edits:
                            edit.features.set(data['features'])
                form = EditVehiclesForm(initial=initial, operator=operator, user=request.user)
        else:
            form = EditVehiclesForm(initial=initial, operator=operator, user=request.user)

    vehicles = sorted(vehicles, key=lambda v: Service.get_line_name_order(v.fleet_code))
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
        # midnight or 12 hours ago, whichever happened first
        if now.hour >= 12:
            today = now - datetime.timedelta(hours=now.hour, minutes=now.minute)
            today = today.replace(second=0, microsecond=0)
        else:
            today = now - datetime.timedelta(hours=12)

        for vehicle in vehicles:
            if vehicle.latest_journey:
                when = vehicle.latest_journey.datetime
                vehicle.last_seen = {
                    'service': vehicle.latest_journey.route_name,
                    'when': when,
                    'today': when >= today
                }

    context = {
        'breadcrumb': breadcrumb,
        'parent': parent,
        'operators': parent and operators,
        'object': operator,
        'vehicles': vehicles,
        'paginator': paginator,
        'code_column': any(vehicle.fleet_number_mismatch() for vehicle in vehicles),
        'branding_column': any(vehicle.branding and vehicle.branding != 'None' for vehicle in vehicles),
        'name_column': any(vehicle.name for vehicle in vehicles),
        'notes_column': any(vehicle.notes and vehicle.notes != 'Spare ticket machine' for vehicle in vehicles),
        'garage_column': any(vehicle.garage_name for vehicle in vehicles),
        'features_column': features_column,
        'columns': columns,
        'edits': submitted,
        'revisions': revisions,
        'revision': revisions and revision,
        'form': form,
        'liveries_css_version': cache.get('liveries_css_version', 0)
    }

    if not parent and not form:
        context['map'] = any(hasattr(vehicle, 'last_seen') and vehicle.last_seen['today'] for vehicle in vehicles)

    return render(request, 'operator_vehicles.html', context)


@require_GET
def operator_map(request, slug):
    operator = get_object_or_404(Operator.objects.select_related('region'), slug=slug)

    return render(request, 'operator_map.html', {
        'object': operator,
        'operator': operator,
        'breadcrumb': [operator.region, operator],
        'liveries_css_version': cache.get('liveries_css_version', 0)
    })


@require_GET
def vehicles_json(request):

    try:
        bounds = get_bounding_box(request)
    except KeyError:
        bounds = None

    vehicles = Vehicle.objects.select_related('vehicle_type').annotate(
        feature_names=StringAgg('features__name', ', '),
        service_line_name=Coalesce('latest_journey__trip__route__line_name', 'latest_journey__service__line_name'),
        service_slug=F('latest_journey__service__slug')
    ).defer('data')

    if 'service__isnull' in request.GET:
        vehicles = vehicles.filter(
            latest_journey__service__isnull=BooleanField().to_python(request.GET['service__isnull'])
        )

    vehicle_ids = None
    service_ids = None

    if bounds is not None:
        # ids of vehicles within box
        xmin, ymin, xmax, ymax = bounds.extent

        # convert to kilometres (only for redis to convert back to degrees)
        width = haversine((ymin, xmax), (ymin, xmin)) or 1
        height = haversine((ymin, xmax), (ymax, xmax)) or 1

        try:
            vehicle_ids = redis_client.geosearch(
                'vehicle_location_locations',
                longitude=(xmax + xmin) / 2,
                latitude=(ymax + ymin) / 2,
                unit='km',
                width=width,
                height=height
            )
        except redis.exceptions.ResponseError as e:
            return HttpResponseBadRequest(e)
    else:
        if 'service' in request.GET:
            try:
                service_ids = [int(service_id) for service_id in request.GET['service'].split(',')]
            except ValueError:
                return HttpResponseBadRequest()
            vehicle_ids = list(redis_client.sunion(
                [f'service{service_id}vehicles' for service_id in service_ids]
            ))
        elif 'operator' in request.GET:
            vehicles = vehicles.filter(
                operator__in=request.GET['operator'].split(',')
            ).in_bulk()
        else:
            # ids of all vehicles
            vehicle_ids = redis_client.zrange('vehicle_location_locations', 0, -1)

    if vehicle_ids is None:
        vehicle_ids = list(vehicles.keys())

    vehicle_locations = redis_client.mget([f'vehicle{int(vehicle_id)}' for vehicle_id in vehicle_ids])

    if type(vehicles) is not dict:
        # remove expired items from 'vehicle_location_locations'
        to_remove = [vehicle_ids[i] for i, item in enumerate(vehicle_locations) if not item]

        if to_remove:
            redis_client.zrem('vehicle_location_locations', *to_remove)

        # only get vehicles with unexpired locations
        vehicles = vehicles.in_bulk([vehicle_ids[i] for i, item in enumerate(vehicle_locations) if item])

    locations = []

    trip = request.GET.get('trip')
    if trip:
        trip = int(trip)

    for i, item in enumerate(vehicle_locations):
        vehicle_id = int(vehicle_ids[i])
        if item:
            try:
                vehicle = vehicles[vehicle_id]
            except KeyError:
                continue  # vehicle was deleted?
            item = json.loads(item)
            item['vehicle'] = vehicle.get_json(item['heading'])
            if vehicle.service_line_name:
                item["service"] = {
                    "line_name": vehicle.service_line_name,
                    "url": f"/services/{vehicle.service_slug}"
                }

            if trip and 'trip_id' in item and item['trip_id'] == trip:
                vj = VehicleJourney(service_id=item['service_id'], trip_id=trip)
                progress = vj.get_progress(item)
                if progress:
                    item['progress'] = {
                        'prev_stop': progress.from_stop_id,
                        'next_stop': progress.to_stop_id,
                    }
                    prev_stop, next_stop = StopTime.objects.filter(trip=trip, id__gte=progress.from_stoptime)[:2]
                    when = parse_datetime(item['datetime'])
                    when = datetime.timedelta(hours=when.hour, minutes=when.minute, seconds=when.second)

                    prev_time = prev_stop.departure_or_arrival()
                    next_time = next_stop.arrival_or_departure()
                    if prev_time <= when <= next_time:
                        delay = 0
                    elif prev_time < when:
                        delay = (when - next_time).total_seconds()  # late
                    else:
                        delay = (when - prev_time).total_seconds()  # early
                    item['delay'] = delay
                    item['progress']['prev_time'] = prev_time
                    item['progress']['next_time'] = next_time

        if service_ids and (not item or item.get('service_id') not in service_ids):
            for service_id in service_ids:
                redis_client.srem(f'service{service_id}vehicles', vehicle_id)
        elif item:
            locations.append(item)

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
            pipe = redis_client.pipeline(transaction=False)
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


@require_GET
def service_vehicles_history(request, slug):
    service = get_object_or_404(Service.objects.with_line_names(), slug=slug)

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

        journeys = self.object.vehiclejourney_set.select_related('service')
        journeys = journeys.annotate(line_name=Coalesce('trip__route__line_name', 'service__line_name', 'route_name'))

        context = {
            **context,
            **journeys_list(
                self.request,
                journeys,
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
    vehicle = get_object_or_404(
        Vehicle.objects.select_related('vehicle_type', 'livery', 'operator', 'latest_journey'),
        id=vehicle_id
    )

    submitted = False
    revision = None
    initial = {
        'operator': vehicle.operator,
        'reg': vehicle.reg,
        'vehicle_type': vehicle.vehicle_type,
        'features': vehicle.features.all(),
        'colours': str(vehicle.livery_id or vehicle.colours),
        'branding': vehicle.branding,
        'name': vehicle.name,
        'previous_reg': vehicle.data and vehicle.data.get('Previous reg') or None,
        'notes': vehicle.notes,
        'withdrawn': vehicle.withdrawn,
        'spare_ticket_machine': vehicle.notes == 'Spare ticket machine'
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
            try:
                revision = do_revision(vehicle, data, request.user)
            except IntegrityError as e:
                if 'operator' in data:
                    form.add_error('operator', f"{data['operator']} already has a vehicle with the code {vehicle.code}")
                else:
                    raise e
            else:
                if revision:
                    revision.datetime = now
                    revision.save()
                    varnish_ban('/vehicles/history')

                form = None

                if data:
                    edit, changed = get_vehicle_edit(vehicle, data, now, request)
                    if changed:
                        edit.save()
                        submitted = True
                    if 'features' in data:
                        if not changed:  # .save() was not called before
                            edit.save()
                            submitted = True
                        for feature in vehicle.features.all():
                            if feature not in data['features']:
                                VehicleEditFeature.objects.create(edit=edit, feature=feature, add=False)
                        for feature in data['features']:
                            VehicleEditFeature.objects.create(edit=edit, feature=feature, add=True)
    else:
        form = EditVehicleForm(initial=initial, operator=vehicle.operator, vehicle=vehicle, user=request.user)

    if vehicle.operator:
        breadcrumb = [vehicle.operator, Vehicles(vehicle.operator), vehicle]
    else:
        breadcrumb = [vehicle]

    return render(request, 'edit_vehicle.html', {
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


def is_staff(user):
    return user.is_staff


@require_GET
@login_required
def vehicle_edits(request):
    edits = VehicleEdit.objects.filter(approved=None).order_by('-id')

    edits = edits.select_related('livery', 'vehicle__livery', 'user', 'vehicle__operator', 'vehicle__latest_journey')
    edits = edits.prefetch_related('vehicleeditfeature_set__feature', 'vehicle__features')

    order = request.GET.get('order')

    if order in ('score', '-score'):
        edits = edits.order_by(order)
    if order in ('edit_count', '-edit_count'):
        edit_count = SubqueryCount('vehicle__vehicleedit', filter=Q(approved=None))
        edits = edits.annotate(edit_count=edit_count)
        edits = edits.order_by(order, 'vehicle')

    f = VehicleEditFilter(request.GET, queryset=edits)

    paginator = Paginator(f.qs, 100)

    parameters = {key: value for key, value in request.GET.items() if key != 'page'}

    toggle_order = {
        'score': urlencode({**parameters, 'order': '-score' if order == 'score' else 'score'}),
        'vehicle': urlencode({**parameters, 'order': '-edit_count' if order == 'edit_count' else 'edit_count'})
    }

    parameters = urlencode(parameters)

    return render(request, 'vehicle_edits.html', {
        'filter': f,
        'parameters': parameters,
        'toggle_order': toggle_order,
        'edits': paginator.get_page(request.GET.get('page')),
        'liveries_css_version': cache.get('liveries_css_version', 0),
    })


@login_required
def vehicle_edit_vote(request, edit_id, direction):
    edit = get_object_or_404(VehicleEdit, id=edit_id)

    votes = edit.vehicleeditvote_set
    positive = direction == 'up'

    VehicleEditVote.objects.update_or_create(
        {"positive": positive},
        for_edit=edit,
        by_user=request.user
    )

    # a bit dodgy - a vote could change direction between the two count queries!
    edit.score = votes.filter(positive=True).count() - votes.filter(positive=False).count()
    edit.save(update_fields=['score'])

    return HttpResponse(edit.score)


@require_POST
@user_passes_test(is_staff)
def vehicle_edit_action(request, edit_id, action):
    edit = get_object_or_404(VehicleEdit, id=edit_id)

    if action == 'apply':
        edit.apply()
    else:
        if action == 'disapprove':
            edit.approved = False
        elif action == 'approve':
            edit.approved = True

        edit.save(update_fields=['approved'])

    return HttpResponse()


@require_GET
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


@require_GET
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


@require_GET
def journey_json(request, pk):
    journey = get_object_or_404(VehicleJourney.objects.select_related('trip'), pk=pk)

    data = {}

    if journey.trip:
        data['stops'] = [{
            'name': stop_time.stop.get_name_for_timetable() if stop_time.stop else stop_time.stop_code,
            'aimed_arrival_time': stop_time.arrival_time(),
            'aimed_departure_time': stop_time.departure_time(),
            'minor': stop_time.is_minor(),
            'coordinates': stop_time.stop and stop_time.stop.latlong and stop_time.stop.latlong.coords
        } for stop_time in journey.trip.stoptime_set.select_related('stop__locality')]

    locations = redis_client.lrange(f'journey{pk}', 0, -1)
    if locations:
        locations = (json.loads(location) for location in locations)
        data['locations'] = [{
            'coordinates': location[1],
            'delta': location[3],
            'direction': location[2],
            'datetime': parse_datetime(location[0])
        } for location in locations if location[1][0] and location[1][1]]
        data['locations'].sort(key=lambda location: location['datetime'])

    if journey.trip and locations:
        # only stops with coordinates
        stops = [stop for stop in data['stops'] if stop['coordinates']]
        if stops:
            haversine_vector_results = haversine_vector(
                [stop['coordinates'] for stop in stops],
                [location['coordinates'] for location in data['locations']],
                Unit.METERS,
                comb=True
            )
            for i, distances in enumerate(haversine_vector_results):
                minimum, index_of_minimum = min(((value, index) for index, value in enumerate(distances)))
                if minimum < 100:
                    stops[index_of_minimum]['actual_departure_time'] = data['locations'][i]['datetime']

    return JsonResponse(data)


@require_GET
def journey_debug(request, pk):
    journey = get_object_or_404(VehicleJourney, id=pk)
    return JsonResponse(journey.data or {})


@require_POST
def siri(request):
    body = request.body.decode()

    if 'HeartbeatNotification' in body:  # subscription heartbeat
        for _, element in ET.iterparse(request):
            if element.tag == '{http://www.siri.org.uk/siri}ProducerRef':
                cache.set(f'Heartbeat:{element.text}', True, 300)  # 5 minutes
                break

    elif 'VehicleLocation' in body:  # SIRI-VM
        command = import_bod_avl.Command()
        command.source_name = 'TransMach'
        command.do_source()

        data = xmltodict.parse(
            body,
            dict_constructor=dict,
            force_list=['VehicleActivity']
        )
        for item in data['Siri']['ServiceDelivery']['VehicleMonitoringDelivery']['VehicleActivity']:
            command.handle_item(item)

        command.save()

    else:  # SIRI-SX
        assert 'SituationElement' in body
        siri_sx(request)

    # ack
    return HttpResponse(f"""<?xml version="1.0" ?>
<Siri xmlns="http://www.siri.org.uk/siri" version="1.3">
  <DataReceivedAcknowledgement>
    <ResponseTimestamp>{timezone.now().isoformat()}</ResponseTimestamp>
    <Status>true</Status>
  </DataReceivedAcknowledgement>
</Siri>""", content_type='text/xml')
