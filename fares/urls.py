from django.urls import path
from . import views


urlpatterns = [
    path("", views.index),
    path("datasets/<int:pk>", views.DataSetDetailView.as_view(), name="dataset_detail"),
    path("tariffs/<int:pk>", views.TariffDetailView.as_view(), name="tariff_detail"),
    path("tables/<int:pk>", views.FareTableDetailView.as_view(), name="table_detail"),
]
