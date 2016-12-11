# coding=utf-8
"""View definitions."""
import os
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.http import (HttpResponse, JsonResponse, Http404,
                         HttpResponseBadRequest)
from django.utils.cache import patch_response_headers
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.contrib.gis.geos import Polygon
from django.contrib.gis.db.models.functions import Distance
from django.core.mail import EmailMessage
from departures import live
from .utils import timetable_from_service, get_files_from_zipfile
from .models import (Region, StopPoint, AdminArea, Locality, District,
                     Operator, Service, Note)
from .forms import ContactForm


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
    context = {
        'regions': Region.objects.all().order_by('name')
    }
    return render(request, 'index.html', context)


def not_found(request):
    """Custom 404 handler view"""
    if (request.resolver_match
            and request.resolver_match.url_name == 'service-detail'):
        service_code = request.resolver_match.kwargs.get('pk')
        service = Service.objects.filter(service_code=service_code).defer('geometry').first()
        localities = Locality.objects.filter(stoppoint__service=service).distinct()
        context = {
            'service': service,
            'localities': localities,
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
        form = ContactForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['message'][:50].splitlines()[0]
            body = '\n\n'.join((
                form.cleaned_data['message'],
                form.cleaned_data['referrer'],
                str(request.META.get('HTTP_USER_AGENT')),
                str(request.META.get('HTTP_X_REAL_IP'))
            ))
            message = EmailMessage(
                subject,
                body,
                '"%s" <%s>' % (form.cleaned_data['name'],
                               'contact@bustimes.org.uk'),
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
        '💷 £{commission} on a £{transactionAmount} transaction'.format(**data),
        message,
        '%s <%s>' % ('🚌⏰🤖', 'contact@bustimes.org.uk'),
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
    ).order_by('distance').defer('locality__latlong')

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
        if primary_key is not None and not primary_key.isupper():
            self.kwargs['pk'] = primary_key.upper()
        return super(UppercasePrimaryKeyMixin, self).get_object(queryset)


class RegionDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A single region and the administrative areas in it"""

    model = Region

    def get_context_data(self, **kwargs):
        context = super(RegionDetailView, self).get_context_data(**kwargs)

        context['areas'] = AdminArea.objects.filter(region=self.object).order_by('name')
        context['operators'] = Operator.objects.filter(
            region=self.object, service__current=True
        ).distinct().order_by('name')

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
        context['districts'] = District.objects.filter(
            admin_area=self.object,
            locality__stoppoint__active=True
        ).distinct().order_by('name')

        # Districtless localities in this administrative area
        context['localities'] = Locality.objects.filter(
            Q(stoppoint__active=True) | Q(locality__stoppoint__active=True),
            admin_area_id=self.object.id,
            district=None,
            parent=None
        ).defer('latlong').distinct().order_by('name')

        # National Rail/Air/Ferry stops
        if not (context['localities'] or context['districts']):
            context['stops'] = StopPoint.objects.filter(
                admin_area=self.object,
                active=True
            ).order_by('common_name')

        context['breadcrumb'] = [self.object.region]
        return context

    def render_to_response(self, context):
        if len(context['districts']) + len(context['localities']) == 1:
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
        context['localities'] = Locality.objects.filter(
            Q(stoppoint__active=True) | Q(locality__stoppoint__active=True),
            district=self.object
        ).defer('latlong').distinct().order_by('name')
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

        context['localities'] = Locality.objects.filter(
            Q(stoppoint__active=True) |
            Q(locality__stoppoint__active=True),
            parent=self.object,
        ).defer('latlong').distinct().order_by('name')

        context['stops'] = StopPoint.objects.filter(
            locality=self.object,
            active=True
        ).order_by('common_name')

        if not (context['localities'] or context['stops']):
            raise Http404()
        elif context['stops']:
            context['services'] = Service.objects.filter(
                stops__locality=self.object,
                current=True
            ).defer('geometry').distinct().order_by('service_code')
            context['modes'] = {service.mode for service in context['services'] if service.mode}

        context['breadcrumb'] = (crumb for crumb in [
            self.object.admin_area.region,
            self.object.admin_area,
            self.object.district,
            self.object.parent
        ] if crumb is not None)

        return context


class StopPointDetailView(UppercasePrimaryKeyMixin, DetailView):
    """A stop, other stops in the same area, and the services servicing it"""

    model = StopPoint
    queryset = model.objects.select_related('admin_area', 'admin_area__region',
                                            'locality', 'locality__parent',
                                            'locality__district')

    def get_context_data(self, **kwargs):
        context = super(StopPointDetailView, self).get_context_data(**kwargs)

        context['services'] = Service.objects.filter(
            stops=self.object, current=True
        ).defer('geometry').distinct().order_by('service_code')

        if not (self.object.active or context['services']):
            raise Http404()

        text = ', '.join(part for part in (
            'on ' + self.object.street if self.object.street else None,
            'near ' + self.object.crossing if self.object.crossing else None,
            'near ' + self.object.landmark if self.object.landmark else None,
        ) if part is not None)
        if text:
            context['text'] = text[0].upper() + text[1:]

        context['modes'] = {service.mode for service in context['services'] if service.mode}

        if self.object.stop_area_id is not None:
            context['nearby'] = StopPoint.objects.filter(stop_area=self.object.stop_area_id)
        else:
            context['nearby'] = StopPoint.objects.filter(
                common_name=self.object.common_name, locality=self.object.locality)
        context['nearby'] = context['nearby'].filter(active=True).exclude(
            pk=self.object.pk
        ).order_by('atco_code')

        context['breadcrumb'] = (crumb for crumb in (
            self.object.admin_area.region if self.object.admin_area else Region.objects.get(pk='NI'),
            self.object.admin_area,
            self.object.locality.district if self.object.locality else None,
            self.object.locality.parent if self.object.locality else None,
            self.object.locality,
        ) if crumb is not None)
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


def departures(request, pk):
    stop = get_object_or_404(StopPoint, atco_code=pk)
    context, max_age = live.get_departures(
        stop, Service.objects.filter(stops=pk, current=True).defer('geometry')
    )
    if hasattr(context['departures'], 'get_departures'):
        context['departures'] = context['departures'].get_departures()
    response = render(request, 'departures.html', context)
    patch_response_headers(response, cache_timeout=max_age)
    return response


class OperatorDetailView(UppercasePrimaryKeyMixin, DetailView):
    "An operator and the services it operates"

    model = Operator
    queryset = model.objects.defer('parent').select_related('region')

    def get_context_data(self, **kwargs):
        context = super(OperatorDetailView, self).get_context_data(**kwargs)
        context['notes'] = Note.objects.filter(operators=self.object)
        context['services'] = Service.objects.filter(operator=self.object, current=True).order_by(
            'service_code').defer('geometry')
        if not context['services']:
            raise Http404()
        context['modes'] = {service.mode for service in context['services'] if service.mode}
        areas = AdminArea.objects.filter(stoppoint__service__in=context['services']).distinct()
        context['breadcrumb'] = [self.object.region]
        if len(areas) == 1:
            context['breadcrumb'].append(areas[0])
        return context


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = model.objects.select_related('region').prefetch_related('operator')

    def get_context_data(self, **kwargs):
        context = super(ServiceDetailView, self).get_context_data(**kwargs)

        if not self.object.current:
            return context

        context['operators'] = self.object.operator.all()
        context['notes'] = Note.objects.filter(Q(operators__in=context['operators']) | Q(services=self.object))
        context['links'] = []

        if (self.object.show_timetable or '_MEGA' in self.object.service_code
                or 'timetable' in self.request.GET):
            context['timetables'] = [timetable for timetable in timetable_from_service(self.object)
                                     if not timetable.operating_period.finishes_in_past()]
            context['timetables'].sort(key=lambda t: t.operating_period.start)

        if 'timetables' not in context or context['timetables'] == []:
            context['stopusages'] = self.object.stopusage_set.all().select_related(
                'stop__locality'
            ).defer('stop__locality__latlong').order_by('direction', 'order')
            context['has_minor_stops'] = any(s.timing_status == 'OTH' for s in context['stopusages'])
        else:
            stops_dict = {stop.pk: stop for stop in self.object.stops.all().select_related(
                'locality').defer('latlong', 'locality__latlong')}
            for table in context['timetables']:
                for grouping in table.groupings:
                    for row in grouping.rows:
                        row.part.stop.stop = stops_dict.get(row.part.stop.atco_code)

        if bool(context['operators']):
            operator = context['operators']
            context['breadcrumb'] = (self.object.region, context['operators'][0])
            if self.object.is_megabus():
                context['links'].append({
                    'url': 'https://www.awin1.com/awclick.php?mid=2678&id=242611&clickref=links',
                    'text': 'Buy tickets from megabus.com'
                })
            else:
                for operator in context['operators']:
                    if operator.pk in FIRST_OPERATORS:
                        context['links'].append({
                            'url': 'https://www.firstgroup.com/%s/tickets' % FIRST_OPERATORS[operator.pk],
                            'text': 'Fares and tickets on the %s website' % operator.name
                        })
                    elif operator.url.startswith('http'):
                        context['links'].append({
                            'url': operator.url,
                            'text': '%s website' % operator.name
                        })
        else:
            context['breadcrumb'] = (self.object.region,)

        traveline_url = self.object.get_traveline_url()
        if traveline_url:
            if self.object.net == 'tfl':
                traveline_text = 'Transport for London'
            elif self.object.region_id == 'S':
                traveline_text = 'Traveline Scotland'
            else:
                traveline_text = 'Traveline'
            context['links'].append({
                'url': traveline_url,
                'text': 'Timetable on the %s website' % traveline_text
            })

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
                return redirect(alternative)

            raise Http404()

        return super(ServiceDetailView, self).render_to_response(context)


def service_xml(_, pk):
    service = get_object_or_404(Service, service_code=pk)
    bodies = (xml_file.read().decode() for xml_file in get_files_from_zipfile(service))
    return HttpResponse(bodies, content_type='text/plain')
