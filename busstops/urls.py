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
    path('apps', views.apps),
    path('map', views.hugemap),
    path('stops.json', views.stops),
    path('regions/<pk>', views.RegionDetailView.as_view(), name='region_detail'),
    path('places/<int:pk>', views.PlaceDetailView.as_view(), name='place_detail'),
    url(r'^(admin-)?areas/(?P<pk>\d+)', views.AdminAreaDetailView.as_view(), name='adminarea_detail'),
    url(r'^districts/(?P<pk>\d+)', views.DistrictDetailView.as_view(), name='district_detail'),
    url(r'^localities/(?P<pk>[ENen][Ss]?[0-9]+)', views.LocalityDetailView.as_view()),
    url(r'^localities/(?P<slug>[\w-]+)', views.LocalityDetailView.as_view(), name='locality_detail'),
    url(r'^stops/(?P<pk>\w+)\.json', views.stop_json),
    url(r'^stops/(?P<pk>[\w-]+)', views.StopPointDetailView.as_view(), name='stoppoint_detail'),
    url(r'^operators/(?P<pk>[A-Z]+)$', views.OperatorDetailView.as_view()),
    url(r'^operators/(?P<slug>[\w-]+)', views.OperatorDetailView.as_view(), name='operator_detail'),
    url(r'^services/(?P<pk>[^/]+)\.xml', views.service_xml),
    url(r'^services/(?P<slug>[\w-]+)', views.ServiceDetailView.as_view(), name='service_detail'),
    path('licences/<licence_number>', views.RegistrationView.as_view()),
    path('registrations/<path:registration__registration_number>', views.VariationView.as_view(), name='variation_list'),
    url(r'^images/(?P<id>\d+)', views.image),
    url(r'^sitemap\.xml$', sitemap, {
        'sitemaps': {
             'operators': views.OperatorSitemap,
             'services': views.ServiceSitemap,
        }
    }),
    url(r'^search', SearchView(form_class=CustomSearchForm)),
    url(r'^journey', views.journey),
]


if settings.DEBUG and hasattr(staticfiles, 'views'):
    import debug_toolbar

    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls))
    ] + (
        static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        + static.static('/', document_root=settings.STATIC_ROOT)
    )
