from django.contrib import admin
from .models import Route, Trip, Calendar, Note


class RouteAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'start_date', 'end_date']
    list_filter = [
        ('source', admin.RelatedOnlyFieldListFilter)
    ]
    raw_id_fields = ['service']
    search_fields = ['line_name', 'line_brand', 'description']


class NoteAdmin(admin.ModelAdmin):
    list_display = ['code', 'text']
    search_fields = ['code', 'text']


admin.site.register(Route, RouteAdmin)
admin.site.register(Trip)
admin.site.register(Calendar)
admin.site.register(Note, NoteAdmin)
