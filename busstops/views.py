# coding=utf-8
"""View definitions."""
import json
import requests
import datetime
from ukpostcodeutils import validation

from django.shortcuts import render, get_object_or_404, get_list_or_404, redirect
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import Union
from django.contrib.gis.db.models.functions import Distance
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q, Prefetch, F, Exists, OuterRef, Count, Min
from django.db.models.functions import Now
from django.http import HttpResponse, HttpResponseBadRequest, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.generic.detail import DetailView
from django.core.paginator import Paginator
from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.core.mail import EmailMessage
from departures import live
from disruptions.models import Situation, Consequence
from fares.forms import FaresForm
from bustimes.models import get_routes, StopTime
from vehicles.models import Vehicle
from vehicles.utils import redis_client
from vosa.models import Registration
from .utils import get_bounding_box
from .models import (Region, StopPoint, AdminArea, Locality, District, Operator,
                     Service, Place, ServiceColour, DataSource)
from .forms import ContactForm, SearchForm


operator_has_current_services = Exists(
    Service.objects.filter(current=True, operator=OuterRef('pk'))
)
operator_has_current_services_or_vehicles = operator_has_current_services | Exists(
    Vehicle.objects.filter(withdrawn=False, operator=OuterRef('pk'))
)


def get_colours(services):
    colours = set(service.colour_id for service in services if service.colour_id)
    if colours:
        return ServiceColour.objects.filter(id__in=colours)


def index(request):
    """The home page with a list of regions"""
    return render(request, 'index.html', {
        'regions': True
    })


def not_found(request, exception):
    """Custom 404 handler view"""
    if request.resolver_match:
        if request.resolver_match.url_name == 'service_detail' and exception.args:
            code = request.resolver_match.kwargs['slug']

            services = Service.objects.filter(current=True)

            if code.lower():
                try:
                    return redirect(services.get(servicecode__scheme='slug', servicecode__code=code))
                except Service.DoesNotExist:
                    pass
            try:
                return redirect(services.get(servicecode__scheme='ServiceCode', servicecode__code=code))
            except Service.DoesNotExist:
                pass

            service_code_parts = code.split('-')
            if len(service_code_parts) >= 4:
                suggestion = None

                # e.g. from '17-N4-_-y08-1' to '17-N4-_-y08':
                suggestion = services.filter(
                    service_code__icontains='_' + '-'.join(service_code_parts[:4]),
                ).first()

                # e.g. from '46-holt-circular-1' to '46-holt-circular-2':
                if not suggestion and code.lower():
                    if service_code_parts[-1].isdigit():
                        slug = '-'.join(service_code_parts[:-1])
                    else:
                        slug = '-'.join(service_code_parts)
                    suggestion = services.filter(slug__startswith=slug).first()

                if suggestion:
                    return redirect(suggestion)

        elif request.resolver_match.url_name == 'stoppoint_detail':
            try:
                return redirect(StopPoint.objects.get(naptan_code=request.resolver_match.kwargs['pk']))
            except StopPoint.DoesNotExist:
                pass

        context = {
            'exception': exception
        }
    else:
        context = None
    response = render(request, '404.html', context)
    response.status_code = 404
    return response


def offline(request):
    """Offline page (for service worker)"""
    return render(request, 'offline.html')


def robots_txt(request):
    return HttpResponse("User-Agent: *\nDisallow: /\n", content_type="text/plain")


def change_password(request):
    return redirect('/accounts/password_reset/')


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
                '"{}" <contactform@bustimes.org>'.format(form.cleaned_data['name']),
                ['contact@bustimes.org'],
                reply_to=[form.cleaned_data['email']],
            )
            message.send()
            submitted = True
    else:
        referrer = request.META.get('HTTP_REFERER')
        form = ContactForm(initial={
            'referrer': referrer,
            'message': request.GET.get('message')
        })
    return render(request, 'contact.html', {
        'form': form,
        'submitted': submitted
    })


def cookies(request):
    """Cookie policy"""
    return render(request, 'cookies.html')


def data(request):
    """Data sources"""
    sources = DataSource.objects.annotate(
        count=Count('route__service', filter=Q(route__service__current=True), distinct=True),
    ).order_by('url').filter(
        ~Q(count=0),
        ~Q(name__contains='GTFS'),
        ~Q(name='MET'),
    )
    return render(request, 'data.html', {
        'sources': sources
    })


