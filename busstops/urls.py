from django.conf import settings
from django.conf.urls import static
from django.urls import include, path, re_path
from django.contrib import staticfiles
from django.contrib.sitemaps.views import sitemap, index
from bustimes.urls import urlpatterns as bustimes_views
from disruptions.urls import urlpatterns as disruptions_urls
from vehicles.urls import urlpatterns as vehicles_urls
from vosa.urls import urlpatterns as vosa_urls
from . import views

sitemaps = {
    'operators': views.OperatorSitemap,
    'services': views.ServiceSitemap,
}

urlpatterns = [
    path('', views.index),
    path('offline', views.offline),
    path('contact', views.contact),
    path('settings', views.settings),
    path('awin-transaction', views.awin_transaction),
    path('cookies', views.cookies),
    path('data', views.data),
    path('stops.json', views.stops),
    path('regions/<pk>', views.RegionDetailView.as_view(), name='region_detail'),
    path('places/<int:pk>', views.PlaceDetailView.as_view(), name='place_detail'),
    re_path(r'^(admin-)?areas/(?P<pk>\d+)', views.AdminAreaDetailView.as_view(), name='adminarea_detail'),
    path('districts/<int:pk>', views.DistrictDetailView.as_view(), name='district_detail'),
    re_path(r'^localities/(?P<pk>[ENen][Ss]?[0-9]+)', views.LocalityDetailView.as_view()),
    path('localities/<slug>', views.LocalityDetailView.as_view(), name='locality_detail'),
    path('stops/<pk>.json', views.stop_json),
    path('stops/<pk>.xml', views.stop_xml),
    path('stops/<pk>.txt', views.stop_gtfs),
    path('stops/<pk>', views.StopPointDetailView.as_view(), name='stoppoint_detail'),
    re_path(r'^operators/(?P<pk>[A-Z]+)$', views.OperatorDetailView.as_view()),
    path('operators/<slug>', views.OperatorDetailView.as_view(), name='operator_detail'),
    path('services/<int:service_id>.json', views.service_map_data),
    path('services/<slug>', views.ServiceDetailView.as_view(), name='service_detail'),
    path('sitemap.xml', index, {'sitemaps': sitemaps}),
    path('sitemap-<section>.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    path('search', views.search),
    path('journey', views.journey),
] + bustimes_views + disruptions_urls + vehicles_urls + vosa_urls


if settings.DEBUG and hasattr(staticfiles, 'views'):
    import debug_toolbar

    urlpatterns += [
        path('__debug__', include(debug_toolbar.urls)),
    ] + static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
      + static.static('/', document_root=settings.STATIC_ROOT)
