from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html
from django.urls import reverse

from sql_util.utils import SubqueryCount

from .models import OperatorUser, User


def get_count(obj, attribute, approved):
    return format_html(
        '<a href="{}?user={}&approved__{}">{}</a>',
        reverse("admin:vehicles_vehicleedit_changelist"),
        obj.id,
        approved,
        getattr(obj, attribute, None),
    )


class OperatorUserInline(admin.TabularInline):
    model = OperatorUser
    raw_id_fields = ["operator"]


class UserAdmin(admin.ModelAdmin):
    raw_id_fields = ["user_permissions"]
    actions = ["trust", "distrust"]
    search_fields = ["username", "email"]
    readonly_fields = ["revisions", "approved", "disapproved", "pending"]
    list_display = [
        "id",
        "username",
        "email",
        "last_login",
        "is_active",
        "trusted",
    ] + readonly_fields
    list_display_links = ["id", "username"]
    inlines = [OperatorUserInline]
    list_filter = ["is_staff", "groups"]

    def revisions(self, obj):
        return format_html(
            '<a href="{}?user={}">{}</a>',
            reverse("admin:vehicles_vehiclerevision_changelist"),
            obj.id,
            obj.revisions,
        )

    revisions.admin_order_field = "revisions"

    def approved(self, obj):
        return get_count(obj, "approved", "exact=1")

    approved.admin_order_field = "approved"

    def disapproved(self, obj):
        return get_count(obj, "disapproved", "exact=0")

    disapproved.admin_order_field = "disapproved"

    def pending(self, obj):
        return get_count(obj, "pending", "isnull=True")

    pending.admin_order_field = "pending"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.resolver_match.view_name in (
            "admin:accounts_user_changelist",
            "admin:accounts_user_change",
        ):
            return queryset.annotate(
                approved=SubqueryCount("vehicleedit", filter=Q(approved=True)),
                disapproved=SubqueryCount("vehicleedit", filter=Q(approved=False)),
                pending=SubqueryCount("vehicleedit", filter=Q(approved=None)),
                revisions=SubqueryCount("vehiclerevision"),
            )
        return queryset

    def trust(self, request, queryset):
        count = queryset.order_by().update(trusted=True)
        self.message_user(request, f"Trusted {count} users")

    def distrust(self, request, queryset):
        count = queryset.order_by().update(trusted=False)
        self.message_user(request, f"Disusted {count} users")


admin.site.register(User, UserAdmin)
