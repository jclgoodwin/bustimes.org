from django.shortcuts import render
from django.views.generic.detail import DetailView
from busstops.models import StopPoint, Locality, AdminArea, Region, District
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def index(request):
    context = {
        # 'localities': Locality.objects.all()[:20],
        # 'towns': StopPoint.objects.order_by().values_list('town', flat=True).distinct(),
        # 'grandparent_localities': Locality.objects.order_by().values_list('grandparent_name', flat=True).distinct(),
        'regions': Region.objects.all()
    }

    return render(request, 'index.html', context)


class RegionDetailView(DetailView):
    model = Region

    def get_context_data(self, **kwargs):
        context = super(RegionDetailView, self).get_context_data(**kwargs)
        context['areas'] = AdminArea.objects.filter(region=self.object).order_by('name')
        return context


class AdminAreaDetailView(DetailView):
    model = AdminArea

    def get_context_data(self, **kwargs):
        context = super(AdminAreaDetailView, self).get_context_data(**kwargs)
        context['districts'] = District.objects.filter(admin_area=self.object)#.order_by('name')
        context['localities'] = Locality.objects.filter(admin_area=self.object).order_by('name')
        context['stops'] = StopPoint.objects.filter(admin_area=self.object).order_by('common_name')
        return context


class DistrictDetailView(DetailView):
    model = District

    def get_context_data(self, **kwargs):
        context = super(DistrictDetailView, self).get_context_data(**kwargs)
        context['localities'] = Locality.objects.filter(district=self.object).order_by('name')
        return context


class LocalityDetailView(DetailView):
    model = Locality

    def get_context_data(self, **kwargs):
        context = super(LocalityDetailView, self).get_context_data(**kwargs)
        context['stops'] = StopPoint.objects.filter(locality=self.object).order_by('common_name')

        if context['stops']:
            coordinates = map(lambda s: s.location, context['stops']);
            latitudes = map(lambda s: s.latitude, coordinates)
            longitudes = map(lambda s: s.longitude, coordinates)
            context['max_longitude'] = max(longitudes)
            context['min_longitude'] = min(longitudes)
            context['max_latitude'] = max(latitudes)
            context['min_latitude'] = min(latitudes)
            context['mid_longitude'] = (context['min_longitude'] + context['max_longitude']) / 2;
            context['mid_latitude'] = (context['min_latitude'] + context['max_latitude']) / 2;

        return context


class StopPointDetailView(DetailView):
    model = StopPoint

    def get_context_data(self, **kwargs):
        context = super(StopPointDetailView, self).get_context_data(**kwargs)
        context['nearby'] = StopPoint.objects.filter(locality=self.object.locality)
        return context
