from django.urls import path
from . import views


urlpatterns = [
    path('licences/<path:slug>', views.LicenceView.as_view(), name='licence_detail'),
    path('registrations/<path:slug>', views.RegistrationView.as_view(), name='registration_detail'),
]
