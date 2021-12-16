from django.db.models import Q
from django_filters.rest_framework import FilterSet, CharFilter, NumberFilter, ChoiceFilter


class VehicleEditFilter(FilterSet):
    change = ChoiceFilter(
        method='change_filter',
        label='Change',
        choices=(
            ('reg', 'Number plate'),
            ('vehicle_type', 'Type'),
            ('name', 'Name'),
            ('notes', 'Notes'),
            ('branding', 'Branding'),
        )
    )
    vehicle = NumberFilter()
    user = NumberFilter()
    vehicle__operator = CharFilter(label='Operator')
    livery = NumberFilter()

    def change_filter(self, queryset, name, value):
        return queryset.filter(~Q(**{value: ''}))
