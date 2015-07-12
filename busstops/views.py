from django.shortcuts import render
from django.http import JsonResponse
from django.views.generic.detail import DetailView
from busstops.models import Region, StopPoint, AdminArea, Locality, District, Operator, Service
# from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
# from datetime import datetime, date

from django.contrib.gis.geos import Polygon


def index(request):
    context = {
        'regions': Region.objects.all()
    }
    return render(request, 'index.html', context)

def hugemap(request):
    return render(request, 'map.html')

def stops(request):
    bbox = Polygon.from_bbox((request.GET['xmin'], request.GET['ymin'], request.GET['xmax'], request.GET['ymax']))
    results = StopPoint.objects.filter(latlong__within=bbox)

    data = {'type': 'FeatureCollection', 'features': []}
    for stop in results:
        data['features'].append(
            {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [stop.latlong.x, stop.latlong.y]
                },
                'properties': {
                    'name': str(stop),
                    'url': stop.get_absolute_url()
                    }
                }
            )
    return JsonResponse(data, safe=False)

def search(request):
    data = []
    query = request.GET.get('q')
    if query:
        for locality in Locality.objects.filter(name__icontains=query)[:10]:
            data.append({
                'name': str(locality) + ', ' + locality.admin_area.name,
                'url':  locality.get_absolute_url()})
    return JsonResponse(data, safe=False)


class RegionDetailView(DetailView):
    model = Region

    def get_context_data(self, **kwargs):
        context = super(RegionDetailView, self).get_context_data(**kwargs)
        context['areas'] = AdminArea.objects.filter(region=self.object).exclude(stoppoint=None).order_by('name')
        return context


class AdminAreaDetailView(DetailView):
    model = AdminArea

    def get_context_data(self, **kwargs):
        context = super(AdminAreaDetailView, self).get_context_data(**kwargs)

        # Districts in this administrative area, if any
        context['districts'] = District.objects.filter(
            admin_area=self.object, locality__stoppoint__active=True).distinct()

        # Localities in this administrative area that don't belong to any district, if any
        context['localities'] = Locality.objects.filter(
            admin_area=self.object, district=None, stoppoint__active=True
            ).distinct().order_by('name')

        # National Rail/Air/Ferry stops
        if len(context['localities']) == 0 and len(context['districts']) == 0:
            context['stops'] = StopPoint.objects.filter(
                admin_area=self.object, active=True).order_by('common_name')

        context['breadcrumb'] = [self.object.region]
        return context


class DistrictDetailView(DetailView):
    model = District

    def get_context_data(self, **kwargs):
        context = super(DistrictDetailView, self).get_context_data(**kwargs)
        context['localities'] = Locality.objects.filter(
            district=self.object, stoppoint__active=True).distinct().order_by('name')
        context['breadcrumb'] = [self.object.admin_area.region, self.object.admin_area]
        return context


class LocalityDetailView(DetailView):
    model = Locality

    def get_context_data(self, **kwargs):
        context = super(LocalityDetailView, self).get_context_data(**kwargs)
        context['stops'] = StopPoint.objects.filter(locality=self.object, active=True).order_by('common_name')
        context['breadcrumb'] = [self.object.admin_area.region, self.object.admin_area]
        return context


class StopPointDetailView(DetailView):
    model = StopPoint

    def get_context_data(self, **kwargs):
        context = super(StopPointDetailView, self).get_context_data(**kwargs)
        context['nearby'] = StopPoint.objects.filter(
            locality=self.object.locality, active=True).exclude(atco_code=self.object.atco_code)
        context['services'] = Service.objects.filter(stops=self.object).distinct()
        context['breadcrumb'] = [self.object.admin_area.region, self.object.admin_area, self.object.locality]
        return context


class OperatorDetailView(DetailView):
    model = Operator

    def get_context_data(self, **kwargs):
        context = super(OperatorDetailView, self).get_context_data(**kwargs)
        context['services'] = Service.objects.filter(operator=self.object).distinct()
        return context


class ServiceDetailView(DetailView):
    model = Service

    def get_context_data(self, **kwargs):
        context = super(ServiceDetailView, self).get_context_data(**kwargs)
        context['breadcrumb'] = [self.object.operator]
        context['stops'] = StopPoint.objects.filter(service=self.object).distinct()
        return context
