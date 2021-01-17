from django.contrib import admin
from django.db.models import Exists, OuterRef
from django.utils.safestring import mark_safe
from .models import Route, Trip, Calendar, CalendarDate, Note, StopTime, Garage


class TripInline(admin.TabularInline):
    model = Trip
    show_change_link = True
    raw_id_fields = ['destination', 'calendar', 'notes']
    fields = ['start', 'end', 'destination', 'inbound', 'calendar']


class StopTimeInline(admin.TabularInline):
    model = StopTime
    autocomplete_fields = ['stop']


class RouteAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'code', 'start_date', 'end_date']
    list_filter = [
        ('source', admin.RelatedOnlyFieldListFilter)
    ]
    raw_id_fields = ['service', 'registration']
    search_fields = ['line_name', 'line_brand', 'description']
    inlines = [TripInline]


class TripAdmin(admin.ModelAdmin):
    raw_id_fields = ['route', 'destination', 'calendar', 'notes']
    inlines = [StopTimeInline]


class CalendarDateInline(admin.TabularInline):
    model = CalendarDate


class CalendarAdmin(admin.ModelAdmin):
    list_display = ['id', '__str__', 'summary']
    inlines = [CalendarDateInline]
    readonly_fields = ['routes']

    def routes(self, obj):
        return mark_safe('<br>'.join(
            f'<a href="{route.get_absolute_url()}">{route}</a>' for route in Route.objects.filter(
                Exists(Trip.objects.filter(calendar=obj, route=OuterRef('pk')))
            )
        ))


class NoteAdmin(admin.ModelAdmin):
    list_display = ['code', 'text']
    search_fields = ['code', 'text']


admin.site.register(Route, RouteAdmin)
admin.site.register(Trip, TripAdmin)
admin.site.register(Calendar, CalendarAdmin)
admin.site.register(Note, NoteAdmin)
admin.site.register(Garage)
