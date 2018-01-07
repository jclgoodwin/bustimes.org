from django.conf import settings
from django.conf.urls import include, url, static
from django.contrib import staticfiles
from django.contrib.sitemaps.views import sitemap
from haystack.views import SearchView
from .forms import CustomSearchForm
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
    url(r'^regions/(?P<pk>\w+)', views.RegionDetailView.as_view(), name='region_detail'),
    url(r'^(admin-)?areas/(?P<pk>\d+)', views.AdminAreaDetailView.as_view(), name='adminarea_detail'),
    url(r'^districts/(?P<pk>\d+)', views.DistrictDetailView.as_view(), name='district_detail'),
    url(r'^localities/(?P<pk>[A-Z0-9]+)', views.LocalityDetailView.as_view()),
    url(r'^localities/(?P<slug>[\w-]+)', views.LocalityDetailView.as_view(), name='locality_detail'),
    url(r'^stops/(?P<pk>\w+)\.json', views.stop_json),
    url(r'^stops/(?P<pk>[\w-]+)', views.StopPointDetailView.as_view(), name='stoppoint_detail'),
    url(r'^operators/(?P<pk>[A-Z]+)$', views.OperatorDetailView.as_view()),
    url(r'^operators/(?P<slug>[\w-]+)', views.OperatorDetailView.as_view(), name='operator_detail'),
    url(r'^services/(?P<pk>[^/]+)\.xml', views.service_xml),
    url(r'^services/(?P<slug>[\w-]+)', views.ServiceDetailView.as_view(), name='service_detail'),
    url(r'^images/(?P<id>\d+)', views.image),
    url(r'^sitemap\.xml$', sitemap, {
        'sitemaps': {
             'operators': views.OperatorSitemap,
             'services': views.ServiceSitemap,
        }
    }),
    url(r'^search', SearchView(form_class=CustomSearchForm)),
]


if settings.DEBUG and hasattr(staticfiles, 'views'):
    import debug_toolbar

    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls))
    ] + (
        static.static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
        + static.static('/', document_root=settings.STATIC_ROOT)
    )
