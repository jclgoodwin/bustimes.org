from django.urls import include, path
from django.contrib import admin
from accounts.views import register, RegisterConfirmView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/register/', register, name='register'),
    path('accounts/register/confirm/<uidb64>/<token>/', RegisterConfirmView.as_view(), name='register_confirm'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('busstops.urls')),
]


handler404 = 'busstops.views.not_found'
