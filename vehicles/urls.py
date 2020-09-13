from django.urls import path
from . import views


urlpatterns = [
    path('groups/<parent>/vehicles', views.operator_vehicles, name='operator_vehicles'),
    path('operators/<slug>/vehicles', views.operator_vehicles, name='operator_vehicles'),
    path('operators/<slug>/vehicles/edit', views.operator_vehicles),
    path('services/<slug>/vehicles', views.service_vehicles_history),
    path('vehicles', views.vehicles),
    path('vehicles.json', views.vehicles_json),
    path('vehicles/history', views.vehicles_history),
    path('vehicles/<int:pk>', views.VehicleDetailView.as_view(), name='vehicle_detail'),
    path('vehicles/<slug>', views.VehicleDetailView.as_view()),
    path('vehicles/<int:vehicle_id>/edit', views.edit_vehicle),
    path('vehicles/<int:vehicle_id>/history', views.vehicle_history),
    path('journeys/<int:pk>', views.JourneyDetailView.as_view(), name='journey_detail'),
    path('journeys/<int:pk>/debug', views.journey_debug),
    path('journeys/<int:pk>.json', views.journey_json),
    path('vehicles/locations/<int:location_id>', views.location_detail),
    path('siri', views.siri),
    path('map', views.map),
]
