from django.urls import path
from . import views


urlpatterns = [
    path("licences/<licence_number>/rss", views.LicenceFeed()),
    path("licences/<path:slug>", views.licence_or_registration, name="licence_detail"),
    path(
        "registrations/<path:slug>",
        views.licence_or_registration,
        name="registration_detail",
    ),
]
