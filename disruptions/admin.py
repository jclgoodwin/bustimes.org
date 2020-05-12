from django.contrib import admin
from .models import Situation


class SituationAdmin(admin.ModelAdmin):
    # list_display = ('code', 'fleet_number', 'fleet_code', 'reg', 'operator', 'vehicle_type',
    #                 'get_flickr_link', 'last_seen', 'livery', 'colours', 'branding', 'name', 'notes', 'data')
    # list_filter = (
    #     'withdrawn',
    #     ('source', admin.RelatedOnlyFieldListFilter),
    #     ('operator', admin.RelatedOnlyFieldListFilter),
    #     'livery',
    #     'vehicle_type',
    # )
    # list_select_related = ['operator', 'livery', 'vehicle_type', 'latest_location']
    # list_editable = ('fleet_number', 'fleet_code', 'reg', 'operator', 'vehicle_type',
    #                  'livery', 'colours', 'branding', 'name', 'notes')
    raw_id_fields = ['source']
    autocomplete_fields = ['stops', 'services', 'operator']


admin.site.register(Situation, SituationAdmin)
