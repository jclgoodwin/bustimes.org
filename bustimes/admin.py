from django.contrib import admin
from .models import Route, Trip, Calendar


class RouteAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'start_date', 'end_date']
    list_filter = ['source']
    raw_id_fields = ['service']
    search_fields = ['line_name', 'line_brand', 'description']


admin.site.register(Route, RouteAdmin)
admin.site.register(Trip)
admin.site.register(Calendar)
