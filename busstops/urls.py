from django.conf import settings
from django.conf.urls import include, url, static
from django.urls import path
from django.contrib import staticfiles
from django.contrib.sitemaps.views import sitemap
from haystack.views import SearchView
from .forms import CustomSearchForm
from . import views

urlpatterns = [
    path('', views.index),
    path('offline', views.offline),
    path('contact', views.contact),
    path('awin-transaction', views.awin_transaction),
    path('cookies', views.cookies),
    path('data', views.data),
    path('map', views.hugemap),
    path('stops.json', views.stops),
    path('regions/<pk>', views.RegionDetailView.as_view(), name='region_detail'),
    path('places/<int:pk>', views.PlaceDetailView.as_view(), name='place_detail'),
    url(r'^(admin-)?areas/(?P<pk>\d+)', views.AdminAreaDetailView.as_view(), name='adminarea_detail'),
    path('districts/<int:pk>', views.DistrictDetailView.as_view(), name='district_detail'),
    url(r'^localities/(?P<pk>[ENen][Ss]?[0-9]+)', views.LocalityDetailView.as_view()),
    path('localities/<slug>', views.LocalityDetailView.as_view(), name='locality_detail'),
    path('stops/<pk>.json', views.stop_json),
    path('stops/<pk>', views.StopPointDetailView.as_view(), name='stoppoint_detail'),
    url(r'^operators/(?P<pk>[A-Z]+)$', views.OperatorDetailView.as_view()),
    path('operators/<slug>', views.OperatorDetailView.as_view(), name='operator_detail'),
    path('operators/<slug>/vehicles', views.operator_vehicles),
    path('services/<slug>/vehicles', views.service_vehicles_history),
    path('services/<pk>.xml', views.service_xml),
    path('services/<slug>', views.ServiceDetailView.as_view(), name='service_detail'),
    path('licences/<licence_number>', views.RegistrationView.as_view(), name='registration_list'),
    path('registrations/<path:registration__registration_number>', views.VariationView.as_view(),
         name='variation_list'),
    path('vehicles', views.vehicles),
    path('vehicles.json', views.vehicles_json),
    path('vehicles/<int:pk>', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('sitemap.xml', sitemap, {
        'sitemaps': {
             'operators': views.OperatorSitemap,
             'services': views.ServiceSitemap,
        }
    }),
    path('search', SearchView(form_class=CustomSearchForm)),
    path('journey', views.journey),
]


if settings.DEBUG and hasattr(staticfiles, 'views'):
    import debug_toolbar

    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls))
    ] + (
        static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        + static.static('/', document_root=settings.STATIC_ROOT)
    )
