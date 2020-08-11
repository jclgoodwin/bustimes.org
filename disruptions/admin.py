from django.contrib import admin
from .models import Situation, Consequence, Link, ValidityPeriod, StopSuspension


class ConsequenceInline(admin.StackedInline):
    model = Consequence
    autocomplete_fields = ['stops', 'services', 'operators']
    show_change_link = True


class ValidityPeriodInline(admin.TabularInline):
    model = ValidityPeriod


class LinkInline(admin.TabularInline):
    model = Link


class SituationAdmin(admin.ModelAdmin):
    raw_id_fields = ['source']
    inlines = [ValidityPeriodInline, LinkInline, ConsequenceInline]
    list_display = ['summary', 'reason', 'source', 'current']
    list_filter = ['reason', 'source', 'current']


class StopSuspensionAdmin(admin.ModelAdmin):
    autocomplete_fields = ['stops', 'service']


admin.site.register(Situation, SituationAdmin)
admin.site.register(StopSuspension, StopSuspensionAdmin)
