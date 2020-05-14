from django.contrib import admin
from .models import Situation, Consequence, Link, ValidityPeriod


class ConsequenceInline(admin.StackedInline):
    model = Consequence
    autocomplete_fields = ['stops', 'services', 'operators']


class ValidityPeriodInline(admin.TabularInline):
    model = ValidityPeriod


class LinkInline(admin.TabularInline):
    model = Link


class SituationAdmin(admin.ModelAdmin):
    raw_id_fields = ['source']
    inlines = [ValidityPeriodInline, LinkInline, ConsequenceInline]
    list_display = ['summary', 'reason', 'source', 'current']
    list_filter = ['reason', 'source', 'current']


admin.site.register(Situation, SituationAdmin)
