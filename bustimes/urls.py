from django.urls import path
from . import views


urlpatterns = [
    path('routes/<int:pk>', views.RouteDetailView.as_view(), name='route_detail'),
    # path('routes/<int:pk>', views.RouteDetailView.as_view(), name='route_detail'),
    path('services/<slug>/debug', views.ServiceDebugView.as_view()),
]
