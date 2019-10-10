# coding=utf-8
"""View definitions."""
import os
import json
import ciso8601
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Prefetch, F
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseBadRequest
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.generic.detail import DetailView
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.core.mail import EmailMessage
from haystack.query import SearchQuerySet
from departures import live
from .utils import format_gbp
from .models import Region, StopPoint, AdminArea, Locality, District, Operator, Service, Note, Journey, Place
from .forms import ContactForm


prefetch_stop_services = Prefetch(
    'service_set', to_attr='current_services',
    queryset=Service.objects.filter(current=True).distinct('line_name', 'stops').order_by().defer('geometry')
)


def index(request):
    """The home page with a list of regions"""
    return render(request, 'index.html', {
        'regions': True
    })


def not_found(request, exception):
    """Custom 404 handler view"""
    if request.resolver_match:
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
            'referrer': referrer
        })
    return render(request, 'contact.html', {
        'form': form,
        'submitted': submitted
    })


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


def map(request):
    """The full-page slippy map"""
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
        latlong__within=bounding_box, active=True, service__current=True
    ).prefetch_related(
        prefetch_stop_services
    ).select_related('locality').defer('osm', 'locality__latlong').distinct()

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
                'indicator': stop.indicator,
                'bearing': stop.get_heading(),
                'url': stop.get_absolute_url(),
                'services': stop.get_line_names()
            }
        } for stop in results]
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

        context['stops'] = self.object.stoppoint_set.filter(active=True, service__current=True).distinct()
        context['stops'] = context['stops'].prefetch_related(prefetch_stop_services).defer('osm')

        if not (context['localities'] or context['stops']):
            raise Http404('Sorry, it looks like no services currently stop at {}'.format(self.object))
        elif context['stops']:
            context['services'] = sorted(Service.objects.filter(
                stops__locality=self.object,
                current=True
            ).prefetch_related('operator').defer('geometry').distinct(), key=Service.get_order)
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

        services = self.object.service_set.filter(current=True).defer('geometry')
        services = services.annotate(direction=F('stopusage__direction')).distinct('pk').order_by()
        context['services'] = sorted(services.prefetch_related('operator'), key=Service.get_order)

        if not (self.object.active or context['services']):
            raise Http404('Sorry, it looks like no services currently stop at {}'.format(self.object))

        departures = cache.get(self.object.atco_code)
        if not departures:
            departures, max_age = live.get_departures(self.object, context['services'])
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

        nearby = StopPoint.objects.filter(active=True, service__current=True).distinct()

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
        elif self.object.atco_code[:3] in {'je-', 'gg-'}:
            nearby = nearby.filter(common_name__iexact=self.object.common_name,
                                   atco_code__startswith=self.object.atco_code[:3])
        else:
            nearby = None

        if nearby is not None:
            context['nearby'] = nearby.exclude(pk=self.object.pk).prefetch_related(prefetch_stop_services).defer('osm')

        context['breadcrumb'] = [crumb for crumb in (
            region,
            self.object.admin_area,
            self.object.locality and self.object.locality.district,
            self.object.locality and self.object.locality.parent,
            self.object.locality,
        ) if crumb is not None]
        return context


def stop_gtfs(_, pk):
    stop = get_object_or_404(StopPoint, atco_code=pk)
    content = 'stop_id,stop_name,stop_lat,stop_lon\n{},{},{},{}\n'.format(
        stop.atco_code, stop.get_qualified_name(), stop.latlong.y, stop.latlong.x)
    return HttpResponse(content, content_type='text/plain')


