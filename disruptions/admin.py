from django.contrib import admin
from .models import Situation, Consequence, Link


class ConsequenceInline(admin.StackedInline):
    model = Consequence
    autocomplete_fields = ['stops', 'services', 'operators']


class LinkInline(admin.TabularInline):
    model = Link


class SituationAdmin(admin.ModelAdmin):
    raw_id_fields = ['source']
    inlines = [ConsequenceInline, LinkInline]
    list_display = ['summary', 'reason', 'source']
    list_filter = ['reason', 'source']


admin.site.register(Situation, SituationAdmin)
