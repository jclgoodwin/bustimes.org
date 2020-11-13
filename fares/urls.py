from django.urls import path
from . import views


urlpatterns = [
    path('tariffs/<int:pk>', views.TariffDetailView.as_view(), name='tariff_detail'),
]
