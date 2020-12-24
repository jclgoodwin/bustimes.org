from django.urls import path, re_path
from . import views


urlpatterns = [
    path('services/<slug>/debug', views.ServiceDebugView.as_view()),
    re_path(r'^sources/(?P<source>\d+)/routes/(?P<code>.*)', views.route_xml, name='route_xml'),
    path('stops/<pk>/times.json', views.stop_times_json),
    path('trips/<pk>.json', views.trip_json),
]
