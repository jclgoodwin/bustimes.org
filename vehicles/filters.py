from django_filters import ChoiceFilter, CharFilter, FilterSet, NumberFilter


class VehicleRevisionFilter(FilterSet):
    vehicle__operator = CharFilter(
        label="Operator ID",
    )
    vehicle = NumberFilter(label="Vehicle ID")
    user = NumberFilter(label="User ID")
    status = ChoiceFilter(
        label="Status",
        choices=[
            ("pending", "pending"),
            ("approved", "approved"),
            ("disapproved", "disapproved"),
        ],
        method="status_filter",
    )

    def status_filter(self, queryset, name, value):
        match value:
            case "pending":
                return queryset.filter(pending=True, disapproved=False)
            case "disapproved":
                return queryset.filter(pending=False, disapproved=True)
            case "approved":
                return queryset.filter(pending=False, disapproved=False)