def status(request):
    sources = DataSource.objects.annotate(
        count=Count('route__service', filter=Q(route__service__current=True), distinct=True),
    ).order_by('url')

    tnds = sources.filter(url__contains='tnds.basemap')

    return render(request, 'status.html', {
        'bod_avl_status': cache.get('bod_avl_status', []),
        'tfn_disruption_heartbeat': cache.get('Heartbeat:TransportAPI'),
        'tnds': tnds
    })


def stops(request):
    """JSON endpoint accessed by the JavaScript map,
    listing the active StopPoints within a rectangle,
    in standard GeoJSON format
    """
    try:
        bounding_box = get_bounding_box(request)
    except (KeyError, ValueError):
        return HttpResponseBadRequest()

    results = StopPoint.objects.filter(
        latlong__bboverlaps=bounding_box, active=True
    ).annotate(
        line_names=ArrayAgg('service__line_name', filter=Q(service__current=True), distinct=True)
    ).filter(line_names__isnull=False).select_related('locality').defer('locality__latlong')

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': stop.latlong.coords,
            },
            'properties': {
                'name': stop.get_qualified_name(),
                'indicator': stop.indicator,
                'bearing': stop.get_heading(),
                'url': stop.get_absolute_url(),
                'services': stop.get_line_names()
            }
        } for stop in results]
    })


class UppercasePrimaryKeyMixin:
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

        context['operators'] = Operator.objects.filter(
            operator_has_current_services_or_vehicles,
            Q(region=self.object) | Q(regions=self.object)
        ).distinct()

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

        stops = StopPoint.objects.filter(active=True)

        # Districts in this administrative area
        context['districts'] = self.object.district_set.filter(Exists(
            stops.filter(locality__district=OuterRef('pk'))
        ))

        # Districtless localities in this administrative area
        context['localities'] = self.object.locality_set.filter(
            Exists(stops.filter(locality=OuterRef('pk'))) | Exists(stops.filter(locality__parent=OuterRef('pk'))),
            district=None,
            parent=None
        ).defer('latlong')

        if not (context['localities'] or context['districts']):
            services = Service.objects.filter(current=True).defer('geometry', 'search_vector')
            services = services.filter(Exists(
                StopPoint.objects.filter(service=OuterRef('pk'), admin_area=self.object)
            ))
            context['services'] = sorted(services, key=Service.get_order)
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

        stops = StopPoint.objects.filter(active=True)
        context['localities'] = self.object.locality_set.filter(
            Exists(stops.filter(locality=OuterRef('pk'))) | Exists(stops.filter(locality__parent=OuterRef('pk'))),
        ).defer('latlong')

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

        stops = StopPoint.objects.filter(active=True)
        has_stops = Exists(stops.filter(locality=OuterRef('pk')))
        has_stops |= Exists(stops.filter(locality__parent=OuterRef('pk')))

        context['localities'] = self.object.locality_set.filter(has_stops).defer('latlong')

        context['adjacent'] = Locality.objects.filter(
            has_stops,
            adjacent=self.object
        ).defer('latlong')

        stops = self.object.stoppoint_set
        context['stops'] = stops.annotate(
            line_names=ArrayAgg('service__line_name', filter=Q(service__current=True), distinct=True)
        ).filter(line_names__isnull=False).defer('latlong')

        if not (context['localities'] or context['stops']):
            raise Http404(f'Sorry, it looks like no services currently stop at {self.object}')
        elif context['stops']:
            context['services'] = sorted(Service.objects.filter(
                Exists(self.object.stoppoint_set.filter(service=OuterRef('pk'))),
                current=True
            ).annotate(operators=ArrayAgg('operator__name')).defer('geometry'), key=Service.get_order)
            context['modes'] = {service.mode for service in context['services'] if service.mode}
            context['colours'] = get_colours(context['services'])
        context['breadcrumb'] = [crumb for crumb in [
            self.object.admin_area.region,
            self.object.admin_area,
            self.object.district,
            self.object.parent
        ] if crumb is not None]

        return context


