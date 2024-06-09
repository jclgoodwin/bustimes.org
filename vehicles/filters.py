from django_filters import BooleanFilter, CharFilter, FilterSet, NumberFilter


class VehicleRevisionFilter(FilterSet):
    vehicle__operator = CharFilter(
        label="Operator ID",
    )
    vehicle = NumberFilter(label="Vehicle ID")
    user = NumberFilter(label="User ID")
    pending = BooleanFilter()
    disapproved = BooleanFilter()
