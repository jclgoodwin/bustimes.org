from django.conf.urls import patterns, url
# from django.shortcuts import redirect

from busstops import views

# sitemaps = {
#     'events': views.EventsSitemap,
#     'static': views.StaticViewSitemap,
# }

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^regions/(?P<pk>[A-Z]+)/$', views.RegionDetailView.as_view(), name='region-detail'),
    url(r'^admin-areas/(?P<pk>[0-9]+)/$', views.AdminAreaDetailView.as_view(), name='adminarea-detail'),
    url(r'^districts/(?P<pk>[0-9]+)/$', views.DistrictDetailView.as_view(), name='district-detail'),
    url(r'^localities/(?P<pk>[-\w]+)/$', views.LocalityDetailView.as_view(), name='locality-detail'),
    url(r'^stops/(?P<pk>[-\w]+)/$', views.StopPointDetailView.as_view(), name='stoppoint-detail'),
    # url(r'^press/', views.press, name='press'),
    # url(r'^sitemap\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemaps}),
    # url(r'^(?P<slug>[-_\w]+)/$', views.DetailView.as_view(), name='event'),
)
