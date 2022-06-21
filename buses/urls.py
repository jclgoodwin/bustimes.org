from django.urls import include, path
from django.contrib import admin
from api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/", include(api.router.urls)),
    path("", include("busstops.urls")),
]


handler404 = "busstops.views.not_found"
handler500 = "busstops.views.error"