class StopPointDetailView(DetailView):
    """A stop, other stops in the same area, and the services servicing it"""

    model = StopPoint
    queryset = model.objects.select_related('admin_area', 'admin_area__region',
                                            'locality', 'locality__parent',
                                            'locality__district')
    queryset = queryset.defer('locality__latlong', 'locality__parent__latlong')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        services = self.object.service_set.with_line_names().filter(current=True).defer('geometry')
        # services = services.annotate(direction=F('stopusage__direction'))
        services = services.annotate(operators=ArrayAgg('operator__name', distinct=True))
        context['services'] = sorted(services, key=Service.get_order)

        if not (self.object.active or context['services']):
            raise Http404(f'Sorry, it looks like no services currently stop at {self.object}')

        when = None
        date = self.request.GET.get('date')
        time_string = self.request.GET.get('time')
        if date:
            try:
                date = datetime.date.fromisoformat(date)
            except ValueError:
                pass
            else:
                time = datetime.time()
                if time_string:
                    try:
                        time = datetime.time.fromisoformat(time_string)
                    except ValueError:
                        pass
                when = datetime.datetime.combine(date, time)
                context['when'] = when

        departures, _ = live.get_departures(self.object, context['services'], when)
        context.update(departures)
        if context['departures']:
            context['live'] = any(item.get('live') for item in context['departures'])

        text = ', '.join(part for part in (
            'on ' + self.object.street if self.object.street else None,
            'near ' + self.object.crossing if self.object.crossing else None,
            'near ' + self.object.landmark if self.object.landmark else None,
        ) if part is not None)
        if text:
            context['text'] = f'{text[0].upper()}{text[1:]}'

        context['modes'] = {service.mode for service in context['services'] if service.mode}
        context['colours'] = get_colours(context['services'])

        region = self.object.get_region()

        nearby = StopPoint.objects.filter(active=True)

        if self.object.stop_area_id is not None:
            nearby = nearby.filter(stop_area=self.object.stop_area_id)
        elif self.object.locality or self.object.admin_area:
            nearby = nearby.filter(common_name=self.object.common_name)
            if self.object.locality:
                nearby = nearby.filter(locality=self.object.locality)
            else:
                nearby = nearby.filter(admin_area=self.object.admin_area)
                if self.object.town:
                    nearby = nearby.filter(town=self.object.town)
        else:
            nearby = None

        if nearby is not None:
            context['nearby'] = nearby.exclude(pk=self.object.pk).annotate(
                line_names=ArrayAgg('service__line_name', filter=Q(service__current=True), distinct=True)
            ).filter(line_names__isnull=False).defer('latlong')

        consequences = Consequence.objects.filter(stops=self.object)
        context['situations'] = Situation.objects.filter(
            publication_window__contains=Now(),
            consequence__stops=self.object,
            current=True
        ).distinct().prefetch_related(
            Prefetch('consequence_set', queryset=consequences, to_attr='consequences'),
            'link_set',
            'validityperiod_set'
        )

        context['breadcrumb'] = [crumb for crumb in (
            region,
            self.object.admin_area,
            self.object.locality and self.object.locality.district,
            self.object.locality and self.object.locality.parent,
            self.object.locality,
        ) if crumb is not None]
        return context


