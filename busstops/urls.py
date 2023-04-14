from django.apps import apps
from django.contrib.sitemaps.views import index, sitemap
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_control
from django.views.generic.base import TemplateView

from buses.utils import cache_control_s_maxage, stale_if_error
from bustimes.urls import urlpatterns as bustimes_views
from disruptions.urls import urlpatterns as disruptions_urls
from fares import mytrip
from fares import views as fares_views
from fares.urls import urlpatterns as fares_urls
from vehicles.urls import urlpatterns as vehicles_urls
from vosa.urls import urlpatterns as vosa_urls

from . import views

sitemaps = {
    "operators": views.OperatorSitemap,
    "services": views.ServiceSitemap,
}

urlpatterns = [
    path(
        "",
        cache_control_s_maxage(3600)(
            stale_if_error(3600)(TemplateView.as_view(template_name="index.html"))
        ),
    ),
    path("offline", TemplateView.as_view(template_name="offline.html")),
    path("version", views.version),
    path("count", views.count),
    path("contact", views.contact),
    path("cookies", TemplateView.as_view(template_name="cookies.html")),
    path("503", TemplateView.as_view(template_name="503.html")),
    path("data", TemplateView.as_view(template_name="data.html")),
    path("status", views.status),
    path("timetable-source-stats.json", views.timetable_source_stats),
    path("stats.json", views.stats),
    path("robots.txt", views.robots_txt),
    path("stops.json", cache_control_s_maxage(1800)(views.stops_json)),
    path(
        "regions/<pk>",
        cache_control_s_maxage(1800)(
            stale_if_error(3600)(views.RegionDetailView.as_view())
        ),
        name="region_detail",
    ),
    path(
        "places/<int:pk>",
        views.PlaceDetailView.as_view(),
        name="place_detail",
    ),
    re_path(
        r"^(admin-)?areas/(?P<pk>\d+)",
        views.AdminAreaDetailView.as_view(),
        name="adminarea_detail",
    ),
    path(
        "districts/<int:pk>",
        views.DistrictDetailView.as_view(),
        name="district_detail",
    ),
    re_path(
        r"^localities/(?P<pk>[ENen][Ss]?[0-9]+)",
        cache_control_s_maxage(1800)(views.LocalityDetailView.as_view()),
    ),
    path(
        "localities/<slug>",
        cache_control_s_maxage(1800)(views.LocalityDetailView.as_view()),
        name="locality_detail",
    ),
    path(
        "stops/<pk>",
        cache_control_s_maxage(60)(
            stale_if_error(120)(views.StopPointDetailView.as_view())
        ),
        name="stoppoint_detail",
    ),
    path("stations/<pk>", views.StopAreaDetailView.as_view(), name="stoparea_detail"),
    path(
        "stops/<slug:atco_code>/departures",
        views.stop_departures,
    ),
    re_path(r"^operators/(?P<pk>[A-Z]+)$", views.OperatorDetailView.as_view()),
    path(
        "operators/<slug>",
        stale_if_error(3600)(views.OperatorDetailView.as_view()),
        name="operator_detail",
    ),
    path("operators/<slug>/tickets", mytrip.operator_tickets),
    path("operators/<slug>/tickets/<uuid:id>", mytrip.operator_ticket),
    path("services/<int:service_id>.json", views.service_map_data),
    path("services/<int:service_id>/timetable", views.service_timetable),
    path(
        "services/<slug>",
        stale_if_error(3600)(views.ServiceDetailView.as_view()),
        name="service_detail",
    ),
    path("services/<slug>/fares", fares_views.service_fares),
    path("sitemap.xml", cache_control(max_age=3600)(index), {"sitemaps": sitemaps}),
    path(
        "sitemap-<section>.xml",
        cache_control(max_age=3600)(sitemap),
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("search", views.search),
    path("journey", views.journey),
    path(".well-known/change-password", views.change_password),
    path("fares/", include(fares_urls)),
]

urlpatterns += bustimes_views + disruptions_urls + vehicles_urls + vosa_urls


if apps.is_installed("debug_toolbar"):
    import debug_toolbar

    urlpatterns += [
        path("__debug__", include(debug_toolbar.urls)),
    ]
