from django.urls import path
from . import views


urlpatterns = [
    path("licences/<slug>", views.LicenceView.as_view(), name="licence_detail"),
    path(
        "registrations/<path:slug>",
        views.RegistrationView.as_view(),
        name="registration_detail",
    ),
    path("licences/<licence_number>/rss", views.LicenceFeed()),
    path("areas/<licence_number>/rss", views.AreaFeed()),
]
