from django.urls import path, re_path
from . import views


urlpatterns = [
    path('services/<slug>/debug', views.ServiceDebugView.as_view()),
    re_path(r'services/(?P<source>[\w ]+)/(?P<code>.+)', views.service_xml),
]
