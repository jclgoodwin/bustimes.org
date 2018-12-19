# coding=utf-8
"""View definitions."""
import os
import json
import ciso8601
from datetime import timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction
from django.db.models import Max, Q
from django.http import (HttpResponse, JsonResponse, Http404,
                         HttpResponseBadRequest)
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import last_modified
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.conf import settings
from django.contrib.gis.geos import Polygon, Point
from django.contrib.gis.db.models.functions import Distance
from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.core.mail import EmailMessage
from haystack.query import SearchQuerySet
from departures import live
from .utils import format_gbp
from .models import (Region, StopPoint, AdminArea, Locality, District, Operator, Service, Note, Journey, Place,
                     Registration, Variation, Vehicle, VehicleLocation, DataSource)
from .forms import ContactForm


def index(request):
    """The home page with a list of regions"""
    return render(request, 'index.html', {
        'regions': True
    })


def not_found(request, exception):
    """Custom 404 handler view"""
    context = None
    if request.resolver_match:
        view_name = request.resolver_match.view_name.lower()
        if view_name == 'service_detail':
            slug = request.resolver_match.kwargs.get('slug')
            service = Service.objects.filter(Q(service_code=slug) | Q(slug=slug)).defer('geometry').first()
            localities = Locality.objects.filter(stoppoint__service=service).defer('latlong').distinct()
            context = {
                'service': service,
                'localities': localities,
            }
        else:
            context = {
                'exception': exception
            }
    response = render(request, '404.html', context)
    response.status_code = 404
    return response


def offline(request):
    """Offline page (for service worker)"""
    return render(request, 'offline.html')


def contact(request):
    """Contact page with form"""
    submitted = False
    if request.method == 'POST':
        form = ContactForm(request.POST, request=request)
        if form.is_valid():
            subject = form.cleaned_data['message'][:50].splitlines()[0]
            body = '{}\n\n{}'.format(form.cleaned_data['message'], form.cleaned_data['referrer'])
            message = EmailMessage(
                subject,
                body,
                '"%s" <%s>' % (form.cleaned_data['name'], 'robot@bustimes.org'),
                ('contact@bustimes.org',),
                reply_to=(form.cleaned_data['email'],),
            )
            message.send()
            submitted = True
    else:
        referrer = request.META.get('HTTP_REFERER')
        form = ContactForm(initial={
            'referrer': referrer
        })
    return render(request, 'contact.html', {
        'form': form,
        'submitted': submitted
    })


@csrf_exempt
def awin_transaction(request):
    json_string = request.POST.get('AwinTransactionPush') or request.body
    if not json_string:
        return HttpResponseBadRequest()
    data = json.loads(json_string)
    message = '\n'.join('%s: %s' % pair for pair in data.items())
    EmailMessage(
        '💷 {} on a {} transaction'.format(format_gbp(data['commission']), format_gbp(data['transactionAmount'])),
        message,
        '%s <%s>' % ('🚌⏰🤖', 'robot@bustimes.org'),
        ('contact@bustimes.org',)
    ).send()
    return HttpResponse()


def cookies(request):
    """Cookie policy"""
    return render(request, 'cookies.html')


def data(request):
    """Data sources"""
    return render(request, 'data.html')


def hugemap(request):
    """The biggish JavaScript map"""
    return render(request, 'map.html')


def get_bounding_box(request):
    return Polygon.from_bbox(
        [request.GET[key] for key in ('xmin', 'ymin', 'xmax', 'ymax')]
    )


def stops(request):
    """JSON endpoint accessed by the JavaScript map,
    listing the active StopPoints within a rectangle,
    in standard GeoJSON format
    """
    try:
        bounding_box = get_bounding_box(request)
    except KeyError:
        return HttpResponseBadRequest()

    results = StopPoint.objects.filter(
        latlong__within=bounding_box, active=True
    ).select_related('locality').annotate(
        distance=Distance('latlong', bounding_box.centroid)
    ).order_by('distance').defer('osm', 'locality__latlong')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': tuple(stop.latlong)
            },
            'properties': {
                'name': stop.get_qualified_name(),
                'url': stop.get_absolute_url(),
            }
        } for stop in results]
    })


def vehicles(request):
    return render(request, 'vehicles.html')


def vehicles_last_modified(request):
    locations = VehicleLocation.objects.filter(current=True)
    if 'service' in request.GET:
        locations = locations.filter(service_id=request.GET['service'])

    try:
        location = locations.values('datetime').latest('datetime')
        return location['datetime']
    except VehicleLocation.DoesNotExist:
        return


