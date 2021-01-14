from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.urls import reverse
from .models import User


def get_count(obj, attribute, approved):
    count = getattr(obj, attribute, None)
    if count is None:
        count = getattr(obj, f'{attribute}_count')()
    return format_html(
        '<a href="{}?user={}&approved__{}">{}</a>',
        reverse('admin:vehicles_vehicleedit_changelist'),
        obj.id,
        approved,
        count
    )


class UserAdmin(admin.ModelAdmin):
    raw_id_fields = ['user_permissions']
    actions = ['trust', 'distrust']
    search_fields = ['username', 'email']
    readonly_fields = ['revisions', 'approved', 'disapproved', 'pending']
    list_display = ['id', 'username', 'email', 'last_login', 'is_active', 'trusted'] + readonly_fields
    list_display_links = ['id', 'username']

    def revisions(self, obj):
        return format_html(
            '<a href="{}?user={}">{}</a>',
            reverse('admin:vehicles_vehiclerevision_changelist'),
            obj.id,
            obj.revisions_count()
        )

    def approved(self, obj):
        return get_count(obj, 'approved', 'exact=1')
    approved.admin_order_field = 'approved'

    def disapproved(self, obj):
        return get_count(obj, 'disapproved', 'exact=0')
    disapproved.admin_order_field = 'disapproved'

    def pending(self, obj):
        return get_count(obj, 'pending', 'isnull=True')
    pending.admin_order_field = 'pending'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.resolver_match.view_name == 'admin:accounts_user_changelist':
            return queryset.annotate(
                approved=Count('vehicleedit', filter=Q(vehicleedit__approved=True)),
                disapproved=Count('vehicleedit', filter=Q(vehicleedit__approved=False)),
                pending=Count('vehicleedit', filter=Q(vehicleedit__approved=None)),
            )
        return queryset

    def trust(self, request, queryset):
        count = queryset.order_by().update(trusted=True)
        self.message_user(request, f'Trusted {count} users')

    def distrust(self, request, queryset):
        count = queryset.order_by().update(trusted=False)
        self.message_user(request, f'Disusted {count} users')


admin.site.register(User, UserAdmin)
