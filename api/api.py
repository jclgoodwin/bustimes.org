from rest_framework import routers
from . import views


router = routers.DefaultRouter()
router.register("vehicles", views.VehicleViewSet)
router.register("vehiclejourneys", views.VehicleJourneyViewSet)
router.register("liveries", views.LiveryViewSet)
router.register("vehicletypes", views.VehicleTypeViewSet)
router.register("trips", views.TripViewSet)
