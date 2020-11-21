from django.contrib import admin
from django.db.models import Count, Q
from vehicles.admin import VehicleEditInline
from vehicles.models import VehicleRevision
from .models import User


class VehicleRevisionInline(admin.TabularInline):
    model = VehicleRevision
    fields = ['datetime', 'vehicle_id', 'from_operator_id', 'to_operator_id', 'changes']
    readonly_fields = fields
    show_change_link = True


class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'email', 'last_login', 'is_active', 'trusted',
                    'approved', 'disapproved', 'pending']
    raw_id_fields = ['user_permissions']
    inlines = [VehicleEditInline, VehicleRevisionInline]
    actions = ['trust', 'distrust']

    def approved(self, obj):
        return obj.approved
    approved.admin_order_field = 'approved'

    def disapproved(self, obj):
        return obj.disapproved
    disapproved.admin_order_field = 'disapproved'

    def pending(self, obj):
        return obj.pending
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
        count = queryset.update(trusted=True)
        self.message_user(request, f'Trusted {count} users')

    def distrust(self, request, queryset):
        count = queryset.update(trusted=False)
        self.message_user(request, f'Disusted {count} users')


admin.site.register(User, UserAdmin)
