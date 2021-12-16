from django.db.models import Q
from django_filters.rest_framework import FilterSet, CharFilter, NumberFilter


class VehicleEditFilter(FilterSet):
    change = CharFilter(method='change_filter', label='Change')
    vehicle = NumberFilter()
    user = NumberFilter()
    vehicle__operator = CharFilter()
    livery = NumberFilter()

    def change_filter(self, queryset, name, value):
        if value in ('vehicle_type', 'reg', 'notes', 'branding', 'name'):
            queryset = queryset.filter(~Q(**{value: ''}))
        return queryset
