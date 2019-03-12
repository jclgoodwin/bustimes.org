from django.urls import path
from . import views


urlpatterns = [
    path('operators/<slug>/vehicles', views.operator_vehicles),
    path('services/<slug>/vehicles', views.service_vehicles_history),
    path('vehicles', views.vehicles),
    path('vehicles.json', views.vehicles_json),
    path('vehicles/<int:pk>', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('vehicle-tracking-report', views.dashboard),
    path('journeys/<int:pk>.json', views.journey_json),
]
