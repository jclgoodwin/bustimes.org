# coding=utf-8
"""View definitions."""
import os
import json
import PIL
import ciso8601
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.http import (HttpResponse, JsonResponse, Http404,
                         HttpResponseBadRequest)
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.contrib.gis.db.models.functions import Distance
from django.contrib.sitemaps import Sitemap
from django.core.cache import cache
from django.core.mail import EmailMessage
from departures import live
from .utils import format_gbp, viglink
from .models import (Region, StopPoint, AdminArea, Locality, District,
                     Operator, Service, Note, Image)
from .forms import ContactForm, ImageForm


DIR = os.path.dirname(__file__)
FIRST_OPERATORS = {
    'FABD': 'aberdeen',
    'FTVA': 'berkshire-thames-valley',
    'FBRA': 'bradford',
    'FBRI': 'bristol-bath-and-west',
    'FCWL': 'cornwall',
    'FESX': 'essex',
    'FGLA': 'greater-glasgow',
    'FMAN': 'greater-manchester',
    'FHAL': 'halifax-calder-valley-huddersfield',
    'FLDS': 'leeds',
    'FLEI': 'leicester',
    'FECS': 'norfolk-suffolk',
    'FHAM': 'portsmouth-fareham-gosport',
    'FPOT': 'potteries',
    'FBOS': 'somerset',
    'FCYM': 'south-west-wales',
    'FSCE': 'south-east-and-central-scotland',
    'FSYO': 'south-yorkshire',
    'FSOT': 'southampton',
    'FDOR': 'wessex-dorset-south-somerset',
    'FSMR': 'worcestershire',
    'FYOR': 'york'
}


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
            for model in (Operator, StopPoint, Locality):
                model_name = model.__name__.lower()
                if model_name in view_name:
                    context = {
                        model_name: model.objects.filter(**request.resolver_match.kwargs).first()
                    }
                    break
    response = render(request, '404.html', context)
    response.status_code = 404
    return response


def offline(request):
    """Offline page (for service worker)"""
    return render(request, 'offline.html')


def apps(request):
    return render(request, 'apps.html')


def contact(request):
    """Contact page with form"""
    submitted = False
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['message'][:50].splitlines()[0]
            body = '\n\n'.join((
                form.cleaned_data['message'],
                form.cleaned_data['referrer'],
                str(request.META.get('HTTP_USER_AGENT')),
                str(request.META.get('REMOTE_ADDR'))
            ))
            message = EmailMessage(
                subject,
                body,
                '"%s" <%s>' % (form.cleaned_data['name'], 'robot@bustimes.org.uk'),
                ('contact@bustimes.org.uk',),
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
    json_string = request.POST.get('AwinTransactionPush')
    data = json.loads(json_string)
    message = '\n'.join('%s: %s' % pair for pair in data.items())
    EmailMessage(
        '💷 {} on a {} transaction'.format(format_gbp(data['commission']), format_gbp(data['transactionAmount'])),
        message,
        '%s <%s>' % ('🚌⏰🤖', 'robot@bustimes.org.uk'),
        ('contact@bustimes.org.uk',)
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


def stops(request):
    """JSON endpoint accessed by the JavaScript map,
    listing the active StopPoints within a rectangle,
    in standard GeoJSON format
    """
    try:
        bounding_box = Polygon.from_bbox(
            [request.GET[key] for key in ('xmin', 'ymin', 'xmax', 'ymax')]
        )
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
        return super(UppercasePrimaryKeyMixin, self).get_object(queryset)


class RegionDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single region and the administrative areas in it"""

    model = Region

    def get_context_data(self, **kwargs):
        context = super(RegionDetailView, self).get_context_data(**kwargs)

        context['areas'] = self.object.adminarea_set.exclude(name='')
        if len(context['areas']) == 1:
            context['districts'] = context['areas'][0].district_set.filter(locality__stoppoint__active=True).distinct()
            del context['areas']
        context['operators'] = self.object.operator_set.filter(service__current=True).distinct()

        return context


class AdminAreaDetailView(DetailView):
    """A single administrative area,
    and the districts, localities (or stops) in it
    """

    model = AdminArea
    queryset = model.objects.select_related('region')

    def get_context_data(self, **kwargs):
        context = super(AdminAreaDetailView, self).get_context_data(**kwargs)

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
        return super(AdminAreaDetailView, self).render_to_response(context)


class DistrictDetailView(DetailView):
    """A single district, and the localities in it"""

    model = District
    queryset = model.objects.select_related('admin_area', 'admin_area__region')

    def get_context_data(self, **kwargs):
        context = super(DistrictDetailView, self).get_context_data(**kwargs)
        context['localities'] = self.object.locality_set.filter(
            Q(stoppoint__active=True) | Q(locality__stoppoint__active=True),
        ).defer('latlong').distinct()
        context['breadcrumb'] = [self.object.admin_area.region, self.object.admin_area]
        return context

    def render_to_response(self, context):
        if len(context['localities']) == 1:
            return redirect(context['localities'][0])
        return super(DistrictDetailView, self).render_to_response(context)


class LocalityDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single locality, its children (if any), and the stops in it"""

    model = Locality
    queryset = model.objects.select_related(
        'admin_area', 'admin_area__region', 'district', 'parent'
    )

    def get_context_data(self, **kwargs):
        context = super(LocalityDetailView, self).get_context_data(**kwargs)

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
            raise Http404()
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
        context = super(StopPointDetailView, self).get_context_data(**kwargs)

        context['services'] = sorted(
            self.object.service_set.filter(current=True).defer('geometry').distinct(),
            key=Service.get_order
        )

        if not (self.object.active or context['services']):
            raise Http404()

        departures = cache.get(self.object.atco_code)
        if not departures:
            bot = self.request.META.get('HTTP_X_BOT')
            departures, max_age = live.get_departures(
                self.object, context['services'], bot
            )
            if hasattr(departures['departures'], 'get_departures'):
                departures['departures'] = departures['departures'].get_departures()
            if not bot:
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
        'live_sources': tuple(stop.live_sources.values_list('name', flat=True)),
        'heading': stop.heading,
        'bearing': stop.bearing,
        'stop_type': stop.stop_type,
        'bus_stop_type': stop.bus_stop_type,
        'timing_status': stop.timing_status,
        'admin_area': stop.admin_area_id,
        'active': stop.active,
    }, safe=False)


