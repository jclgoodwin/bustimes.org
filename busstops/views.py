"View definitions."
import zipfile
import os
import re
import operator
import requests
import pytz
from datetime import datetime
from django.utils.text import slugify
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseBadRequest
from django.views.generic.detail import DetailView
from django.contrib.gis.geos import Polygon
from busstops.models import Region, StopPoint, AdminArea, Locality, District, Operator, Service
from timetables import timetable


DIR = os.path.dirname(__file__)


def index(request):
    "The home page with a list of regions"
    context = {
        'regions': Region.objects.all()
    }
    return render(request, 'index.html', context)


def cookies(request):
    "Cookie policy"
    return render(request, 'cookies.html')


def data(request):
    "Data sources"
    return render(request, 'data.html')


def hugemap(request):
    "The biggish JavaScript map"
    return render(request, 'map.html')


def stops(request):
    """
    JSON endpoint accessed by the JavaScript map,
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
    )

    return JsonResponse({
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': (stop.latlong.x, stop.latlong.y)
            },
            'properties': {
                'name': str(stop),
                'url': stop.get_absolute_url()
            }
        } for stop in results]
    })


def search(request):
    """
    A list of up to 10 localities
    whose names all contain the `request.GET['q']` string
    """
    term = request.GET.get('q')
    if term:
        parts = re.split('[^\w]', term)
        query = reduce(operator.and_, (Locality.objects.filter(name__icontains=part) for part in parts))

        response = [{
            'name': locality.get_qualified_name(),
            'url':  locality.get_absolute_url()
        } for locality in query[:12]]

        return JsonResponse(response, safe=False)


class RegionDetailView(DetailView):
    "A single region and the administrative areas in it"

    model = Region

    def get_context_data(self, **kwargs):
        context = super(RegionDetailView, self).get_context_data(**kwargs)

        context['areas'] = AdminArea.objects.filter(region=self.object).order_by('name')
        context['operators'] = Operator.objects.filter(region=self.object, service__isnull=False).distinct().order_by('name')

        return context


class AdminAreaDetailView(DetailView):
    "A single administrative area, and the districts, localities (or stops) in it"

    model = AdminArea
    queryset = model._default_manager.select_related('region')

    def get_context_data(self, **kwargs):
        context = super(AdminAreaDetailView, self).get_context_data(**kwargs)

        # Districts in this administrative area
        context['districts'] = District.objects.filter(
            admin_area=self.object,
            locality__isnull=False
        ).distinct().order_by('name')

        # Districtless localities in this administrative area
        context['localities'] = Locality.objects.filter(
            Q(stoppoint__isnull=False) | Q(locality__isnull=False),
            admin_area_id=self.object.id,
            district=None,
            parent=None
        ).defer('location').distinct().order_by('name')

        # National Rail/Air/Ferry stops
        if len(context['localities']) == 0 and len(context['districts']) == 0:
            context['stops'] = StopPoint.objects.filter(
                admin_area=self.object,
                active=True
            ).defer('location').order_by('common_name')

        context['breadcrumb'] = [self.object.region]
        return context

    def render_to_response(self, context):
        if len(context['districts']) + len(context['localities']) == 1:
            if len(context['districts']) == 1:
                return redirect(context['districts'][0])
            return redirect(context['localities'][0])
        return super(AdminAreaDetailView, self).render_to_response(context)


class DistrictDetailView(DetailView):
    "A single district, and the localities in it"

    model = District
    queryset = model._default_manager.select_related('admin_area', 'admin_area__region')

    def get_context_data(self, **kwargs):
        context = super(DistrictDetailView, self).get_context_data(**kwargs)
        context['localities'] = Locality.objects.filter(
            Q(stoppoint__isnull=False) | Q(locality__isnull=False),
            district=self.object,
            parent=None,
        ).defer('location').distinct().order_by('name')
        context['breadcrumb'] = [self.object.admin_area.region, self.object.admin_area]
        return context

    def render_to_response(self, context):
        if len(context['localities']) == 1:
            return redirect(context['localities'][0])
        return super(DistrictDetailView, self).render_to_response(context)


class LocalityDetailView(DetailView):
    "A single locality, its children (if any), and  the stops in it"

    model = Locality
    queryset = model._default_manager.select_related('admin_area', 'admin_area__region', 'district', 'parent')

    def get_context_data(self, **kwargs):
        context = super(LocalityDetailView, self).get_context_data(**kwargs)

        context['stops'] = StopPoint.objects.filter(
            locality=self.object,
            active=True
        ).order_by('common_name')

        context['localities'] = Locality.objects.filter(
            Q(stoppoint__active=True) |
            Q(locality__stoppoint__active=True),
            parent=self.object,
        ).defer('location').distinct().order_by('name')

        context['services'] = Service.objects.filter(
            stops__locality=self.object
        ).distinct().exclude(current=False).order_by('service_code')

        context['breadcrumb'] = filter(None, [
            self.object.admin_area.region,
            self.object.admin_area,
            self.object.district,
            self.object.parent
        ])

        return context


class StopPointDetailView(DetailView):
    "A stop, other stops in the same area, and the services servicing it"

    model = StopPoint
    queryset = model._default_manager.select_related('admin_area', 'admin_area__region', 'locality', 'locality__parent')

    def get_context_data(self, **kwargs):
        context = super(StopPointDetailView, self).get_context_data(**kwargs)
        if self.object.stop_area_id is not None:
            context['nearby'] = StopPoint.objects.filter(
                stop_area=self.object.stop_area_id
            ).defer('location').exclude(atco_code=self.object.atco_code).order_by('atco_code')
        context['services'] = Service.objects.filter(stops=self.object).exclude(current=False).order_by('service_code')
        context['breadcrumb'] = filter(None, [
            self.object.admin_area.region,
            self.object.admin_area,
            self.object.locality.district,
            self.object.locality.parent,
            self.object.locality,
        ])
        return context


def departures(request, pk):
    stop = get_object_or_404(StopPoint, pk=pk)
    services = {service.line_name: service for service in Service.objects.filter(stops=pk).exclude(current=False)}
    if stop.tfl:
        timezone = pytz.timezone('Europe/London')

        req = requests.get('https://api.tfl.gov.uk/StopPoint/%s/arrivals' % pk)
        items = ({
            'time': timezone.fromutc(datetime.strptime(item.get('expectedArrival'), '%Y-%m-%dT%H:%M:%SZ')),
            'service': services.get(item.get('lineName')),
            'destination': item.get('destinationName'),
        } for item in req.json())
        return render(request, 'departures.html', {
            'departures': items,
            'tfl': 'https://tfl.gov.uk/bus/stop/%s/%s' % (stop.atco_code, slugify(stop.common_name))
        })



class OperatorDetailView(DetailView):
    "An operator and the services it operates"

    model = Operator
    queryset = model._default_manager.defer('parent').select_related('region')

    def get_context_data(self, **kwargs):
        context = super(OperatorDetailView, self).get_context_data(**kwargs)
        context['services'] = Service.objects.filter(operator=self.object).exclude(current=False).order_by('service_code')
        context['breadcrumb'] = [self.object.region]
        return context


class ServiceDetailView(DetailView):
    "A service and the stops it stops at"

    model = Service
    queryset = model._default_manager.select_related('region')

    def get_context_data(self, **kwargs):
        context = super(ServiceDetailView, self).get_context_data(**kwargs)

        if self.object.current is False:
            return context

        context['operators'] = self.object.operator.all()

        context['traveline_url'] = self.object.get_traveline_url()

        context['stops'] = self.object.stops.all().select_related('locality').defer('location', 'locality__location')

        if self.object.show_timetable or '_MEGA' in self.object.service_code or 'timetable' in self.request.GET:
            context['timetables'] = timetable.timetable_from_service(self.object, context['stops'])

        if bool(context['operators']):
            context['breadcrumb'] = [self.object.region, context['operators'][0]]

        return context

    def render_to_response(self, context):
        if self.object.current is False:
            alternative = Service.objects.filter(description=self.object.description).exclude(current=False).first()
            if alternative is not None:
                return redirect(alternative)
            raise Http404()

        return super(ServiceDetailView, self).render_to_response(context)


def service_xml(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if service.region_id == 'GB':
        archive_name = 'NCSD'
        parts = pk.split('_')
        pk = '%s_%s' % (parts[-1], parts[-2])
    else:
        archive_name = service.region_id
    archive_path = os.path.join(DIR, '../data/TNDS/', archive_name + '.zip')
    archive = zipfile.ZipFile(archive_path)
    file_names = [name for name in archive.namelist() if pk in name]

    bodies = ''
    for body in (archive.open(file_name).read() for file_name in file_names):
        bodies += body
    return HttpResponse(bodies, content_type='text/xml')