class OperatorDetailView(DetailView):
    "An operator and the services it operates"

    model = Operator
    queryset = model.objects.select_related('region').prefetch_related('licences')

    def get_object(self, **kwargs):
        try:
            return super().get_object(**kwargs)
        except Http404 as e:
            if 'slug' in self.kwargs:
                try:
                    return get_object_or_404(self.queryset, operatorcode__code=self.kwargs['slug'],
                                             operatorcode__source__name='slug')
                except Http404:
                    self.kwargs['pk'] = self.kwargs['slug'].upper()
                    return super().get_object(**kwargs)
            raise e

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        services = self.object.service_set.with_line_names().filter(current=True).defer('geometry', 'search_vector')
        services = services.annotate(start_date=Min('route__start_date'))
        context['services'] = sorted(services, key=Service.get_order)
        context['today'] = timezone.localdate()

        vehicles = self.object.vehicle_set.filter(withdrawn=False)

        context['vehicles'] = vehicles.exists()

        if context['services']:
            context['breadcrumb'] = [self.object.region]

            context['colours'] = get_colours(context['services'])

        if context['vehicles']:
            vehicles = vehicles.values_list('id', flat=True)
            context['map'] = redis_client.exists(*[f"vehicle{vehicle_id}" for vehicle_id in vehicles])

        return context

    def render_to_response(self, context):
        if not context['services'] and not context['vehicles']:
            alternative = Operator.objects.filter(
                operator_has_current_services,
                name=self.object.name,
            ).first()
            if alternative:
                return redirect(alternative)
            raise Http404
        return super().render_to_response(context)


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = model.objects.with_line_names().select_related('region', 'source').prefetch_related('operator')

    def get_object(self, **kwargs):
        try:
            return super().get_object(**kwargs)
        except Http404:
            return get_list_or_404(self.model, service_code=self.kwargs['slug'])[0]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if not self.object.current or self.object.slug != self.kwargs['slug']:
            return context

        operators = self.object.operator.all()
        context['operators'] = operators

        context['related'] = self.object.get_similar_services()

        if context['related']:
            context['colours'] = get_colours(context['related'])

        # timetable

        if not self.object.timetable_wrong:
            date = self.request.GET.get('date')
            if date:
                try:
                    date = datetime.date.fromisoformat(date)
                except ValueError:
                    date = None
            if context['related']:
                parallel = self.object.get_linked_services()
                context['linked_services'] = parallel
            else:
                parallel = []
            detailed = 'detailed' in self.request.GET
            timetable = self.object.get_timetable(date, parallel, detailed)
            if timetable and timetable.routes:

                if timetable.date or timetable.groupings:
                    context['timetable'] = timetable

                registrations = {route.registration_id for route in timetable.routes if route.registration_id}
                context['registrations'] = Registration.objects.filter(id__in=registrations)

        else:
            date = None

        if self.object.tracking and self.object.vehiclejourney_set.exists():
            context['vehicles'] = True

        # disruptions

        consequences = Consequence.objects.filter(Q(services=self.object) | (Q(operators__in=operators, services=None)))
        context['situations'] = Situation.objects.filter(
            Exists(consequences.filter(situation=OuterRef('id'))) | Q(situation_number=''),
            publication_window__contains=Now(),
            current=True
        ).distinct().prefetch_related(
            Prefetch('consequence_set', queryset=consequences.prefetch_related('stops'), to_attr='consequences'),
            'link_set',
            'validityperiod_set'
        )
        stop_situations = {}
        for situation in context['situations']:
            for consequence in situation.consequences:
                for stop in consequence.stops.all():
                    stop_situations[stop.atco_code] = situation

        if 'timetable' not in context or not timetable.groupings:
            context['stopusages'] = self.object.stopusage_set.all().select_related(
                'stop__locality'
            ).defer(
                'stop__latlong', 'stop__locality__latlong'
            )
            context['has_minor_stops'] = any(stop_usage.is_minor() for stop_usage in context['stopusages'])
            for stop_usage in context['stopusages']:
                if stop_usage.stop_id in stop_situations:
                    if stop_situations[stop_usage.stop_id].summary == 'Does not stop here':
                        stop_usage.suspended = True
                    else:
                        stop_usage.situation = True

        else:
            stops = StopPoint.objects.select_related('locality').defer('latlong', 'locality__latlong')
            stop_codes = (row.stop.atco_code for grouping in context['timetable'].groupings for row in grouping.rows)
            stops = stops.in_bulk(stop_codes)
            for atco_code in stops:
                if atco_code in stop_situations:
                    if stop_situations[atco_code].summary == 'Does not stop here':
                        stops[atco_code].suspended = True
                    else:
                        stops[atco_code].situation = True
            for grouping in context['timetable'].groupings:
                grouping.apply_stops(stops)

        try:
            context['breadcrumb'] = [Region.objects.filter(adminarea__stoppoint__service=self.object).distinct().get()]
        except (Region.DoesNotExist, Region.MultipleObjectsReturned):
            context['breadcrumb'] = [self.object.region]

        context['liveries_css_version'] = cache.get('liveries_css_version', 0)

        context['links'] = []

        if self.object.is_megabus():
            context['links'].append({
                'url': self.object.get_megabus_url(),
                'text': 'Buy tickets at megabus.com'
            })

        if operators:
            operator = operators[0]
            context['breadcrumb'].append(operator)
            context['payment_methods'] = []
            for method in operator.payment_methods.all():
                if 'app' in method.name and method.url:
                    context['app'] = method
                else:
                    context['payment_methods'].append(method)
            for operator in operators:
                if operator.name == 'National Express':
                    context["links"].append({
                        "url": "https://nationalexpress.prf.hn/click/camref:1011ljPYw",
                        "text": "Buy tickets at nationalexpress.com"
                    })
                    break

        tariffs = self.object.tariff_set
        tariffs = tariffs.filter(source__published=True)
        if tariffs.exists():
            if self.request.GET:
                context['fares'] = FaresForm(tariffs, self.request.GET)
            else:
                context['fares'] = FaresForm(tariffs)

        for url, text in self.object.get_traveline_links(date):
            context['links'].append({
                'url': url,
                'text': text
            })

        return context

    def render_to_response(self, context):
        if not self.object.current:
            services = Service.objects.filter(current=True).only('slug')
            alternative = None

            if self.object.line_name:
                alternative = services.filter(
                    line_name__iexact=self.object.line_name,
                    operator__in=self.object.operator.all(), stops__service=self.object
                ).first()
                if not alternative:
                    alternative = services.filter(
                        line_name__iexact=self.object.line_name,
                        stops__service=self.object
                    ).first()
                if not alternative:
                    alternative = services.filter(
                        line_name__iexact=self.object.line_name,
                        operator__in=self.object.operator.all()
                    ).first()

            if not alternative and self.object.description:
                alternative = services.filter(
                    description=self.object.description
                ).first()

            if alternative:
                return redirect(alternative)

            raise Http404()

        if self.object.slug != self.kwargs['slug']:
            return redirect(self.object)

        return super().render_to_response(context)


