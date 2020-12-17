from django.urls import path, re_path
from . import views


urlpatterns = [
    path('services/<slug>/debug', views.ServiceDebugView.as_view()),
    re_path(r'^sources/(?P<source>\d+)/routes/(?P<code>.+)', views.route_xml, name='route_xml'),
]
