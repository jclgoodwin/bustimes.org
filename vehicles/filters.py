from django_filters import ChoiceFilter, CharFilter, FilterSet, NumberFilter
from django.db.models import Q


class VehicleRevisionFilter(FilterSet):
    operator = CharFilter(label="Operator ID", method="operator_filter")
    vehicle = NumberFilter(label="Vehicle ID")
    user = NumberFilter(label="User ID")
    approved_by = NumberFilter(label="(Dis)approver")
    status = ChoiceFilter(
        label="Status",
        choices=[
            ("pending", "pending"),
            ("approved", "approved"),
            ("disapproved", "disapproved"),
        ],
        method="status_filter",
    )

    def operator_filter(self, queryset, _, value):
        return queryset.filter(
            Q(vehicle__operator=value) | Q(from_operator=value) | Q(to_operator=value)
        )

    def status_filter(self, queryset, _, value):
        match value:
            case "pending":
                return queryset.filter(pending=True, disapproved=False)
            case "disapproved":
                return queryset.filter(pending=False, disapproved=True)
            case "approved":
                return queryset.filter(pending=False, disapproved=False)
