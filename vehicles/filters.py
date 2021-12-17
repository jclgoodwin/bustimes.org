from django.db.models import Q
from django_filters.rest_framework import FilterSet, CharFilter, NumberFilter, ChoiceFilter, BooleanFilter


def filter_not_empty(queryset, name, value):
    condition = Q(**{name: ''})
    if value:
        condition = ~condition
    return queryset.filter(condition)


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
            ('withdrawn', 'Withdrawn'),
            ('livery', 'Livery'),
        )
    )
    vehicle = NumberFilter()
    user = NumberFilter()
    vehicle__operator = CharFilter(label='Operator')
    vehicle__withdrawn = BooleanFilter(label='Withdrawn')
    url = BooleanFilter(label='URL', method=filter_not_empty)
    livery = NumberFilter()

    def change_filter(self, queryset, name, value):
        if value == 'livery':
            return queryset.filter(~Q(livery=None) | ~Q(colours=''))
        return queryset.filter(~Q(**{value: ''}))
