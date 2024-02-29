from django_filters.rest_framework import CharFilter, FilterSet, NumberFilter


class VehicleRevisionFilter(FilterSet):
    vehicle__operator = CharFilter(
        label="Operator ID",
    )
    vehicle = NumberFilter(label="Vehicle ID")
    user = NumberFilter(label="User ID")
