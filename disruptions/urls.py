from django.urls import path
from . import views


urlpatterns = [
    path('disruptions/<int:id>', views.disruption, name='disruption'),
]