def stop_xml(_, pk):
    stop = get_object_or_404(StopPoint, atco_code=pk)
    source = stop.admin_area.sirisource_set.first()
    if source:
        departures = live.SiriSmDepartures(source, stop, ())
        return HttpResponse(departures.get_response().text, content_type='text/xml')
    raise Http404()


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
                name=self.object.name,
                service__current=True
            ).first()
            if alternative:
                return redirect(alternative)
            raise Http404
        return super().render_to_response(context)


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = model.objects.select_related('region', 'source').prefetch_related('operator')

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

        related_q = Q(link_from__to_service=self.object) | Q(link_to__from_service=self.object)
        if self.object.description and self.object.line_name:
            related_q |= Q(description=self.object.description)
            related_q |= Q(line_name=self.object.line_name, operator__in=context['operators'])
        related = Service.objects.filter(related_q, current=True).exclude(pk=self.object.pk).defer('geometry')
        context['related'] = sorted(related.distinct().prefetch_related('operator'), key=Service.get_order)

        if self.object.show_timetable and not self.object.timetable_wrong:
            date = self.request.GET.get('date')
            today = timezone.localtime().date()
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
                next_usage = self.object.journey_set.filter(datetime__date__gte=today).values('datetime__date').first()
                if next_usage:
                    date = next_usage['datetime__date']
            if context['related']:
                parallel = list(Service.objects.filter(
                    Q(link_from__to_service=self.object, link_from__how='parallel')
                    | Q(link_to__from_service=self.object, link_to__how='parallel')
                ).order_by().defer('geometry'))
            else:
                parallel = []
            context['timetable'] = self.object.get_timetable(date, parallel)
        else:
            date = None

        if not context.get('timetable') or not context['timetable'].groupings:
            context['stopusages'] = self.object.stopusage_set.all().select_related(
                'stop__locality'
            ).defer('stop__osm', 'stop__locality__latlong')
            context['has_minor_stops'] = any(s.is_minor() for s in context['stopusages'])
        else:
            stops = StopPoint.objects.select_related('locality').defer('osm', 'latlong', 'locality__latlong')
            context['timetable'].groupings = [grouping for grouping in context['timetable'].groupings
                                              if type(grouping.rows) is not list or
                                              grouping.rows and grouping.rows[0].times]
            stops = stops.in_bulk(row.stop for grouping in context['timetable'].groupings for row in grouping.rows)
            for grouping in context['timetable'].groupings:
                grouping.rows = [row for row in grouping.rows if any(row.times)]
                for row in grouping.rows:
                    row.stop = stops.get(row.stop)
        try:
            context['breadcrumb'] = [Region.objects.filter(adminarea__stoppoint__service=self.object).distinct().get()]
        except (Region.DoesNotExist, Region.MultipleObjectsReturned):
            context['breadcrumb'] = [self.object.region]

        if self.object.is_megabus():
            context['links'].append({
                'url': self.object.get_megabus_url(),
                'text': 'Buy tickets at megabus.com'
            })

        if context['operators']:
            context['breadcrumb'].append(context['operators'][0])
            context['payment_methods'] = context['operators'][0].payment_methods.all()
            for operator in context['operators']:
                if operator.is_national_express() or self.object.service_code == 'DNAX090':
                    context['links'].append({
                        'url': operator.get_national_express_url(),
                        'text': 'Buy tickets at nationalexpress.com'
                    })

        traveline_url, traveline_text = self.object.get_traveline_link(date)
        if traveline_url:
            context['links'].append({
                'url': traveline_url,
                'text': 'Timetable on the %s website' % traveline_text
            })

        return context

    def render_to_response(self, context):
        if not self.object.current:
            alternative = Service.objects.filter(
                line_name=self.object.line_name,
                stopusage__stop_id__in=self.object.stopusage_set.values_list('stop_id', flat=True),
                current=True
            ).defer('geometry').first() or Service.objects.filter(
                description=self.object.description,
                current=True
            ).defer('geometry').first()

            if alternative is not None:
                return redirect(alternative, permanent=True)

            raise Http404()

        if 'pk' in self.kwargs:
            return redirect(self.object, permanent=True)

        return super().render_to_response(context)


@cache_control(max_age=86400)
def service_map_data(request, pk):
    service = get_object_or_404(Service, pk=pk)
    stops = StopPoint.objects.filter(service=service, latlong__isnull=False).select_related('locality')
    data = {
        "stops": {
            'type': 'FeatureCollection',
            'features': [{
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': tuple(stop.latlong)
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
    if service.geometry:
        data['geometry'] = json.loads(service.geometry.simplify().json)
    return JsonResponse(data)


def service_xml(request, pk):
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
        return Service.objects.filter(current=True).defer('geometry')


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
