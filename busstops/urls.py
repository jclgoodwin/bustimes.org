from django.conf.urls import url
from django.conf import settings

from django.contrib import staticfiles
from . import views

urlpatterns = [
    url(r'^$', views.index),
    url(r'^offline', views.offline),
    url(r'^contact', views.contact),
    url(r'^awin-transaction', views.awin_transaction),
    url(r'^cookies', views.cookies),
    url(r'^data', views.data),
    url(r'^map', views.hugemap),
    url(r'^stops\.json', views.stops),
    url(r'^regions/(?P<pk>\w+)', views.RegionDetailView.as_view(), name='region-detail'),
    url(r'^(admin-)?areas/(?P<pk>\d+)', views.AdminAreaDetailView.as_view(), name='adminarea-detail'),
    url(r'^districts/(?P<pk>\d+)', views.DistrictDetailView.as_view(), name='district-detail'),
    url(r'^localities/(?P<pk>\w+)', views.LocalityDetailView.as_view(), name='locality-detail'),
    url(r'^stops/(?P<pk>\w+)/departures', views.departures),
    url(r'^stops/(?P<pk>\w+)\.json', views.stop_json),
    url(r'^stops/(?P<pk>\w+)', views.StopPointDetailView.as_view(), name='stoppoint-detail'),
    url(r'^operators/(?P<pk>\w+)', views.OperatorDetailView.as_view(), name='operator-detail'),
    url(r'^services/(?P<pk>[^/]+)\.xml', views.service_xml),
    url(r'^services/(?P<pk>[^/]+)', views.ServiceDetailView.as_view(), name='service-detail'),
]

if settings.DEBUG and hasattr(staticfiles, 'views'):
    urlpatterns += [
        url(r'^(?P<path>serviceworker.js)$', staticfiles.views.serve),
    ]