def service_timetable(request, service_id):
    service = get_object_or_404(Service.objects.defer('geometry'), id=service_id)
    date = request.GET.get('date')
    if date:
        date = datetime.date.fromisoformat(date)
    parallel = service.get_linked_services()
    timetable = service.get_timetable(date, parallel)
    stops = StopPoint.objects.select_related('locality').defer('latlong', 'locality__latlong')
    stop_codes = (row.stop.atco_code for grouping in timetable.groupings for row in grouping.rows)
    stops = stops.in_bulk(stop_codes)
    for grouping in timetable.groupings:
        grouping.apply_stops(stops)
    return render(request, 'timetable.html', {
        'object': service,
        'timetable': timetable
    })


@cache_control(max_age=86400)  # cache for a day
def service_map_data(request, service_id):
    service = get_object_or_404(Service.objects.only('geometry'), id=service_id)
    stops = service.stops.filter(
        ~Exists(Situation.objects.filter(summary='Does not stop here',
                                         consequence__stops=OuterRef('pk'),
                                         consequence__services=service)),
        latlong__isnull=False
    )
    stops = stops.distinct().order_by().select_related('locality')
    data = {
        "stops": {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': stop.latlong.coords,
                },
                'properties': {
                    'name': stop.get_qualified_name(),
                    'indicator': stop.indicator,
                    'bearing': stop.get_heading(),
                    'url': stop.get_absolute_url(),
                }
            } for stop in stops]
        }
    }

    routes = get_routes(service.route_set.select_related('source'), timezone.localdate())
    if routes:
        stops = StopTime.objects.filter(trip__route__in=routes)
    else:
        stops = StopTime.objects.filter(trip__route__service=service)

    stops = stops.select_related('stop').only('trip_id', 'stop_id', 'stop__latlong')

    route_links = {
        (route_link.from_stop_id, route_link.to_stop_id): route_link
        for route_link in service.routelink_set.all()
    }

    pairs = set()
    line_string = []
    multi_line_string = [line_string]

    previous_stop = None
    for stop in stops:
        if previous_stop and previous_stop.trip_id == stop.trip_id:
            pair = (previous_stop.stop_id, stop.stop_id)
            if pair not in pairs:
                pairs.add(pair)
                if pair in route_links:
                    line_string += route_links[pair].geometry.coords
                elif previous_stop.stop.latlong and stop.stop.latlong:
                    line_string.append(previous_stop.stop.latlong.coords)
                    line_string.append(stop.stop.latlong.coords)
            elif line_string:
                line_string = []
                multi_line_string.append(line_string)
        elif line_string:
            line_string = []
            multi_line_string.append(line_string)
        previous_stop = stop

    data["geometry"] = {
        "type": "MultiLineString",
        "coordinates": multi_line_string
    }

    return JsonResponse(data)


