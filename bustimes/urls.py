from django.urls import path
from . import views


urlpatterns = [
    path('services/<slug>/debug', views.ServiceDebugView.as_view()),
    path('services/<region>/<code>.xml', views.service_xml),
]
