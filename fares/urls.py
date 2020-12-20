from django.urls import path
from . import views


urlpatterns = [
    path('', views.index),
    path('datasets/<int:pk>', views.DataSetDetailView.as_view(), name='dataset_detail'),
    path('tariffs/<int:pk>', views.TariffDetailView.as_view(), name='tariff_detail'),
]