class OperatorSitemap(Sitemap):
    protocol = 'https'

    def items(self):
        return Operator.objects.filter(operator_has_current_services_or_vehicles).defer('search_vector')


class ServiceSitemap(Sitemap):
    protocol = 'https'

    def items(self):
        return Service.objects.filter(current=True).defer('geometry', 'search_vector')


def search(request):
    form = SearchForm(request.GET)

    context = {
        'form': form,
    }

    if form.is_valid():
        query_text = form.cleaned_data['q']
        context['query'] = query_text

        postcode = ''.join(query_text.split()).upper()
        if validation.is_valid_postcode(postcode):
            res = requests.get('https://api.postcodes.io/postcodes/' + postcode, timeout=1)
            if res.ok:
                result = res.json()['result']
                point = Point(result['longitude'], result['latitude'], srid=4326)

                context['postcode'] = Locality.objects.filter(
                    latlong__bboverlaps=point.buffer(0.05)
                ).filter(
                    Q(stoppoint__active=True) | Q(locality__stoppoint__active=True)
                ).distinct().annotate(
                    distance=Distance('latlong', point)
                ).order_by('distance').defer('latlong')[:2]

        if 'postcode' not in context:
            query = SearchQuery(query_text, search_type="websearch", config="english")

            rank = SearchRank(F('search_vector'), query)

            localities = Locality.objects.filter()
            operators = Operator.objects.filter(operator_has_current_services_or_vehicles)
            services = Service.objects.with_line_names().filter(current=True)

            services = services.annotate(operators=ArrayAgg('operator__name', distinct=True))

            for key, queryset in (
                ('localities', localities),
                ('operators', operators),
                ('services', services),
            ):
                queryset = queryset.filter(search_vector=query).annotate(rank=rank).order_by('-rank')
                context[key] = Paginator(queryset, 20).get_page(request.GET.get('page'))

            vehicles = Vehicle.objects.select_related('operator')
            query_text = query_text.replace(' ', '')
            if len(query_text) >= 5:
                if query_text.isdigit():
                    context['vehicles'] = vehicles.filter(fleet_code__iexact=query_text)
                elif not query_text.isalpha():
                    context['vehicles'] = vehicles.filter(reg__iexact=query_text)

    return render(request, 'search.html', context)


def journey(request):
    origin = request.GET.get('from')
    from_q = request.GET.get('from_q')
    destination = request.GET.get('to')
    to_q = request.GET.get('to_q')

    if origin:
        origin = get_object_or_404(Locality, slug=origin)
    if from_q:
        query = SearchQuery(from_q)
        rank = SearchRank(F('search_vector'), query)
        from_options = Locality.objects.filter(search_vector=query).annotate(rank=rank).order_by('-rank')
        if len(from_options) == 1:
            origin = from_options[0]
            from_options = None
        elif origin not in from_options:
            origin = None
    else:
        from_options = None

    if destination:
        destination = get_object_or_404(Locality, slug=destination)
    if to_q:
        query = SearchQuery(to_q)
        rank = SearchRank(F('search_vector'), query)
        to_options = Locality.objects.filter(search_vector=query).annotate(rank=rank).order_by('-rank')
        if len(to_options) == 1:
            destination = to_options[0]
            to_options = None
        elif destination not in to_options:
            destination = None
    else:
        to_options = None

    journeys = None
    # if origin and destination:
    #     journeys = Journey.objects.filter(
    #         stopusageusage__stop__locality=origin
    #     ).filter(stopusageusage__stop__locality=destination)
    # else:
    #     journeys = None

    return render(request, 'journey.html', {
        'from': origin,
        'from_q': from_q or origin or '',
        'from_options': from_options,
        'to': destination,
        'to_q': to_q or destination or '',
        'to_options': to_options,
        'journeys': journeys
    })
