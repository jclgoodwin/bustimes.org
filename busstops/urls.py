from django.conf.urls import patterns, url

from busstops import views


urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url('map', views.hugemap),
    url('stops.json', views.stops),
    url('search.json', views.search),
    url(r'^regions/(?P<pk>[A-Z]+)/?$', views.RegionDetailView.as_view(), name='region-detail'),
    url(r'^(admin-)?areas/(?P<pk>[0-9]+)/?$', views.AdminAreaDetailView.as_view(), name='adminarea-detail'),
    url(r'^districts/(?P<pk>\d+)/?$', views.DistrictDetailView.as_view(), name='district-detail'),
    url(r'^localities/(?P<pk>[-\w]+)/?$', views.LocalityDetailView.as_view(), name='locality-detail'),
    url(r'^stops/(?P<pk>[-\w]+)/?$', views.StopPointDetailView.as_view(), name='stoppoint-detail'),
    url(r'^operators/(?P<pk>[-\w]+)/?$', views.OperatorDetailView.as_view(), name='operator-detail'),
    url(r'^services/(?P<pk>[-\w]+)/?$', views.ServiceDetailView.as_view(), name='service-detail'),
)
