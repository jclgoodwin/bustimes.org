from django.conf import settings
from django.urls import include, path, re_path
from django.views.generic.base import TemplateView
from django.contrib.sitemaps.views import sitemap, index
from bustimes.urls import urlpatterns as bustimes_views
from disruptions.urls import urlpatterns as disruptions_urls
from vehicles.urls import urlpatterns as vehicles_urls
from vosa.urls import urlpatterns as vosa_urls
from fares.urls import urlpatterns as fares_urls
from fares import views as fares_views
from . import views

sitemaps = {
    "operators": views.OperatorSitemap,
    "services": views.ServiceSitemap,
}

urlpatterns = [
    path("", TemplateView.as_view(template_name="index.html")),
    path("offline", TemplateView.as_view(template_name="offline.html")),
    path("contact", views.contact),
    path("cookies", TemplateView.as_view(template_name="cookies.html")),
    path("data", TemplateView.as_view(template_name="data.html")),
    path("status", views.status),
    path("robots.txt", views.robots_txt),
    path(
        "ads.txt",
        TemplateView.as_view(template_name="ads.txt", content_type="text/plain"),
    ),
    path("stops.json", views.stops),
    path("regions/<pk>", views.RegionDetailView.as_view(), name="region_detail"),
    path("places/<int:pk>", views.PlaceDetailView.as_view(), name="place_detail"),
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
        views.LocalityDetailView.as_view(),
    ),
    path(
        "localities/<slug>",
        views.LocalityDetailView.as_view(),
        name="locality_detail",
    ),
    path(
        "stops/<pk>",
        views.StopPointDetailView.as_view(),
        name="stoppoint_detail",
    ),
    re_path(r"^operators/(?P<pk>[A-Z]+)$", views.OperatorDetailView.as_view()),
    path(
        "operators/<slug>",
        views.OperatorDetailView.as_view(),
        name="operator_detail",
    ),
    path("operators/<slug>/tickets", fares_views.operator_tickets),
    path("operators/<slug>/tickets/<id>", fares_views.operator_ticket),
    path("services/<int:service_id>.json", views.service_map_data),
    path("services/<int:service_id>/timetable", views.service_timetable),
    path(
        "services/<slug>",
        views.ServiceDetailView.as_view(),
        name="service_detail",
    ),
    path("services/<slug>/fares", fares_views.service_fares),
    path("sitemap.xml", index, {"sitemaps": sitemaps}),
    path(
        "sitemap-<section>.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("search", views.search),
    path("journey", views.journey),
    path(".well-known/change-password", views.change_password),
    path("fares/", include(fares_urls)),
]

urlpatterns += bustimes_views + disruptions_urls + vehicles_urls + vosa_urls


if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path("__debug__", include(debug_toolbar.urls)),
    ]
