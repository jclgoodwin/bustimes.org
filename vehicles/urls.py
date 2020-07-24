from django.urls import path
from . import views


urlpatterns = [
    path('groups/<parent>/vehicles', views.operator_vehicles, name='operator_vehicles'),
    path('operators/<slug>/vehicles', views.operator_vehicles, name='operator_vehicles'),
    path('operators/<slug>/vehicles/edit', views.operator_vehicles),
    path('services/<slug>/vehicles', views.service_vehicles_history),
    path('vehicles', views.vehicles),
    path('vehicles.json', views.vehicles_json),
    path('vehicles/<int:pk>', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('vehicles/<int:vehicle_id>/edit', views.edit_vehicle),
    path('vehicle-tracking-report', views.tracking_report),
    path('journeys/<int:pk>', views.JourneyDetailView.as_view(), name='journey_detail'),
    path('journeys/<int:pk>.json', views.journey_json),
    path('vehicles/locations/<int:location_id>', views.location_detail),
    path('siri', views.siri),
    path('map', views.map2),
]