class OperatorDetailView(UppercasePrimaryKeyMixin, DetailView):
    "An operator and the services it operates"

    model = Operator
    queryset = model.objects.select_related('region')

    def get_context_data(self, **kwargs):
        context = super(OperatorDetailView, self).get_context_data(**kwargs)
        context['notes'] = self.object.note_set.all()
        context['services'] = sorted(self.object.service_set.filter(current=True).defer('geometry'),
                                     key=Service.get_order)
        if not context['services']:
            raise Http404()
        context['modes'] = {service.mode for service in context['services'] if service.mode}
        context['breadcrumb'] = [self.object.region]
        return context


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = model.objects.select_related('region').prefetch_related('operator')

    def get_object(self, **kwargs):
        try:
            return super(ServiceDetailView, self).get_object(**kwargs)
        except Http404:
            self.kwargs['pk'] = self.kwargs['slug']
            return super(ServiceDetailView, self).get_object(**kwargs)

    def post(self, *args, **kwargs):
        form = ImageForm(self.request.POST)
        service = self.get_object()
        if form.is_valid():
            service.add_flickr_photo(form.cleaned_data['url'])

        return redirect(service)

    def get_context_data(self, **kwargs):
        context = super(ServiceDetailView, self).get_context_data(**kwargs)

        if not self.object.current or 'pk' in self.kwargs:
            return context

        context['operators'] = self.object.operator.all()
        context['notes'] = Note.objects.filter(Q(operators__in=context['operators']) | Q(services=self.object)
                                               | Q(services=None, operators=None))
        context['links'] = []

        context['form'] = ImageForm()

        if self.object.show_timetable:
            date = self.request.GET.get('date')
            today = timezone.now().date()
            if date:
                try:
                    date = ciso8601.parse_datetime(date).date()
                    if date < today:
                        date = None
                except AttributeError:
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
            context['has_minor_stops'] = any(s.timing_status == 'OTH' for s in context['stopusages'])
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
            elif self.object.line_name == 'FlixBus':
                context['links'].append({
                    'url': viglink('https://www.flixbus.co.uk'),
                    'text': 'Buy tickets from FlixBus'
                })
            elif self.object.line_name == 'Ouibus':
                context['links'].append({
                    'url': viglink('https://www.ouibus.com'),
                    'text': 'Buy tickets from Ouibus'
                })
            else:
                for operator in context['operators']:
                    if operator.url.startswith('http'):
                        context['links'].append({
                            'url': operator.url,
                            'text': '%s website' % operator.name
                        })
        else:
            context['breadcrumb'] = (self.object.region,)

        traveline_url, traveline_text = self.object.get_traveline_link(date)
        if traveline_url:
            context['links'].append({
                'url': traveline_url,
                'text': 'Timetable on the %s website' % traveline_text
            })

        if self.object.description and self.object.line_name != 'FlixBus' and self.object.line_name != 'Ouibus':
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

        response = super(ServiceDetailView, self).render_to_response(context)
        response['Link'] = '<https://bustimes.org{}>; rel="canonical"'.format(self.object.get_absolute_url())
        return response


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


def image(request, id):
    image = get_object_or_404(Image, id=id)
    response = HttpResponse(content_type='image/jpeg')
    pil_image = PIL.Image.open(image.image)
    pil_image.thumbnail((600, 300), resample=PIL.Image.LANCZOS)
    pil_image.save(response, 'JPEG', quality=100)
    return response