@last_modified(vehicles_last_modified)
def vehicles_json(request):
    locations = VehicleLocation.objects.filter(current=True).order_by()

    try:
        bounding_box = get_bounding_box(request)
        locations = locations.filter(latlong__within=bounding_box)
    except KeyError:
        pass

    if 'service' in request.GET:
        locations = locations.filter(service_id=request.GET['service'])

    locations = locations.select_related('service', 'vehicle__operator', 'vehicle__vehicle_type')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': tuple(location.latlong),
            },
            'properties': {
                'vehicle': location.vehicle and {
                    'url': location.vehicle.get_absolute_url(),
                    'name': str(location.vehicle),
                    'type': location.vehicle.vehicle_type and str(location.vehicle.vehicle_type),
                },
                'operator': location.vehicle and location.vehicle.operator and str(location.vehicle.operator),
                'service': location.service and {
                    'line_name': location.service.line_name,
                    'url': location.service.get_absolute_url(),
                },
                'journey': location.get_label(),
                'delta': location.early,
                'direction': location.heading,
                'datetime': location.datetime
            }
        } for location in locations]
    })


def service_vehicles_history(request, slug):
    service = get_object_or_404(Service, slug=slug)
    date = request.GET.get('date')
    if date:
        try:
            date = ciso8601.parse_datetime(date).date()
        except ValueError:
            date = None
    if not date:
        try:
            date = service.vehiclelocation_set.values_list('datetime', flat=True).latest('datetime').date()
        except VehicleLocation.DoesNotExist:
            date = timezone.now().date()
    locations = service.vehiclelocation_set.filter(datetime__date=date).select_related('vehicle')
    operator = service.operator.select_related('region').first()
    return render(request, 'busstops/vehicle_detail.html', {
        'breadcrumb': [operator.region, operator, service],
        'date': date,
        'object': service,
        'locations': locations.order_by('vehicle', 'id')
    })


class UppercasePrimaryKeyMixin(object):
    """Normalises the primary key argument to uppercase"""
    def get_object(self, queryset=None):
        """Given a pk argument like 'ea' or 'sndr',
        convert it to 'EA' or 'SNDR',
        then otherwise behaves like ordinary get_object
        """
        primary_key = self.kwargs.get('pk')
        if primary_key is not None and '-' not in primary_key and not primary_key.isupper():
            self.kwargs['pk'] = primary_key.upper()
        return super().get_object(queryset)


class RegionDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single region and the administrative areas in it"""

    model = Region

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['areas'] = self.object.adminarea_set.exclude(name='')
        if len(context['areas']) == 1:
            context['districts'] = context['areas'][0].district_set.filter(locality__stoppoint__active=True).distinct()
            del context['areas']
        context['operators'] = self.object.operator_set.filter(service__current=True).distinct()
        if len(context['operators']) == 1:
            context['services'] = sorted(context['operators'][0].service_set.filter(current=True).defer('geometry'),
                                         key=Service.get_order)

        return context


class PlaceDetailView(DetailView):
    model = Place
    queryset = model.objects.select_related('source')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['places'] = self.model.objects.filter(polygon__coveredby=self.object.polygon).exclude(id=self.object.id)

        if 'Singapore' in self.object.source.name:
            breadcrumb = list(self.model.objects.filter(polygon__covers=self.object.polygon).exclude(id=self.object.id))
            context['breadcrumb'] = [Region.objects.get(id='SG')] + breadcrumb

        if not context['places']:
            context['stops'] = StopPoint.objects.filter(latlong__coveredby=self.object.polygon)

        return context


class AdminAreaDetailView(DetailView):
    """A single administrative area,
    and the districts, localities (or stops) in it
    """

    model = AdminArea
    queryset = model.objects.select_related('region')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Districts in this administrative area
        context['districts'] = self.object.district_set.filter(locality__stoppoint__active=True).distinct()

        # Districtless localities in this administrative area
        context['localities'] = self.object.locality_set.filter(
            Q(stoppoint__active=True) | Q(locality__stoppoint__active=True),
            district=None,
            parent=None
        ).defer('latlong').distinct()

        if not (context['localities'] or context['districts']):
            context['services'] = sorted(Service.objects.filter(stops__admin_area=self.object,
                                                                current=True).distinct().defer('geometry'),
                                         key=Service.get_order)
            context['modes'] = {service.mode for service in context['services'] if service.mode}
        context['breadcrumb'] = [self.object.region]
        return context

    def render_to_response(self, context):
        if 'services' not in context and len(context['districts']) + len(context['localities']) == 1:
            if not context['localities']:
                return redirect(context['districts'][0])
            return redirect(context['localities'][0])
        return super().render_to_response(context)


class DistrictDetailView(DetailView):
    """A single district, and the localities in it"""

    model = District
    queryset = model.objects.select_related('admin_area', 'admin_area__region')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['localities'] = self.object.locality_set.filter(
            Q(stoppoint__active=True) | Q(locality__stoppoint__active=True),
        ).defer('latlong').distinct()
        context['breadcrumb'] = [self.object.admin_area.region, self.object.admin_area]
        return context

    def render_to_response(self, context):
        if len(context['localities']) == 1:
            return redirect(context['localities'][0])
        return super().render_to_response(context)


class LocalityDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single locality, its children (if any), and the stops in it"""

    model = Locality
    queryset = model.objects.select_related(
        'admin_area', 'admin_area__region', 'district', 'parent'
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['localities'] = self.object.locality_set.filter(
            Q(stoppoint__active=True) |
            Q(locality__stoppoint__active=True),
        ).defer('latlong').distinct()

        context['adjacent'] = Locality.objects.filter(
            Q(neighbour=self.object) |
            Q(adjacent=self.object)
        ).filter(
            Q(stoppoint__active=True) |
            Q(locality__stoppoint__active=True),
        ).defer('latlong').distinct()

        context['stops'] = self.object.stoppoint_set.filter(active=True).defer('osm')

        if not (context['localities'] or context['stops']):
            raise Http404('Sorry, it looks like no services currently stop at {}'.format(self.object))
        elif context['stops']:
            context['services'] = sorted(Service.objects.filter(
                stops__locality=self.object,
                current=True
            ).defer('geometry').distinct(), key=Service.get_order)
            context['modes'] = {service.mode for service in context['services'] if service.mode}

        context['breadcrumb'] = [crumb for crumb in [
            self.object.admin_area.region,
            self.object.admin_area,
            self.object.district,
            self.object.parent
        ] if crumb is not None]

        return context


class StopPointDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A stop, other stops in the same area, and the services servicing it"""

    model = StopPoint
    queryset = model.objects.select_related('admin_area', 'admin_area__region',
                                            'locality', 'locality__parent',
                                            'locality__district')
    queryset = queryset.defer('osm', 'locality__latlong', 'locality__parent__latlong')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['services'] = sorted(
            self.object.service_set.filter(current=True).defer('geometry').distinct(),
            key=Service.get_order
        )

        if not (self.object.active or context['services']):
            raise Http404('Sorry, it looks like no services currently stop at {}'.format(self.object))

        departures = cache.get(self.object.atco_code)
        if not departures:
            bot = self.request.META.get('HTTP_X_BOT')
            departures, max_age = live.get_departures(self.object, context['services'], bot)
            if hasattr(departures['departures'], 'get_departures'):
                departures['departures'] = departures['departures'].get_departures()
            if max_age:
                cache.set(self.object.atco_code, departures, max_age)

        context.update(departures)
        if context['departures']:
            context['live'] = any(item.get('live') for item in context['departures'])

        text = ', '.join(part for part in (
            'on ' + self.object.street if self.object.street else None,
            'near ' + self.object.crossing if self.object.crossing else None,
            'near ' + self.object.landmark if self.object.landmark else None,
        ) if part is not None)
        if text:
            context['text'] = text[0].upper() + text[1:]

        context['modes'] = {service.mode for service in context['services'] if service.mode}

        region = self.object.get_region()

        nearby = None
        if self.object.stop_area_id is not None:
            nearby = StopPoint.objects.filter(stop_area=self.object.stop_area_id)
        elif self.object.locality or self.object.admin_area:
            nearby = StopPoint.objects.filter(common_name=self.object.common_name)
            if self.object.locality:
                nearby = nearby.filter(locality=self.object.locality)
            else:
                nearby = nearby.filter(admin_area=self.object.admin_area)
                if self.object.town:
                    nearby = nearby.filter(town=self.object.town)
        elif self.object.atco_code[:3] in {'je-', 'gg-'}:
            nearby = StopPoint.objects.filter(common_name__iexact=self.object.common_name,
                                              atco_code__startswith=self.object.atco_code[:3])
        if nearby is not None:
            context['nearby'] = nearby.filter(active=True).exclude(
                pk=self.object.pk
            ).defer('osm')

        context['breadcrumb'] = [crumb for crumb in (
            region,
            self.object.admin_area,
            self.object.locality and self.object.locality.district,
            self.object.locality and self.object.locality.parent,
            self.object.locality,
        ) if crumb is not None]
        return context


def stop_json(_, pk):
    stop = get_object_or_404(StopPoint, atco_code=pk)
    return JsonResponse({
        'atco_code': stop.atco_code,
        'naptan_code': stop.naptan_code,
        'common_name': stop.common_name,
        'landmark': stop.landmark,
        'street': stop.street,
        'crossing': stop.crossing,
        'indicator': stop.indicator,
        'latlong': tuple(stop.latlong),
        'stop_area': stop.stop_area_id,
        'locality': stop.locality_id,
        'suburb': stop.suburb,
        'town': stop.town,
        'locality_centre': stop.locality_centre,
        'heading': stop.heading,
        'bearing': stop.bearing,
        'stop_type': stop.stop_type,
        'bus_stop_type': stop.bus_stop_type,
        'timing_status': stop.timing_status,
        'admin_area': stop.admin_area_id,
        'active': stop.active,
    }, safe=False)


class OperatorDetailView(DetailView):
    "An operator and the services it operates"

    model = Operator
    queryset = model.objects.select_related('region')

    def get_object(self, **kwargs):
        try:
            return super().get_object(**kwargs)
        except Http404 as e:
            if 'slug' in self.kwargs:
                self.kwargs['pk'] = self.kwargs['slug'].upper()
                return super().get_object(**kwargs)
            raise e

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['services'] = sorted(self.object.service_set.filter(current=True).defer('geometry'),
                                     key=Service.get_order)
        if context['services']:
            context['notes'] = self.object.note_set.all()
            context['modes'] = {service.mode for service in context['services'] if service.mode}
            context['breadcrumb'] = [self.object.region]
        return context

    def render_to_response(self, context):
        if not context['services']:
            alternative = self.model.objects.filter(
                operatorcode__code=self.object.id,
                operatorcode__source__name='National Operator Codes',
                service__current=True
            ).first()
            if alternative:
                return redirect(alternative)
            raise Http404('Sorry, it looks like no services are currently operated by {}'.format(self.object))
        return super().render_to_response(context)


def operator_vehicles(request, slug):
    operator = get_object_or_404(Operator, slug=slug)
    return render(request, 'operator_vehicles.html', {
        'breadcrumb': [operator.region, operator],
        'object': operator,
        'today': timezone.now().date(),
        'vehicles': operator.vehicle_set.order_by('fleet_number').select_related('vehicle_type',
                                                                                 'latest_location__service')
    })


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = model.objects.select_related('region').prefetch_related('operator')

    def get_object(self, **kwargs):
        try:
            return super().get_object(**kwargs)
        except Http404:
            self.kwargs['pk'] = self.kwargs['slug']
            return super().get_object(**kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.object.current or 'pk' in self.kwargs:
            return context

        context['operators'] = self.object.operator.all()
        context['notes'] = Note.objects.filter(Q(operators__in=context['operators']) | Q(services=self.object)
                                               | Q(services=None, operators=None))
        context['links'] = []

        if self.object.show_timetable and not self.object.timetable_wrong:
            date = self.request.GET.get('date')
            today = timezone.now().date()
            if date:
                try:
                    date = ciso8601.parse_datetime(date).date()
                    if date < today:
                        date = None
                except ValueError:
                    date = None
            if not date:
                date = self.object.servicedate_set.filter(date__gte=today).first()
                if date:
                    date = date.date
            if not date:
                next_usage = self.object.journey_set.filter(datetime__date__gte=today).first()
                if next_usage:
                    date = next_usage.datetime.date()
            context['timetables'] = self.object.get_timetables(date)
        else:
            date = None

        if not context.get('timetables') or not context['timetables'][0].groupings:
            context['stopusages'] = self.object.stopusage_set.all().select_related(
                'stop__locality'
            ).defer('stop__osm', 'stop__locality__latlong')
            context['has_minor_stops'] = any(s.is_minor() for s in context['stopusages'])
        else:
            stops_dict = {stop.pk: stop for stop in self.object.stops.all().select_related(
                'locality').defer('osm', 'latlong', 'locality__latlong')}
            for table in context['timetables']:
                table.groupings = [grouping for grouping in table.groupings
                                   if type(grouping.rows) is not list or
                                   grouping.rows and grouping.rows[0].times]
                for grouping in table.groupings:
                    grouping.rows = [row for row in grouping.rows if any(row.times)]
                    for row in grouping.rows:
                        row.part.stop.stop = stops_dict.get(row.part.stop.atco_code)

        if bool(context['operators']):
            operator = context['operators']
            context['breadcrumb'] = (self.object.region, context['operators'][0])
            if self.object.is_megabus():
                context['links'].append({
                    'url': self.object.get_megabus_url(),
                    'text': 'Buy tickets from megabus.com'
                })
            else:
                for operator in context['operators']:
                    if operator.is_national_express():
                        context['links'].append({
                            'url': operator.get_national_express_url(),
                            'text': 'Buy tickets on the {} website'.format(operator.name)
                        })
                    elif operator.url.startswith('http'):
                        context['links'].append({
                            'url': operator.url,
                            'text': '{} website'.format(operator.name)
                        })
                    if operator.twitter:
                        for handle in operator.twitter.split():
                            context['links'].append({
                                'url': 'https://twitter.com/{}'.format(handle),
                                'text': '@{} on Twitter'.format(handle)
                            })
        else:
            context['breadcrumb'] = (self.object.region,)

        traveline_url, traveline_text = self.object.get_traveline_link(date)
        if traveline_url:
            context['links'].append({
                'url': traveline_url,
                'text': 'Timetable on the %s website' % traveline_text
            })

        if self.object.description and self.object.line_name:
            related = Service.objects.filter(current=True).exclude(pk=self.object.pk).defer('geometry')
            related = related.filter(Q(description=self.object.description) |
                                     Q(line_name=self.object.line_name, operator__in=context['operators']))
            context['related'] = sorted(related, key=Service.get_order)

        return context

    def render_to_response(self, context):
        if not self.object.current:
            alternative = Service.objects.filter(
                description=self.object.description,
                current=True
            ).defer('geometry').first() or Service.objects.filter(
                line_name=self.object.line_name,
                stopusage__stop_id__in=self.object.stopusage_set.values_list('stop_id', flat=True),
                current=True
            ).defer('geometry').first()

            if alternative is not None:
                return redirect(alternative, permanent=True)

            raise Http404()

        if 'pk' in self.kwargs:
            return redirect(self.object, permanent=True)

        return super().render_to_response(context)


class RegistrationView(ListView):
    model = Registration

    def get_queryset(self):
        return self.model.objects.filter(**self.kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        object_list = self.object_list.annotate(
            date=Max('variation__effective_date')
        ).order_by('-date')

        cancelled_statuses = ('Admin Cancelled', 'Cancellation', 'Cancelled', 'Expired', 'Refused', 'Withdrawn')
        context['cancelled'] = object_list.filter(registration_status__in=cancelled_statuses)
        context['object_list'] = object_list.exclude(pk__in=context['cancelled'])

        if not (context['object_list'] or context['cancelled']):
            raise Http404()

        context['operator'] = self.object_list.select_related('operator__operator__region').first().operator
        if context['operator']:
            context['breadcrumb'] = [context['operator'].operator.region, context['operator'].operator]

        return context


class VariationView(ListView):
    model = Variation

    def get_queryset(self):
        return self.model.objects.filter(**self.kwargs).select_related('registration__operator__operator__region')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.object_list:
            raise Http404()

        if self.object_list[0].registration.operator:
            context['breadcrumb'] = [
                self.object_list[0].registration.operator.operator.region,
                self.object_list[0].registration.operator.operator,
                self.object_list[0].registration.operator
            ]

        return context


def service_xml(_, pk):
    try:
        service = Service.objects.get(slug=pk)
    except Service.DoesNotExist:
        service = get_object_or_404(Service, pk=pk)
    if service.region_id == 'NI':
        path = os.path.join(settings.DATA_DIR, 'NI', service.pk + '.json')
        with open(path) as open_file:
            bodies = open_file.read()
    else:
        bodies = (xml_file.read().decode() for xml_file in service.get_files_from_zipfile())
    return HttpResponse(bodies, content_type='text/plain')


class OperatorSitemap(Sitemap):
    protocol = 'https'

    def items(self):
        return Operator.objects.filter(service__current=True).distinct()


class ServiceSitemap(Sitemap):
    protocol = 'https'

    def items(self):
        return Service.objects.filter(current=True)


def journey(request):
    origin = request.GET.get('from')
    from_q = request.GET.get('from_q')
    destination = request.GET.get('to')
    to_q = request.GET.get('to_q')

    if origin:
        origin = get_object_or_404(Locality, slug=origin)
    if from_q:
        from_options = SearchQuerySet().models(Locality).filter(content=from_q).load_all()
        if from_options.count() == 1:
            origin = from_options[0].object
            from_options = None
        elif origin not in from_options:
            origin = None
    else:
        from_options = None

    if destination:
        destination = get_object_or_404(Locality, slug=destination)
    if to_q:
        to_options = SearchQuerySet().models(Locality).filter(content=to_q).load_all()
        if to_options.count() == 1:
            destination = to_options[0].object
            to_options = None
        elif destination not in to_options:
            destination = None
    else:
        to_options = None

    if origin and destination:
        journeys = Journey.objects.filter(
            stopusageusage__stop__locality=origin
        ).filter(stopusageusage__stop__locality=destination)
    else:
        journeys = None

    return render(request, 'journey.html', {
        'from': origin,
        'from_q': from_q or origin or '',
        'from_options': from_options,
        'to': destination,
        'to_q': to_q or destination or '',
        'to_options': to_options,
        'journeys': journeys
    })


class VehicleDetailView(DetailView):
    model = Vehicle
    queryset = model.objects.select_related('operator', 'operator__region')

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
        if not date:
            try:
                date = self.object.vehiclelocation_set.values_list('datetime', flat=True).latest('datetime').date()
            except VehicleLocation.DoesNotExist:
                date = timezone.now().date()
        context['date'] = date
        context['locations'] = self.object.vehiclelocation_set.filter(datetime__date=date).select_related('service')
        return context


@transaction.atomic
def handle_siri_vm_vehicle(source, item):
    operator = item['OperatorRef']
    operator = {
        'WP': 'WHIP',
        'GP': 'GPLM',
        'CBLE': 'CBBH',
        'ATS': 'ARBB'
    }.get(operator, operator)
    if operator == 'UNIB':
        return
    try:
        operator = Operator.objects.get(pk=operator)
    except Operator.DoesNotExist as e:
        print(e, operator, item)
        return
    if operator.pk == 'SCCM':
        service = Service.objects.filter(operator__in=('SCCM', 'SCPB', 'SCHU', 'SCBD'))
    else:
        service = operator.service_set
    service = service.filter(current=True)
    line_name = item['PublishedLineName']
    if line_name.startswith('PR'):
        service = service.filter(pk__contains='-{}-'.format(line_name))
    else:
        if operator.pk == 'WHIP' and line_name == 'U':
            line_name = 'Universal U'
        service = service.filter(line_name=line_name)
    try:
        service = service.get()
    except Service.MultipleObjectsReturned:
        service = service.filter(Q(stops=item['OriginRef']) | Q(stops=item['DestinationRef'])).distinct().get()
    except (Service.MultipleObjectsReturned, Service.DoesNotExist) as e:
        print(e, operator.pk, line_name)
        service = None
    vehicle, created = Vehicle.objects.get_or_create(operator=operator, code=item['VehicleRef'], source=source)
    if not created and vehicle.latest_location and vehicle.latest_location.current:
        vehicle.latest_location.current = False
        vehicle.latest_location.save()
    vehicle.latest_location = VehicleLocation.objects.create(
        vehicle=vehicle,
        service=service,
        datetime=ciso8601.parse_datetime(item['RecordedAtTime']),
        latlong=Point(float(item['Longitude']), float(item['Latitude'])),
        source=source,
        heading=item['Bearing'],
        current=True
    )
    vehicle.save()


@csrf_exempt
def siri_vm(request):
    now = timezone.now()
    source, _ = DataSource.objects.update_or_create({
        'datetime': now
    }, name='SIRI POST')
    data = json.loads(request.body)
    for item in data:
        handle_siri_vm_vehicle(source, item)
    five_minutes_ago = now - timedelta(minutes=5)
    source.vehiclelocation_set.filter(current=True, datetime__lte=five_minutes_ago).update(current=False)
    return HttpResponse()
