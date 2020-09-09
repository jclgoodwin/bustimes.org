from django.urls import include, path
from django.contrib import admin
from accounts.views import register


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/register/', register, name='register'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('busstops.urls')),
]


handler404 = 'busstops.views.not_found'
