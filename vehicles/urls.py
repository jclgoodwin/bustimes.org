from django.urls import path

from . import views

urlpatterns = [
    path("groups/<parent>/vehicles", views.operator_vehicles, name="operator_vehicles"),
    path(
        "operators/<slug>/vehicles", views.operator_vehicles, name="operator_vehicles"
    ),
    path(
        "operators/<slug>/vehicles/edit",
        views.operator_vehicles,
        name="operator_vehicles_edit",
    ),
    path("operators/<slug>/map", views.operator_map, name="operator_map"),
    path("operators/<slug>/debug", views.operator_debug),
    path("services/<slug>/vehicles", views.service_vehicles_history),
    path("vehicles", views.vehicles),
    path("vehicles.json", views.vehicles_json),
    path("vehicles/debug", views.debug),
    path("vehicles/history", views.vehicles_history),
    path("vehicles/history/<int:revision_id>/revert", views.vehicle_revision_revert),
    path("vehicles/edits", views.vehicle_edits),
    path("vehicles/edits/<int:edit_id>/vote/<direction>", views.vehicle_edit_vote),
    path("vehicles/edits/<int:edit_id>/<action>", views.vehicle_edit_action),
    path("vehicles/<int:pk>", views.VehicleDetailView.as_view()),
    path("vehicles/<slug>", views.VehicleDetailView.as_view(), name="vehicle_detail"),
    path("vehicles/<int:id>/edit", views.edit_vehicle),
    path("vehicles/<slug>/edit", views.edit_vehicle, name="vehicle_edit"),
    path(
        "vehicles/<int:id>/history",
        views.vehicle_history,
    ),
    path(
        "vehicles/<slug>/history",
        views.vehicle_history,
        name="vehicle_history",
    ),
    path(
        "vehicles/<int:id>/debug",
        views.latest_journey_debug,
        name="latest_journey_debug",
    ),
    path("vehicles/<slug>/debug", views.latest_journey_debug),
    path("journeys/<int:pk>.json", views.journey_json),
    path("liveries.<int:version>.css", views.liveries_css),
    path("map", views.map),
]
