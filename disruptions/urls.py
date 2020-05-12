from django.urls import path
from . import views


urlpatterns = [
    path('situations/<int:id>', views.situation, name='situation'),
]
