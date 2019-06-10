from django.conf import settings
from django.conf.urls import include, url, static
from django.urls import path
from django.contrib import staticfiles
from django.contrib.sitemaps.views import sitemap, index
from haystack.views import SearchView
from vehicles.urls import urlpatterns as vehicles_urls
from vosa.urls import urlpatterns as vosa_urls
from .forms import CustomSearchForm
from . import views

sitemaps = {
    'operators': views.OperatorSitemap,
    'services': views.ServiceSitemap,
}

urlpatterns = [
    path('', views.index),
    path('offline', views.offline),
    path('contact', views.contact),
    path('awin-transaction', views.awin_transaction),
    path('cookies', views.cookies),
    path('data', views.data),
    path('map', views.map),
    path('vehicles', views.map),
    path('stops.json', views.stops),
    path('regions/<pk>', views.RegionDetailView.as_view(), name='region_detail'),
    path('places/<int:pk>', views.PlaceDetailView.as_view(), name='place_detail'),
    url(r'^(admin-)?areas/(?P<pk>\d+)', views.AdminAreaDetailView.as_view(), name='adminarea_detail'),
    path('districts/<int:pk>', views.DistrictDetailView.as_view(), name='district_detail'),
    url(r'^localities/(?P<pk>[ENen][Ss]?[0-9]+)', views.LocalityDetailView.as_view()),
    path('localities/<slug>', views.LocalityDetailView.as_view(), name='locality_detail'),
    path('stops/<pk>.json', views.stop_json),
    path('stops/<pk>.xml', views.stop_xml),
    path('stops/<pk>.txt', views.stop_gtfs),
    path('stops/<pk>', views.StopPointDetailView.as_view(), name='stoppoint_detail'),
    url(r'^operators/(?P<pk>[A-Z]+)$', views.OperatorDetailView.as_view()),
    path('operators/<slug>', views.OperatorDetailView.as_view(), name='operator_detail'),
    path('services/<pk>/geometry.js', views.service_geometry),
    path('services/<pk>.xml', views.service_xml),
    path('services/<slug>', views.ServiceDetailView.as_view(), name='service_detail'),
    path('sitemap.xml', index, {'sitemaps': sitemaps}),
    path('sitemap-<section>.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    path('search', SearchView(form_class=CustomSearchForm)),
    path('journey', views.journey),
] + vehicles_urls + vosa_urls


if settings.DEBUG and hasattr(staticfiles, 'views'):
    import debug_toolbar

    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls))
    ] + (
        static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        + static.static('/', document_root=settings.STATIC_ROOT)
    )
