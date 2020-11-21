from django.contrib import admin
from vehicles.admin import VehicleEditInline
from vehicles.models import VehicleRevision
from .models import User


class VehicleRevisionInline(admin.TabularInline):
    model = VehicleRevision
    fields = ['datetime', 'vehicle_id', 'from_operator_id', 'to_operator_id', 'changes']
    readonly_fields = fields
    show_change_link = True


class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'email', 'last_login', 'is_active']
    raw_id_fields = ['user_permissions']
    inlines = [VehicleEditInline, VehicleRevisionInline]


admin.site.register(User, UserAdmin)
