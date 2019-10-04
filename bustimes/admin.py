from django.contrib import admin
from .models import Route, Trip, Calendar


class RouteAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'start_date', 'end_date']
    list_filter = ['source']


admin.site.register(Route, RouteAdmin)
admin.site.register(Trip)
admin.site.register(Calendar)
